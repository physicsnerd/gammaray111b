import numpy as np
import h5py
import pyqtgraph as pg
from qtpy import QtWidgets
from ScopeFoundry.data_browser import DataBrowserView
import csv
import datetime
import os

class PulseHeightDataBrowser(DataBrowserView):
    
    name = 'pulse_height_data_browser'
    
    def setup(self):
        print("PulseHeightDataBrowser setup called")
        self.ui = QtWidgets.QWidget()
        main_layout = QtWidgets.QVBoxLayout(self.ui)

        # Plotting
        self.graph_layout = pg.GraphicsLayoutWidget()
        self.plot = self.graph_layout.addPlot(title="Pulse Height Histogram")
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
        self.raw_data = None
        self.bin_number = None
        self.filepath = None
        self.bar_item = None
    
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
                group = f['measurement/pulse_height_analyzer']
                self.y = group['y'][()]
                print("Loaded y shape:", self.y.shape)

                try:
                    self.x = group['x'][()]
                except KeyError:
                    self.x = np.arange(len(self.y) + 1)
                    print("Generated x:", self.x.shape)
                
                self.raw_data = group['raw_values'][()]
                print("Loaded raw_data shape:", self.raw_data.shape)

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
                        if key == "bin_number":
                            self.bin_number = int(val)
                        meta_lines.append(f"{key} (attr): {val}")

                    self.metadata_box.setPlainText("\n".join(meta_lines))
            except Exception as e:
                print("Failed to load data:", e)
                return

        if self.x is not None and self.y is not None:
            x_mid = 0.5 * (self.x[:-1] + self.x[1:])
            if not self.bin_number:
                self.bin_number = 1
                print('Bin number did not load properly. Defaulting to 1.')
            bin_width = (np.max(self.x) - np.min(self.x)) / self.bin_number
            print("x_mid shape:", x_mid.shape)
            print("y shape:", self.y.shape)
            self.bar_item = pg.BarGraphItem(x=x_mid, height=self.y, width=bin_width, brush='g')
            self.plot.addItem(self.bar_item)

    def export_csv(self):
        if self.x is None or self.y is None or self.raw_data is None:
            return

        base = os.path.splitext(os.path.basename(self.filepath))[0]
        default_csv_path = os.path.join(os.path.dirname(self.filepath), base + "_histogram.csv")
        default_csv_path2 = os.path.join(os.path.dirname(self.filepath), base + "_raw_data.csv")

        fname, _ = QtWidgets.QFileDialog.getSaveFileName(
            self.ui, "Save Histogram CSV", default_csv_path, "CSV files (*.csv)")
        
        fname2, _ = QtWidgets.QFileDialog.getSaveFileName(
            self.ui, "Save Raw Data CSV", default_csv_path2, "CSV files (*.csv)"
        )

        print(f'saving to {fname} and {fname2}')

        # add provenance info
        provenance_lines = [
            f"source_file: {os.path.basename(self.filepath)}",
            f"export_timestamp: {datetime.datetime.now().isoformat(timespec='seconds')}"
        ]

        # grab metadata lines
        meta_text = self.metadata_box.toPlainText().splitlines()

        # ---- HISTOGRAM CSV WITH METADATA HEADER ----
        if fname:
            x_mid = 0.5 * (self.x[:-1] + self.x[1:])
            with open(fname, 'w', newline='') as f:
                writer = csv.writer(f)

                #add original filepath, datetime
                for line in provenance_lines:
                    writer.writerow([f"# {line}"])

                # write metadata as commented header
                for line in meta_text:
                    writer.writerow([f"# {line}"])
                writer.writerow([])  # blank line

                # histogram data
                writer.writerow(['x_mid', 'count'])
                writer.writerows(zip(x_mid, self.y))
        
        # ---- RAW DATA CSV WITH METADATA HEADER ----
        if fname2:
            with open(fname2, 'w', newline='') as f:
                writer = csv.writer(f)

                #add original filepath, datetime
                for line in provenance_lines:
                    writer.writerow([f"# {line}"])

                # write metadata as commented header
                for line in meta_text:
                    writer.writerow([f"# {line}"])
                writer.writerow([])  # blank line

                # raw data values
                writer.writerow(['pulse_height'])
                writer.writerows(self.raw_data)

    def is_file_supported(self, fname):
        print(f"Checking if file is supported: {fname}")
        try:
            with h5py.File(fname, 'r') as f:
                return 'measurement/pulse_height_analyzer/y' in f
        except Exception as e:
            print(f"Error in is_file_supported: {e}")
            return False