import sys
from ScopeFoundry.data_browser import DataBrowser
from ScopeFoundry.data_browser.plug_ins.h5_search import H5SearchPlugIn
from ScopeFoundry.data_browser.plug_ins.time_note import TimeNote
from ScopeFoundry.data_browser.viewers import H5TreeView, RangedOptimizationH5View
from ScopeFoundry.helper_funcs import sibling_path

#from data_browser_plugins import pulse_height_data_browser
from data_browser_plugins.pulse_height_data_browser import PulseHeightDataBrowser
from data_browser_plugins.scope_read_data_browser import ScopeReadDataBrowser

class MyDataBrowser(DataBrowser):
    def setup(self):
        self.add_plugin(H5SearchPlugIn(self))
        #self.add_plugin(TimeNote(self))

        #from data_browser_plugins.pulse_height_data_browser import PulseHeightDataBrowser
        self.add_view(PulseHeightDataBrowser(self))
        self.add_view(ScopeReadDataBrowser(self))

        self.add_view(H5TreeView(self))
        #self.add_view(RangedOptimizationH5View(self))

if __name__ == "__main__":
    app = MyDataBrowser(sys.argv)
    sys.exit(app.exec_())