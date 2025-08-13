import time
import numpy as np

import numpy as np
import pyqtgraph as pg
from qtpy import QtCore, QtWidgets

from ScopeFoundry import Measurement, h5_io


class PulseHeightAnalyze(Measurement):

    name = "pulse_height_analyzer"

    def setup(self):
        """
        Runs once during app initialization.
        This is where you define your settings and set up data structures.
        """

        s = self.settings
        s.New("sampling_period", float, initial=0.01, unit="s")
        s.New("threshold", float, initial=0.01, units="V")
        s.New("N", int, initial=1001)
        s.New("save_h5", bool, initial=True)
        s.New("device", str, initial="ads")
        #s.New("bin_range", int, initial=2048) #why doesn't this work properly
        #self.data = {"y": np.ones(self.settings["N"])}
        self.data = {}
        self.pulse_sum = None  # running sum of buffers
        self.pulse_count = 0
    
    def run(self):
        if self.settings.device == "ni":
            self.run_ni()
        else:
            self.run_ads()
    
    def run_ads(self):
        hw = self.app.hardware["ads"]
        noise_threshold = self.settings["threshold"]

        hw.open_scope()
        #hw.trigger_scope() ...why doesn't this work? can't read scope after being triggered
        bit_res = 2048
        #self.data["x"] = np.array([])
        #self.data["y"] = np.array([])
        #self.update_display()
        values = []

        legit_data_points = 0
        while legit_data_points <= self.settings["N"]:
            buffer = hw.read_scope()
            base = np.average(buffer[200:400])
            height = np.max(buffer[400:900])
            if height >= noise_threshold:
                legit_data_points += 1
                values.append(int((height - base) * bit_res))
                counts, bins = np.histogram(values, bins=range(bit_res))
                self.data["x"] = bins
                self.data["y"] = counts
                buffer = np.array(buffer, dtype=np.float64)

                if self.pulse_sum is None:
                    self.pulse_sum = np.zeros_like(buffer)

                self.pulse_sum += buffer
                self.pulse_count += 1

                # Compute running average
                running_avg = self.pulse_sum / self.pulse_count

                # Store for plotting
                self.data["avg_pulse"] = running_avg
                self.update_display()
                #QtWidgets.QApplication.processEvents()
                if legit_data_points % 10 == 0:
                    self.set_progress(legit_data_points * 100.0 / self.settings["N"])

                # break the loop if user desires.
                if self.interrupt_measurement_called:
                    break
        hw.close_scope()
        #plt.step(bins[2000:-1], counts[2000:], where="post")
        #plt.show()
        """
        y = self.data["y"] = np.ones(self.settings["N"])
        #self.data["y"] = hw.read_scope(wait=self.settings["sampling_period"])

        for i in range(self.settings["N"]):
            values = hw.read_scope()
            y[i] = np.mean(values)

            time.sleep(self.settings["sampling_period"])

            self.set_progress(i * 100.0 / self.settings["N"])

            # break the loop if user desires.
            if self.interrupt_measurement_called:
                break
        """

        if self.settings["save_h5"]:
            # saves data, closes file,
            self.save_h5(data=self.data)

    def run_ni(self):
        """
        Runs when the measurement starts. Executes in a separate thread from the GUI.
        It should not update the graphical interface directly and should focus only
        on data acquisition.
        """
        # Prepare an array for data in memory.
        #y = self.data["y"] = np.ones(self.settings["N"])
        intermediate_values = np.ones(self.settings["N"])
        bin_range = 2048
        values = []

        # Get a reference to the hardware
        hw = self.app.hardware["ni_dac"]

        # Sample the hardware for values N times
        for i in range(self.settings["N"]):

            # read data from device.
            intermediate_values[i] = hw.settings.get_lq("dac_val").read_from_hardware()
            #height = ...
            #base = ...
            #values.append(int((height - base) * bin_range))
            #counts, bins = np.histogram(values, bins=range(bin_range))
            #self.data["x"] = bins
            #self.data["y"] = counts
            self.update_display()
            QtWidgets.QApplication.processEvents()

            # wait for the sampling period.
            time.sleep(self.settings["sampling_period"])



            self.set_progress(i * 100.0 / self.settings["N"])

            # break the loop if user desires.
            if self.interrupt_measurement_called:
                break

        if self.settings["save_h5"]:
            # saves data, closes file,
            self.save_h5(data=self.data)

            # ScopeFoundry 2.1 and later
            # self.save_h5 also sets self.dataset_metadata
            # which allows to save data in other formats
            #import matplotlib.pyplot as plt

            #plt.figure()
            #plt.plot(y)
            #plt.savefig(self.dataset_metadata.get_file_path(".png"))
            #plt.close()

    def setup_figure(self):
        """
        Runs once during App initialization and is responsible
        to create widget self.ui.
        Create plots, controls widgets and buttons here.
        """
        self.ui = QtWidgets.QWidget()
        #x = self.data["x"]
        #y = self.data["y"]

        layout = QtWidgets.QVBoxLayout()
        self.ui.setLayout(layout)
        layout.addWidget(
            self.settings.New_UI(include=("sampling_period", "N", "save_h5"))
        )
        layout.addWidget(self.new_start_stop_button())
        self.graphics_widget = pg.GraphicsLayoutWidget(border=(100, 100, 100))
        self.plot = self.graphics_widget.addPlot(title=self.name)
        #self.plot_lines = {"y": self.plot.plot(pen="g")}
        self.bar_item = pg.BarGraphItem(x=[], height=[], width=1.0, brush='g')
        self.plot.addItem(self.bar_item)

        self.graphics_widget.nextRow()
        self.avg_plot = self.graphics_widget.addPlot(title="Average Pulse Shape")
        self.avg_curve = self.avg_plot.plot(pen="y")  # yellow line

        #bgi = pg.BarGraphItem(x0=x[:-1], x1=x[1:], height=y, pen='w', brush=(0,0,255,150))
        layout.addWidget(self.graphics_widget)

    def update_display(self):
        #self.plot_lines["y"].setData(self.data["y"])
        if "x" in self.data and "y" in self.data:
            x = self.data["x"]
            y = self.data["y"]
            # Use midpoints of bins for bar positions
            x_mid = 0.5 * (x[:-1] + x[1:])
            self.bar_item.setOpts(x=x_mid, height=y, width=1.0)
        if "avg_pulse" in self.data:
            self.avg_curve.setData(self.data["avg_pulse"])