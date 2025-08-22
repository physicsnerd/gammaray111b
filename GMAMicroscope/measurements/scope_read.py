import time

import numpy as np
import pyqtgraph as pg
from qtpy import QtCore, QtWidgets

from ScopeFoundry import Measurement, h5_io

class ScopeRead(Measurement):
    
    name = "read_scope"

    def setup(self):
        """
        Runs once during app initialization.
        This is where you define your settings and set up data structures.
        """

        s = self.settings
        s.New("buffer_size", int, initial=1000)
        s.New("sampling_freq", float, initial=1e6, unit="Hz")
        s.New("N", int, initial=1001)
        s.New("save_h5", bool, initial=False)
        self.data = {}
    
    def run(self):
        hw = self.app.hardware["ads"]
        sampling_freq = self.settings["sampling_freq"]
        buffer_size = self.settings["buffer_size"]
        N = self.settings["N"]

        MS_CONVERSION = 1e3
        US_CONVERSION = 1e6

        hw.open_scope(buffer_size=buffer_size, sample_freq=sampling_freq)

        total_points = N * buffer_size
        self.data["y"] = np.zeros(total_points)
        self.data["x"] = np.zeros(total_points)

        #loop_offset_time = 0
        loop_start = time.time()
        for i in range(int(self.settings["N"])):
            buffer, loop_deadtime = hw.read_scope(), time.time() - loop_start
            print(max(abs(buffer)))
            start = i * buffer_size
            end = start + buffer_size
            self.data["y"][start:end] = buffer
            self.data["x"][start:end] = US_CONVERSION*(loop_deadtime + np.arange(buffer_size)/sampling_freq)
            #self.data["deadtime_mean"] = MS_CONVERSION * loop_deadtime / (i+1)

            if i%10 == 0:
                self.set_progress(i * 100.0 / self.settings["N"])
            self.update_display()
            if self.interrupt_measurement_called:
                break

        hw.close_scope()
        if self.settings["save_h5"]:
            # saves data, closes file,
            self.save_h5(data=self.data)
    
    def setup_figure(self):
        """
        Runs once during App initialization and is responsible
        to create widget self.ui.
        Create plots, controls widgets and buttons here.
        """
        self.ui = QtWidgets.QWidget()

        layout = QtWidgets.QVBoxLayout()
        self.ui.setLayout(layout)
        layout.addWidget(
            self.settings.New_UI(include=("sampling_period", "sampling_wait", "save_h5"))
        )
        layout.addWidget(self.new_start_stop_button())
        self.graphics_widget = pg.GraphicsLayoutWidget(border=(100, 100, 100))
        self.plot = self.graphics_widget.addPlot(title=self.name)
        self.plot_lines = {"y": self.plot.plot(pen="g")}

        layout.addWidget(self.graphics_widget)

        # Mean display
        #self.mean_label = QtWidgets.QLabel("Mean deadtime: N/A")
        #self.mean_label.setAlignment(QtCore.Qt.AlignCenter)

        #layout.addWidget(self.mean_label)

    def update_display(self):
        if "x" in self.data and "y" in self.data:
            self.plot_lines["y"].setData(x=self.data["x"], y=self.data["y"])
        #if "deadtime_mean" in self.data:
        #    mean = self.data["deadtime_mean"]

        #    if mean >= 20:
        #        color = "red"
        #    elif mean >= 8 and mean < 20:
        #        color = "orange"
        #    else:
        #        color = "green"

        #    self.mean_label.setText(f'<span style="color:{color}">Mean deadtime: {mean:.2f} ms</span>')