import time
import numpy as np
import pyqtgraph as pg
from numpy.lib.stride_tricks import as_strided
from qtpy import QtCore, QtWidgets

import logging
from ScopeFoundry import Measurement, h5_io

# ---- configure logging ----
logging.basicConfig(
    level=logging.DEBUG,  # change to INFO or WARNING once stable
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


class PulseHeightAnalyze(Measurement):

    name = "pulse_height_analyzer"

    def setup(self):
        s = self.settings
        s.New("buffer_size", int, initial=1000)
        s.New("pulse_window_size", int, initial=20)
        s.New("sampling_frequency", float, initial=1e6, unit="Hz")
        s.New("threshold", float, initial=1.00, unit="V")
        s.New("bin_number", int, initial=1024)
        s.New("N", int, initial=1001)
        s.New("save_h5", bool, initial=True)
        self.data = {}
        logger.info("Setup complete with settings: %s", dict(s.as_dict()))

    def run(self):
        try:
            hw = self.app.hardware["ads"]
            noise_threshold = self.settings["threshold"]
            buffer_size = self.settings["buffer_size"]
            window_size = self.settings["pulse_window_size"]
            sampling_frequency = self.settings["sampling_frequency"]
            bin_number = self.settings["bin_number"]
            N = self.settings["N"]

            US_CONVERSION = 1e6

            logger.info("Opening scope with buffer_size=%d, sample_freq=%.2e", buffer_size, sampling_frequency)
            hw.open_scope(buffer_size=buffer_size, sample_freq=sampling_frequency)

            raw_data = np.zeros(N)
            legit_data_points = 0
            data_points = 0
            deadtime_total = 0
            loop_deadtime_prev = time.time()

            while legit_data_points <= N:
                data_points += 1
                buffer = np.array(hw.read_scope())

                if buffer is None or buffer.size == 0:
                    logger.warning("Received empty buffer at iteration %d", data_points)
                    continue

                # ---- log buffer stats ----
                buf_min = np.nanmin(buffer)
                buf_max = np.nanmax(buffer)
                buf_nan_count = np.isnan(buffer).sum()
                logger.debug(
                    "Buffer stats (iter %d): size=%d, min=%.4f, max=%.4f, NaNs=%d",
                    data_points, buffer.size, buf_min, buf_max, buf_nan_count
                )

                now = time.time()
                loop_deadtime = now - loop_deadtime_prev
                loop_deadtime_prev = now

                n_chunks = buffer.size // window_size
                if n_chunks == 0:
                    logger.warning("Buffer size %d too small for window_size %d", buffer.size, window_size)
                    continue

                try:
                    chunks = as_strided(
                        buffer,
                        shape=(n_chunks, window_size),
                        strides=(buffer.strides[0] * window_size, buffer.strides[0]),
                    )
                except Exception as e:
                    logger.exception("Error creating strided chunks: %s", e)
                    break

                deadtime_total += US_CONVERSION * (loop_deadtime + buffer.size / sampling_frequency) / n_chunks
                self.data["deadtime_mean"] = deadtime_total / data_points

                base = chunks[:, window_size // 10 : 9 * window_size // 10].min(axis=1)
                height = chunks[:, window_size // 10 : 9 * window_size // 10].max(axis=1)
                amplitudes = np.abs(height - base)

                valid_amplitudes = amplitudes[amplitudes >= noise_threshold]

                if valid_amplitudes.size > 0:
                    end_idx = legit_data_points + valid_amplitudes.size
                    if end_idx > N:
                        end_idx = N
                        logger.debug("Clipping amplitude array to fit raw_data")
                    raw_data[legit_data_points:end_idx] = valid_amplitudes[: end_idx - legit_data_points]
                    legit_data_points = end_idx

                    last_idx = np.where(np.abs(amplitudes) >= noise_threshold)[0][-1]
                    self.data["recent_pulse"] = chunks[last_idx, :]
                    logger.debug("Accepted %d valid amplitudes, total=%d", valid_amplitudes.size, legit_data_points)

                if self.interrupt_measurement_called:
                    logger.info("Measurement interrupted by user")
                    break

                if legit_data_points % 5 == 0 and legit_data_points > 1:
                    counts, bins = np.histogram(raw_data[:legit_data_points - 1], bins=bin_number)
                    self.data["x"] = bins
                    self.data["y"] = counts
                    self.update_display()
                    self.set_progress(legit_data_points * 100.0 / self.settings["N"])
                    logger.debug("Display updated at %d legit points", legit_data_points)

            hw.close_scope()
            self.data["raw_values"] = raw_data
            logger.info("Run complete with %d legit data points", legit_data_points)

            if self.settings["save_h5"]:
                self.save_h5(data=self.data)
                logger.info("Saved data to HDF5")

        except Exception as e:
            logger.exception("Fatal error in run loop: %s", e)
            raise

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

        self.mean_label = QtWidgets.QLabel("Mean deadtime: N/A")
        self.mean_label.setAlignment(QtCore.Qt.AlignCenter)
        layout.addWidget(self.mean_label)
        logger.info("UI setup complete")

    def update_display(self):
        try:
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
                elif mean >= 75:
                    color = "orange"
                else:
                    color = "green"
                self.mean_label.setText(
                    f'<span style="color:{color}">Mean deadtime: {mean:.2f} us</span>'
                )

            logger.debug("Display successfully refreshed")

        except Exception as e:
            logger.exception("Error in update_display: %s", e)
