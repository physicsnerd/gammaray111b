import sys
from ScopeFoundry import BaseMicroscopeApp


class FancyApp(BaseMicroscopeApp):

    name = "GMA"

    def setup(self):

        #from ScopeFoundryHW.NIDAQ import NIDAQHardware
        #self.add_hardware(NIDAQHardware(self))

        from ScopeFoundryHW.ADS import ADSHardware
        self.add_hardware(ADSHardware(self))

        from measurements.pulse_height import PulseHeightAnalyze
        self.add_measurement(PulseHeightAnalyze(self))

        from measurements.scope_read import ScopeRead
        self.add_measurement(ScopeRead(self))

if __name__ == "__main__":
    app = FancyApp(sys.argv)
    app.settings_load_ini("default_settings.ini")
    sys.exit(app.exec_())
