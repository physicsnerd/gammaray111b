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
        s.New("sampling_period", float, initial=60, unit="s")
        s.New("buffer_size", int, initial=1000)
        s.New("sampling_freq", float, initial=1e6, unit="Hz")
        #s.New("N", int, initial=1001)
        s.New("save_h5", bool, initial=False)
        #s.New("device", str, initial="ads")
        #s.New("bin_range", int, initial=2048) #why doesn't this work properly
        #self.data = {"y": np.ones(self.settings["N"])}
        #self.data = {"y": np.ones(int(self.settings["sampling_period"]))}
        self.data = {}
    
    def run(self):
        hw = self.app.hardware["ads"]
        sampling_freq = self.settings["sampling_freq"]
        buffer_size = self.settings["buffer_size"]
        hw.open_scope(buffer_size=buffer_size, sample_freq=sampling_freq)
        buffer = hw.read_scope()
        self.data["y"] = np.array([])
        self.data["x"] = np.array([])
        loop_offset_time = 0
        loop_start_time = time.time()
        for i in range(int(self.settings["sampling_period"])):
            buffer, loop_offset_time = np.mean(hw.read_scope()), time.time() - loop_start_time
            self.data["y"] = np.append(self.data["y"], buffer)
            MS_CONVERSION = 1e3
            self.data["x"] = np.append(self.data["x"], np.array([MS_CONVERSION*(loop_offset_time + i*buffer_size/sampling_freq)]))
            if i%10 == 0:
                self.set_progress(i * 100.0 / self.settings["sampling_period"])
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
        #x = self.data["x"]
        #y = self.data["y"]

        layout = QtWidgets.QVBoxLayout()
        self.ui.setLayout(layout)
        layout.addWidget(
            self.settings.New_UI(include=("sampling_period", "sampling_wait", "save_h5"))
        )
        layout.addWidget(self.new_start_stop_button())
        self.graphics_widget = pg.GraphicsLayoutWidget(border=(100, 100, 100))
        self.plot = self.graphics_widget.addPlot(title=self.name)
        self.plot_lines = {"y": self.plot.plot(pen="g")}
        #self.bar_item = pg.BarGraphItem(x=[], height=[], width=1.0, brush='g')
        #self.plot.addItem(self.bar_item)

        #bgi = pg.BarGraphItem(x0=x[:-1], x1=x[1:], height=y, pen='w', brush=(0,0,255,150))
        layout.addWidget(self.graphics_widget)

    def update_display(self):
        self.plot_lines["y"].setData(x=self.data["x"], y=self.data["y"])
        #if "x" in self.data and "y" in self.data:
        #    x = self.data["x"]
        #    y = self.data["y"]
        #    # Use midpoints of bins for bar positions
        #    x_mid = 0.5 * (x[:-1] + x[1:])
        #    self.bar_item.setOpts(x=x_mid, height=y, width=1.0)