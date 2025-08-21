import time
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
        s.New("buffer_size", int, initial=1000)
        s.New("sampling_frequency", float, initial=1e6, unit="Hz")
        s.New("threshold", float, initial=1.0, unit="mV")
        s.New("bin_number", int, initial=1024)
        s.New("N", int, initial=1001)
        s.New("save_h5", bool, initial=True)
        #self.data = {"y": np.ones(self.settings["N"])}
        self.data = {}
    
    def run(self):
        hw = self.app.hardware["ads"]
        noise_threshold = self.settings["threshold"]
        buffer_size = self.settings["buffer_size"]
        sampling_frequency = self.settings["sampling_frequency"]
        bin_number = self.settings["bin_number"]

        MS_CONVERSION = 1e3
        MV_CONVERSION = 1000

        split_point = buffer_size - 100

        hw.open_scope(buffer_size=buffer_size, sample_freq=sampling_frequency)
        #bit_res = 1024 HM CHECK THIS
        values = []

        legit_data_points = 0
        self.data['deadtime'] = []
        loop_deadtime_prev = time.time()
        while legit_data_points <= self.settings["N"]:
            buffer, loop_deadtime, loop_deadtime_prev = MV_CONVERSION*hw.read_scope(), time.time() - loop_deadtime_prev, time.time()

            self.data["deadtime"].append(MS_CONVERSION*(loop_deadtime + buffer_size/sampling_frequency))
            self.data["deadtime_median"] = sorted(self.data["deadtime"])[int(len(self.data["deadtime"])/2)]

            base = np.average(buffer[200:int(split_point/2)])
            height = np.max(buffer[int(split_point/2):split_point])
            if (height-base) >= noise_threshold:
                legit_data_points += 1
                self.data["recent_pulse"] = np.array(buffer[200:split_point])/MV_CONVERSION
                values.append(int((height - base) * bin_number))#bit_res)) CHECK THIS
                counts, bins = np.histogram(values)#, bins=range(bin_number))
                self.data["x"] = bins
                self.data["y"] = counts

                self.update_display()

                # break the loop if user desires.
                if self.interrupt_measurement_called:
                    break
            if legit_data_points % 10 == 0:
                    self.set_progress(legit_data_points * 100.0 / self.settings["N"])
        counts, bins = np.histogram(values, bins=range(bin_number))
        self.data["x"] = bins
        self.data["y"] = counts
        self.update_display()
        hw.close_scope()

        if self.settings["save_h5"]:
            # saves data, closes file
            self.save_h5(data=self.data)

    def setup_figure(self):
        self.ui = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout()
        self.ui.setLayout(layout)

        layout.addWidget(
            self.settings.New_UI(include=("threshold", "N", "bin_number", "save_h5"))
        )
        layout.addWidget(self.new_start_stop_button())
        self.graphics_widget = pg.GraphicsLayoutWidget(border=(100, 100, 100))
        self.plot = self.graphics_widget.addPlot(title=self.name)
        self.bar_item = pg.BarGraphItem(x=[], height=[], width=1.0, brush='g')
        self.plot.addItem(self.bar_item)

        self.graphics_widget.nextRow()
        self.recent_plot = self.graphics_widget.addPlot(title="Most Recent Pulse Shape")
        self.recent_curve = self.recent_plot.plot(pen="g")
        layout.addWidget(self.graphics_widget)

        # Median display
        self.median_label = QtWidgets.QLabel("Median deadtime: N/A")
        self.median_label.setAlignment(QtCore.Qt.AlignCenter)

        layout.addWidget(self.median_label)

    def update_display(self):
        if "x" in self.data and "y" in self.data:
            x = self.data["x"]
            y = self.data["y"]
            x_mid = 0.5 * (x[:-1] + x[1:])
            self.bar_item.setOpts(x=x_mid, height=y, width=1.0)

        if "recent_pulse" in self.data:
            self.recent_curve.setData(y=self.data["recent_pulse"])

        if "deadtime" in self.data and len(self.data["deadtime"]) > 0:
            median = self.data["deadtime_median"]

            if median >= 20:
                color = "red"
            elif median >= 10 and median < 20:
                color = "yellow"
            else:
                color = "green"

            self.median_label.setText(f'<span style="color:{color}">Median deadtime: {median:.2f} ms</span>')
