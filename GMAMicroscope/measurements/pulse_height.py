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

        split_point = buffer_size - 100   # pulse window size
        hw.open_scope(buffer_size=buffer_size, sample_freq=sampling_frequency)

        counts = np.zeros(bin_number, dtype=int)

        legit_data_points = 0
        data_points = 0
        deadtime_total = 0
        loop_deadtime_prev = time.time()

        while legit_data_points <= self.settings["N"]:
            data_points += 1
            buffer = MV_CONVERSION * hw.read_scope()

            # measure deadtime
            now = time.time()
            loop_deadtime = now - loop_deadtime_prev
            loop_deadtime_prev = now

            deadtime_total += MS_CONVERSION * (loop_deadtime + buffer_size / sampling_frequency)
            self.data["deadtime_mean"] = deadtime_total / data_points

            # --- reshape into (n_chunks, split_point) ---
            n_chunks = len(buffer) // buffer_size
            chunks = buffer[:n_chunks * split_point].reshape(n_chunks, buffer_size)

            # --- vectorized base + height ---
            base = chunks[:, 200:split_point//2].mean(axis=1)
            height = chunks[:, split_point//2:].max(axis=1)

            # --- pulse amplitudes ---
            amplitudes = height - base

            # --- filter pulses above threshold ---
            valid_amplitudes = amplitudes[np.abs(amplitudes) >= noise_threshold]

            if valid_amplitudes.size > 0:
                legit_data_points += valid_amplitudes.size

                # keep most recent pulse trace
                last_idx = np.where(np.abs(amplitudes) >= noise_threshold)[0][-1]
                self.data["recent_pulse"] = chunks[last_idx, 200:] / MV_CONVERSION

                # update histogram in one call
                hist, bins = np.histogram(valid_amplitudes, bins=bin_number, range=(0, 1))
                counts += hist

                # update display
                self.data["x"] = bins
                self.data["y"] = counts
                self.data["raw_values"] = counts.copy()
                self.update_display()

            if self.interrupt_measurement_called:
                break
            if legit_data_points % 10 == 0:
                self.set_progress(legit_data_points * 100.0 / self.settings["N"])

        hw.close_scope()

        if self.settings["save_h5"]:
            self.save_h5(data=self.data)
    
    def run(self):
        hw = self.app.hardware["ads"]
        noise_threshold = self.settings["threshold"]
        buffer_size = self.settings["buffer_size"]
        sampling_frequency = self.settings["sampling_frequency"]
        bin_number = self.settings["bin_number"]

        MS_CONVERSION = 1e3
        US_CONVERSION = 1e6
        MV_CONVERSION = 1000

        split_point = buffer_size - 100
        base_region = slice(200, int(split_point/2))
        height_region = slice(int(split_point/2), split_point)


        hw.open_scope(buffer_size=buffer_size, sample_freq=sampling_frequency)
        values = []

        legit_data_points = 0
        data_points = 0
        self.data['deadtime_mean'] = 0
        deadtime_total = 0
        loop_deadtime_prev = time.time()
        while legit_data_points <= self.settings["N"]:
            data_points += 1
            buffer, loop_deadtime, loop_deadtime_prev = MV_CONVERSION*hw.read_scope(), time.time() - loop_deadtime_prev, time.time()

            deadtime_total += MS_CONVERSION*(loop_deadtime + buffer_size/sampling_frequency)
            self.data['deadtime_mean'] = deadtime_total / data_points

            base = np.average(buffer[base_region])
            height = np.max(buffer[height_region])
            if np.abs(height-base) >= noise_threshold:
                legit_data_points += 1
                self.data["recent_pulse"] = np.array(buffer[200:split_point])/MV_CONVERSION
                values.append((height - base) * bin_number)
                counts, bins = np.histogram(values)
                self.data["x"] = bins
                self.data["y"] = counts
                self.data["raw_values"] = values

                self.update_display()

            # break the loop if user desires.
            if self.interrupt_measurement_called:
                break
            if legit_data_points % 10 == 0:
                self.set_progress(legit_data_points * 100.0 / self.settings["N"])
        #counts, bins = np.histogram(values, bins=range(bin_number))
        #self.data["x"] = bins
        #self.data["y"] = counts
        #self.update_display()
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

        # Mean display
        self.mean_label = QtWidgets.QLabel("Mean deadtime: N/A")
        self.mean_label.setAlignment(QtCore.Qt.AlignCenter)

        layout.addWidget(self.mean_label)

    def update_display(self):
        if "x" in self.data and "y" in self.data:
            x = self.data["x"]
            y = self.data["y"]
            x_mid = 0.5 * (x[:-1] + x[1:])
            self.bar_item.setOpts(x=x_mid, height=y, width=1.0)

        if "recent_pulse" in self.data:
            self.recent_curve.setData(y=self.data["recent_pulse"])

        if "deadtime_mean" in self.data:
            mean = self.data["deadtime_mean"]

            if mean >= 20:
                color = "red"
            elif mean >= 8 and mean < 20:
                color = "orange"
            else:
                color = "green"

            self.mean_label.setText(f'<span style="color:{color}">Mean deadtime: {mean:.2f} ms</span>')
