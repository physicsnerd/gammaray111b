from ScopeFoundry import HardwareComponent
from WF_SDK import device
from WF_SDK import scope
from WF_SDK import wavegen
from WF_SDK import supplies
from WF_SDK import dmm
from WF_SDK import logic
from WF_SDK import pattern
from WF_SDK import static
from WF_SDK import protocol
from WF_SDK.protocol import i2c
from WF_SDK.protocol import spi
from WF_SDK.protocol import uart

class ADSHardware(HardwareComponent):

    def setup(self):
        self.name = 'ads'
        #self.settings.New('channel', dtype=str, initial='/Dev2/ao0')
        self.handle = device.open()
    
    def connect(self):
        # this is the device handle - it will be used by all functions to "address" the connected device
        self.handle = device.open()
    
    def open_scope(self, buffer_size=1000, sample_freq=100e6):
        scope.open(self.handle, buffer_size=buffer_size, sampling_frequency=sample_freq)
        #buffer = scope.record(self.handle, channel=channel)
        #time.sleep(wait)
        #scope.close(self.handle)
        #return buffer
        return
    
    def trigger_scope(self, channel=1, level=0.1):
        scope.trigger(self.handle, enable=True, source=scope.trigger_source.analog, channel=channel, edge_rising=True, level=level)
        return
    
    def read_scope(self, channel=1):
        buffer = scope.record(self.handle, channel=channel)
        return buffer
    
    def close_scope(self):
        scope.close(self.handle)
        return
    
    def use_wavegen(self, channel=1, function=wavegen.function.sine, offset=0, freq=10e3, amp=1):
        wavegen.generate(self.handle, channel=channel, function=function, offset=offset, frequency=freq, amplitude=amp)
        return

    def close_wavegen(self):
        wavegen.close(self.handle)
        return
   
    def disconnect(self):
        device.close(self.handle)
