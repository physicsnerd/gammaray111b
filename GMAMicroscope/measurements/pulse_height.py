import time
import numpy as np

import numpy as np
import pyqtgraph as pg
from qtpy import QtCore, QtWidgets, QtGui

from ScopeFoundry import Measurement, h5_io

class GaugeWidget(QtWidgets.QWidget):
    def __init__(self, minimum=0, maximum=1000, parent=None):
        super().__init__(parent)
        self._min = minimum
        self._max = maximum
        self._value = 0
        self.setMinimumSize(200, 200)

    def setRange(self, minimum, maximum):
        self._min = minimum
        self._max = maximum
        self.update()

    def setValue(self, value):
        self._value = max(self._min, min(self._max, value))
        self.update()

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)

        rect = self.rect().adjusted(10, 10, -10, -10)
        center = rect.center()
        radius = min(rect.width(), rect.height()) / 2

        # --- Draw colored arcs ---
        pen = QtGui.QPen()
        pen.setWidth(15)

        # Green arc (low deadtime: 0–300)
        pen.setColor(QtGui.QColor("green"))
        painter.setPen(pen)
        painter.drawArc(rect, 225*16, -108*16)  # 0–300 ms segment

        # Yellow arc (medium: 300–700)
        pen.setColor(QtGui.QColor("yellow"))
        painter.setPen(pen)
        painter.drawArc(rect, 117*16, -144*16)  # 300–700 ms segment

        # Red arc (high: 700–1000)
        pen.setColor(QtGui.QColor("red"))
        painter.setPen(pen)
        painter.drawArc(rect, -27*16, -108*16)  # 700–1000 ms segment

        # --- Draw needle ---
        angle_span = 270  # dial spans 270°
        start_angle = 225
        norm = (self._value - self._min) / (self._max - self._min)
        angle = start_angle - norm * angle_span

        painter.setPen(QtCore.Qt.NoPen)
        painter.setBrush(QtGui.QColor("black"))
        needle_length = radius * 0.75
        needle = QtCore.QLineF.fromPolar(needle_length, angle)
        needle.translate(center)
        painter.drawLine(center, needle.p2())

        # --- Draw labels ---
        painter.setPen(QtGui.QPen(QtCore.Qt.black))
        font = painter.font()
        font.setPointSize(10)
        painter.setFont(font)

        # Min label
        painter.drawText(
            rect.adjusted(0, radius * 0.4, 0, 0),
            QtCore.Qt.AlignLeft | QtCore.Qt.AlignBottom,
            f"{self._min} ms",
        )

        # Mid label
        painter.drawText(
            rect,
            QtCore.Qt.AlignHCenter | QtCore.Qt.AlignBottom,
            f"{(self._min + self._max) // 2} ms",
        )

        # Max label
        painter.drawText(
            rect.adjusted(0, radius * 0.4, 0, 0),
            QtCore.Qt.AlignRight | QtCore.Qt.AlignBottom,
            f"{self._max} ms",
        )

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
            self.data["deadtime"].append(MS_CONVERSION*(loop_deadtime + buffer_size/sampling_frequency))
            #self.data["deadtime_max"] = max(self.data["deadtime"])
            #self.data["deadtime_mean"] = sum(self.data["deadtime"])/len(self.data["deadtime"])
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
                    self.pulse_sum = np.zeros_like(buffer[200:split_point])

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

        self.deadtime_gauge = GaugeWidget(minimum=0, maximum=1000)
        dial_layout.addWidget(self.deadtime_gauge, alignment=QtCore.Qt.AlignCenter)

        # Median display
        self.median_label = QtWidgets.QLabel("Median deadtime: N/A")
        self.median_label.setAlignment(QtCore.Qt.AlignCenter)
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

            dial_value = min(max(int(latest), self.deadtime_gauge._min), self.deadtime_gauge._max)
            self.deadtime_gauge.setValue(dial_value)

            self.median_label.setText(f"Median deadtime: {median:.2f} ms")