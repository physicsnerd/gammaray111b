import numpy as np
import h5py
import pyqtgraph as pg
from qtpy import QtWidgets
from ScopeFoundry.data_browser import DataBrowserView
import csv
import datetime
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
        self.plot_lines["y"].setData([])

        with h5py.File(filepath, 'r') as f:
            try:
                group = f['measurement/read_scope']
                self.y = group['y'][()]
                print("Loaded y shape:", self.y.shape)

                try:
                    self.x = group['x'][()]
                    print("Loaded x shape:", self.x.shape)
                except KeyError:
                    self.x = np.arange(len(self.y))
                    print("Generated x:", self.x.shape)

                # Metadata
                if 'settings' in group:
                    meta_lines = []

                    settings_group = group['settings']

                    # 1. Datasets inside "settings"
                    for key, ds in settings_group.items():
                        try:
                            val = ds[()]
                            if isinstance(val, (bytes, np.bytes_)):
                                val = val.decode()
                            meta_lines.append(f"{key}: {val}")
                        except Exception as e:
                            meta_lines.append(f"{key}: <unreadable> ({e})")

                    # 2. Attributes inside "settings"
                    for key, val in settings_group.attrs.items():
                        if isinstance(val, (bytes, np.bytes_)):
                            val = val.decode()
                        meta_lines.append(f"{key} (attr): {val}")

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

        print(f'saving to {fname}')

        # add provenance info
        provenance_lines = [
            f"source_file: {os.path.basename(self.filepath)}",
            f"export_timestamp: {datetime.datetime.now().isoformat(timespec='seconds')}"
        ]

        # grab metadata lines
        meta_text = self.metadata_box.toPlainText().splitlines()

        # ---- HISTOGRAM CSV WITH METADATA HEADER ----
        if fname:
            with open(fname, 'w', newline='') as f:
                writer = csv.writer(f)

                #add original filepath, datetime
                for line in provenance_lines:
                    writer.writerow([f"# {line}"])

                # write metadata as commented header
                for line in meta_text:
                    writer.writerow([f"# {line}"])
                writer.writerow([])  # blank line

                # histogram data and raw height data
                writer.writerow(['x', 'y'])
                export_data = zip(self.x, self.y)
                writer.writerows(export_data)
    
    def is_file_supported(self, fname):
        print(f"Checking if file is supported: {fname}")
        try:
            with h5py.File(fname, 'r') as f:
                return 'measurement/read_scope/y' in f
        except Exception as e:
            print(f"Error in is_file_supported: {e}")
            return False