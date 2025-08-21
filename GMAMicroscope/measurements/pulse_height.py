import time
import numpy as np

import numpy as np
import pyqtgraph as pg
from qtpy import QtCore, QtWidgets, QtGui

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
        #s.New("device", str, initial="ads")
        #s.New("bin_range", int, initial=2048) #why doesn't this work properly
        #self.data = {"y": np.ones(self.settings["N"])}
        self.data = {}
        self.pulse_sum = None  # running sum of buffers
        self.pulse_count = 0
    
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
            print(len(buffer))
            self.data["deadtime"].append(MS_CONVERSION*(loop_deadtime + buffer_size/sampling_frequency))
            self.data["deadtime_max"] = max(self.data["deadtime"])
            self.data["deadtime_mean"] = sum(self.data["deadtime"])/len(self.data["deadtime"])
            self.data["deadtime_median"] = sorted(self.data["deadtime"])[int(len(self.data["deadtime"])/2)]
            base = np.average(buffer[200:int(split_point/2)])
            height = np.max(buffer[int(split_point/2):split_point])
            if (height-base) >= noise_threshold:
                legit_data_points += 1
                values.append(int((height - base) * bin_number))#bit_res)) CHECK THIS
                counts, bins = np.histogram(values)#, bins=range(bin_number))
                self.data["x"] = bins
                self.data["y"] = counts
                buffer = np.array(buffer, dtype=np.float64)/MV_CONVERSION

                if self.pulse_sum is None:
                    self.pulse_sum = np.zeros_like(buffer)

                self.pulse_sum += buffer[200:split_point]
                self.pulse_count += 1

                # Compute running average
                running_avg = self.pulse_sum / self.pulse_count
                #print(running_avg)

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
            self.settings.New_UI(include=("sampling_period", "N", "save_h5"))
        )
        layout.addWidget(self.new_start_stop_button())
        self.graphics_widget = pg.GraphicsLayoutWidget(border=(100, 100, 100))
        self.plot = self.graphics_widget.addPlot(title=self.name)
        self.bar_item = pg.BarGraphItem(x=[], height=[], width=1.0, brush='g')
        self.plot.addItem(self.bar_item)

        self.graphics_widget.nextRow()
        self.avg_plot = self.graphics_widget.addPlot(title="Average Pulse Shape")
        self.avg_curve = self.avg_plot.plot(pen="g")
        layout.addWidget(self.graphics_widget)

        # --- Add Deadtime Dial ---
        dial_layout = QtWidgets.QVBoxLayout()
        dial_container = QtWidgets.QWidget()
        dial_container.setLayout(dial_layout)

        # QDial widget
        self.deadtime_dial = QtWidgets.QDial()
        self.deadtime_dial.setNotchesVisible(True)
        self.deadtime_dial.setMinimum(0)
        self.deadtime_dial.setMaximum(1000)  # scale ms range, adjust as needed
        self.deadtime_dial.setEnabled(False)  # read-only look

        # Median display
        self.median_label = QtWidgets.QLabel("Median deadtime: N/A")
        self.median_label.setAlignment(QtCore.Qt.AlignCenter)

        # Style the dial with green-yellow-red background
        # (works by setting gradient in stylesheet)
        self.deadtime_dial.setStyleSheet("""
            QDial {
                background: qconicalgradient(
                    cx:0.5, cy:0.5, angle:90,
                    stop:0 green, 
                    stop:0.6 yellow, 
                    stop:1 red
                );
            }
        """)

        dial_layout.addWidget(self.deadtime_dial, alignment=QtCore.Qt.AlignCenter)
        dial_layout.addWidget(self.median_label)
        layout.addWidget(dial_container)

    def update_display(self):
        if "x" in self.data and "y" in self.data:
            x = self.data["x"]
            y = self.data["y"]
            x_mid = 0.5 * (x[:-1] + x[1:])
            self.bar_item.setOpts(x=x_mid, height=y, width=1.0)

        if "avg_pulse" in self.data:
            self.avg_curve.setData(y=self.data["avg_pulse"])

        # --- Update Dial & Median ---
        if "deadtime" in self.data and len(self.data["deadtime"]) > 0:
            latest = self.data["deadtime"][-1]
            median = self.data["deadtime_median"]

            # Map value into dial range (0–1000 ms scale here)
            dial_value = min(max(int(latest), 0), self.deadtime_dial.maximum())
            self.deadtime_dial.setValue(dial_value)

            # Update label
            self.median_label.setText(f"Median deadtime: {median:.2f} ms")