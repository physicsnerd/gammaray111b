import time
import numpy as np
import pyqtgraph as pg
from numpy.lib.stride_tricks import as_strided
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
        s.New("pulse_window_size", int, initial=20)
        s.New("sampling_frequency", float, initial=1e6, unit="Hz")
        s.New("threshold", float, initial=1.00, unit="V")
        s.New("bin_number", int, initial=1024)
        s.New("N", int, initial=1001)
        s.New("save_h5", bool, initial=True)
        #self.data = {"y": np.ones(self.settings["N"])}
        self.data = {}

    def run(self):
        hw = self.app.hardware["ads"]
        noise_threshold = self.settings["threshold"]
        buffer_size = self.settings["buffer_size"]
        window_size = self.settings["pulse_window_size"]
        sampling_frequency = self.settings["sampling_frequency"]
        bin_number = self.settings["bin_number"]
        N = self.settings["N"]

        US_CONVERSION = 1e6
        MV_CONVERSION = 1000

        #actually will have buffer size of buffer_size*1000 oops
        hw.open_scope(buffer_size=buffer_size, sample_freq=sampling_frequency)

        raw_data = np.zeros(N)

        legit_data_points = 0
        data_points = 0
        deadtime_total = 0
        loop_deadtime_prev = time.time()

        while legit_data_points <= N:
            data_points += 1
            buffer = np.array(hw.read_scope())

            # measure deadtime
            now = time.time()
            loop_deadtime = now - loop_deadtime_prev
            loop_deadtime_prev = now

            # --- reshape into (n_chunks, split_point) ---
            n_chunks = buffer.size // window_size
            #chunks = buffer[:n_chunks * window_size].reshape(n_chunks, window_size)
            chunks = as_strided(buffer, shape=(n_chunks, window_size),
                    strides=(buffer.strides[0]*window_size, buffer.strides[0]))

            deadtime_total += US_CONVERSION * (loop_deadtime + buffer.size / sampling_frequency) / n_chunks
            self.data["deadtime_mean"] = deadtime_total / data_points

            # --- vectorized base + height ---
            base = chunks[:, window_size//10:9*window_size//10].min(axis=1)#remove indexing on these two?
            height = chunks[:, window_size//10:9*window_size//10].max(axis=1)

            # --- pulse amplitudes ---
            amplitudes = np.abs(height - base)

            # --- filter pulses above threshold ---
            valid_amplitudes = amplitudes[amplitudes >= noise_threshold]

            if valid_amplitudes.size > 0:
                raw_data[legit_data_points:legit_data_points + valid_amplitudes.size] = valid_amplitudes
                legit_data_points += valid_amplitudes.size

                # keep most recent pulse trace
                last_idx = np.where(np.abs(amplitudes) >= noise_threshold)[0][-1]
                self.data["recent_pulse"] = chunks[last_idx, :]

            if self.interrupt_measurement_called:
                break

            if legit_data_points % 5 == 0 and legit_data_points > 1:
                counts, bins = np.histogram(raw_data[:legit_data_points - 1], bins=bin_number)
                self.data["x"] = bins
                self.data["y"] = counts
                self.update_display()
                self.set_progress(legit_data_points * 100.0 / self.settings["N"])

        hw.close_scope()
        self.data["raw_values"] = raw_data

        if self.settings["save_h5"]:
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
            bin_width = (np.max(x) - np.min(x)) / self.settings["bin_number"]
            self.bar_item.setOpts(x=x_mid, height=y, width=bin_width)

        if "recent_pulse" in self.data:
            self.recent_curve.setData(y=self.data["recent_pulse"])

        if "deadtime_mean" in self.data:
            mean = self.data["deadtime_mean"]

            if mean >= 100:
                color = "red"
            elif mean >= 75 and mean < 100:
                color = "orange"
            else:
                color = "green"

            self.mean_label.setText(f'<span style="color:{color}">Mean deadtime: {mean:.2f} us</span>')
