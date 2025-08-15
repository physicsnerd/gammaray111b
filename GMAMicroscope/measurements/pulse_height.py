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
        #s.New("sampling_period", float, initial=0.01, unit="s")
        s.New("buffer_size", int, initial=1000)
        s.New("sampling_frequency", float, initial=1e6, unit="Hz")
        s.New("threshold", float, initial=1.0, unit="mV")
        s.New("bin_number", int, initial=1024)
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
        buffer_size = self.settings["buffer_size"]
        sampling_frequency = self.settings["sampling_frequency"]
        bin_number = self.settings["bin_number"]

        MS_CONVERSION = 1e3
        MV_CONVERSION = 1000

        hw.open_scope()
        #bit_res = 1024 HM CHECK THIS
        values = []

        legit_data_points = 0
        self.data['deadtime'] = []
        loop_deadtime_prev = time.time()
        while legit_data_points <= self.settings["N"]:
            buffer, loop_deadtime, loop_deadtime_prev = MV_CONVERSION*hw.read_scope(), time.time() - loop_deadtime_prev, time.time()
            self.data["deadtime"].append(MS_CONVERSION*(loop_deadtime + buffer_size/sampling_frequency))
            self.data["deadtime_max"] = max(self.data["deadtime"])
            self.data["deadtime_mean"] = sum(self.data["deadtime"])/len(self.data["deadtime"])
            base = np.average(buffer[200:400])
            height = np.max(buffer[400:900])
            if (height-base) >= noise_threshold:
                legit_data_points += 1
                values.append(int((height - base) * bin_number))#bit_res)) CHECK THIS
                counts, bins = np.histogram(values, bins=range(bin_number))
                self.data["x"] = bins
                self.data["y"] = counts
                buffer = np.array(buffer, dtype=np.float64)/MV_CONVERSION

                if self.pulse_sum is None:
                    self.pulse_sum = np.zeros_like(buffer)

                self.pulse_sum += buffer
                self.pulse_count += 1

                # Compute running average
                running_avg = self.pulse_sum / self.pulse_count
                print(running_avg)

                # Store for plotting
                self.data["avg_pulse"] = running_avg
                #self.data["avg_pulse_x"] = np.array(range(self.data["avg_pulse"].size))
                #print(self.data["avg_pulse"].size, MS_CONVERSION*buffer_size/sampling_frequency)
                self.update_display()

                # break the loop if user desires.
                if self.interrupt_measurement_called:
                    break
            if legit_data_points % 10 == 0:
                    self.set_progress(legit_data_points * 100.0 / self.settings["N"])
        hw.close_scope()

        if self.settings["save_h5"]:
            # saves data, closes file
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
            self.avg_curve.setData(y=self.data["avg_pulse"])
            #self.avg_curve.setData(x=self.data["avg_pulse_x"], y=self.data["avg_pulse"])