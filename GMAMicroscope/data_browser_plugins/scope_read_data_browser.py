import numpy as np
import h5py
import pyqtgraph as pg
from qtpy import QtWidgets
from ScopeFoundry.data_browser import DataBrowserView
import csv
import os

class ScopeReadDataBrowser(DataBrowserView):
    
    name = 'scope_read_data_browser'

    def setup(self):
        print("PulseHeightDataBrowser setup called")
        self.ui = QtWidgets.QWidget()
        main_layout = QtWidgets.QVBoxLayout(self.ui)

        # Plotting
        self.graph_layout = pg.GraphicsLayoutWidget()
        self.plot = self.graph_layout.addPlot(title="Oscilloscope Trace")
        self.plot_lines = {"y": self.plot.plot(pen="g")}
        main_layout.addWidget(self.graph_layout)

        # Horizontal layout for metadata + buttons
        lower_layout = QtWidgets.QHBoxLayout()
        main_layout.addLayout(lower_layout)

        # Metadata display
        self.metadata_box = QtWidgets.QTextEdit()
        self.metadata_box.setReadOnly(True)
        self.metadata_box.setMinimumWidth(300)
        self.metadata_box.setLineWrapMode(QtWidgets.QTextEdit.NoWrap)
        lower_layout.addWidget(self.metadata_box)

        # Export button
        button_layout = QtWidgets.QVBoxLayout()
        self.export_btn = QtWidgets.QPushButton("Export CSV")
        self.export_btn.clicked.connect(self.export_csv)
        button_layout.addWidget(self.export_btn)
        button_layout.addStretch()
        lower_layout.addLayout(button_layout)

        self.x = None
        self.y = None
        self.filepath = None

    def on_change_data_filename(self, fname=None):
        self.is_file_supported(fname)
        self.load_data(filepath=fname)

    def load_data(self, filepath):
        print(f"load_data called on {filepath}")
        print("Loading:", filepath)
        self.filepath = filepath
        self.metadata_box.clear()
        self.plot.clear()

        with h5py.File(filepath, 'r') as f:
            try:
                group = f['measurement/read_scope']
                self.y = group['y'][()]
                print("Loaded y shape:", self.y.shape)

                try:
                    self.x = group['x'][()]
                except KeyError:
                    self.x = np.arange(len(self.y) + 1)
                    print("Generated x:", self.x.shape)

                # Metadata
                if 'settings' in group:
                    meta_lines = []
                    for key, val in group['settings'].items():
                        if isinstance(val, h5py.Dataset):
                            val_str = val[()]
                            if isinstance(val_str, bytes):
                                val_str = val_str.decode()
                            meta_lines.append(f"{key}: {val_str}")
                    self.metadata_box.setPlainText("\n".join(meta_lines))
            except Exception as e:
                print("Failed to load data:", e)
                return

        if self.x is not None and self.y is not None:
            self.plot_lines["y"].setData(x=self.x, y=self.y)


    def export_csv(self):
        if self.x is None or self.y is None:
            return

        base = os.path.splitext(os.path.basename(self.filepath))[0]
        default_csv_path = os.path.join(os.path.dirname(self.filepath), base + "_scope_trace.csv")

        fname, _ = QtWidgets.QFileDialog.getSaveFileName(
            self.ui, "Save CSV", default_csv_path, "CSV files (*.csv)")

        if fname:
            x_mid = 0.5 * (self.x[:-1] + self.x[1:])
            with open(fname, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['x', 'y'])
                for xi, yi in zip(self.x, self.y):
                    writer.writerow([xi, yi])
    
    def is_file_supported(self, fname):
        print(f"Checking if file is supported: {fname}")
        try:
            with h5py.File(fname, 'r') as f:
                return 'measurement/read_scope/y' in f
        except Exception as e:
            print(f"Error in is_file_supported: {e}")
            return False