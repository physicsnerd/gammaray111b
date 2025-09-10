import sys
import os
import numpy as np
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QPushButton, QFileDialog,
    QSpinBox, QDoubleSpinBox, QLabel, QHBoxLayout
)
from PyQt5.QtCore import QTimer
import matplotlib
matplotlib.use("Qt5Agg")
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure


class LiveHistogram(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Live Histogram Viewer")
        self.filepath = None
        self.file = None
        self.file_position = 0
        self.data = []

        # Layout
        layout = QVBoxLayout()

        # File selector
        self.file_btn = QPushButton("Select File")
        self.file_btn.clicked.connect(self.select_file)
        layout.addWidget(self.file_btn)

        # Controls for bins, min, max
        controls = QHBoxLayout()
        self.bin_label = QLabel("Bins:")
        self.bin_input = QSpinBox()
        self.bin_input.setRange(1, 10000)
        self.bin_input.setValue(1024)

        self.min_label = QLabel("Min:")
        self.min_input = QDoubleSpinBox()
        self.min_input.setRange(-1e9, 1e9)
        self.min_input.setValue(1.0)

        self.max_label = QLabel("Max:")
        self.max_input = QDoubleSpinBox()
        self.max_input.setRange(-1e9, 1e9)
        self.max_input.setValue(5.0)

        controls.addWidget(self.bin_label)
        controls.addWidget(self.bin_input)
        controls.addWidget(self.min_label)
        controls.addWidget(self.min_input)
        controls.addWidget(self.max_label)
        controls.addWidget(self.max_input)
        layout.addLayout(controls)

        # Reset button
        self.reset_btn = QPushButton("Reset Data")
        self.reset_btn.clicked.connect(self.reset_data)
        layout.addWidget(self.reset_btn)

        # Point count label
        self.count_label = QLabel("N points: 0")
        layout.addWidget(self.count_label)

        # Matplotlib figure
        self.figure = Figure()
        self.canvas = FigureCanvas(self.figure)
        layout.addWidget(self.canvas)

        self.setLayout(layout)

        # Timer for live update
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_plot)
        self.timer.start(1000)  # update every second

    def select_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Data File", "", "All Files (*)")
        if path:
            self.filepath = path
            if self.file:
                self.file.close()
            self.file = open(self.filepath, "r")
            self.file_position = 0
            self.data = []
            self.update_count_label()

    def reset_data(self):
        """Clear stored data and reset histogram."""
        self.data = []
        self.file_position = self.file.tell() if self.file else 0
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        ax.set_title("Live Histogram (reset)")
        ax.set_xlabel("Value")
        ax.set_ylabel("Frequency")
        self.canvas.draw()
        self.update_count_label()
    
    def update_count_label(self):
        self.count_label.setText(f"N points: {len(self.data)}")

    def update_plot(self):
        if not self.file:
            return

        try:
            # Seek to last read position
            self.file.seek(self.file_position)
            new_lines = self.file.readlines()
            self.file_position = self.file.tell()

            # Convert new lines to floats
            new_data = []
            for line in new_lines:
                try:
                    new_data.append(float(line.strip()))
                except ValueError:
                    continue  # skip bad lines

            if new_data:
                self.data.extend(new_data)
                self.update_count_label()

        except Exception as e:
            print(f"Error reading file: {e}")
            return

        if not self.data:
            return

        bins = self.bin_input.value()
        vmin = self.min_input.value()
        vmax = self.max_input.value()

        self.figure.clear()
        ax = self.figure.add_subplot(111)
        ax.hist(self.data, bins=bins, range=(vmin, vmax),
                color="blue", edgecolor="blue")
        ax.set_title("Pulse Height Analyzer")
        ax.set_xlabel("Voltage (V)")
        ax.set_ylabel("Counts")
        self.canvas.draw()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = LiveHistogram()
    window.resize(800, 600)
    window.show()
    sys.exit(app.exec_())