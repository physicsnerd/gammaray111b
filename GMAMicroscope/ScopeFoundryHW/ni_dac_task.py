from .ni_task_wrap import NI_TaskWrap
import PyDAQmx as mx
import numpy as np
import logging
logger = logging.getLogger(__name__)

class NI_DacTask(NI_TaskWrap):
    '''
    Digital-to-Analog output task, inherits from abstract NI_TaskWrap task
    '''
    def __init__(self, channel, name = '' ):
        ''' creates DAC task'''
        NI_TaskWrap.__init__(self, name)       
        if self.task:
            self.set_channel(channel)
            
    def set_channel(self, channel ):
        ''' adds output channel[s] to existing task, always voltage range +/- 10 no scaling'''
        self._channel = channel
        self._sample_count = 0
        try:                
            # CreateAOVoltageChan ( const char physicalChannel[], const char nameToAssignToChannel[], 
            #    float64 minVal, float64 maxVal, int32 units, const char customScaleName[]);
            self.task.CreateAOVoltageChan(self._channel, '', -10.0, +10.0, mx.DAQmx_Val_Volts, '')
            
            chan_count = mx.uInt32(0) 
            self.task.GetTaskNumChans(mx.byref(chan_count))
            self._chan_count = chan_count.value
            self._mode = 'single'   #until buffer created
        except mx.DAQError as err:
            self._chan_count = 0
            self.error(err)
            
    def set_rate(self, rate = 1e4, count = 1000, finite = True, clk_source=""):
        """
        Output buffer size determined by amount of data written, unless explicitly set by DAQmxCfgOutputBuffer()
        
        In Finite output mode, count is samples per channel to transfer on Start()
               if count > buffer size, output loops over buffer
               if count < buffer size, partial output, next start resumes from this point in buffer
        waiting for finite task to complete then restarting task has > 1 ms overhead, unclear why,
            overhead can fluctuate by 1.00 ms amounts. stupid old c clock??
        
        In Cont output mode, count is not used, output loops over buffer until stopped
            restarts at beginning of buffer
            stop/restart also has 2 ms overhead

        For unbuffered output (one sample per channel no timing or clock) with autostart enabled,
            if task STARTed BEFORE writing, in tight loop overhead between consecutive writes 18 us with some jitter
            if task is COMMITted  before writing, overhead 40 us 
                (implicit transition back to COMMIT instead of staying in RUNNING)
         """
        if finite:
            dac_mode = mx.int32(mx.DAQmx_Val_FiniteSamps)
        else:
            dac_mode = mx.int32(mx.DAQmx_Val_ContSamps)
        #  CfgSampClkTiming ( const char source[], float64 rate, int32 activeEdge, 
        #                        int32 sampleMode, uInt64 sampsPerChan );
        #  default clock source is subsystem acquisition clock
        try:                 
            dac_rate = mx.float64(rate)   #override python type
            dac_count = mx.uInt64(int(count))
            self.stop() #make sure task not running, 
            self.task.CfgSampClkTiming(clk_source, dac_rate, mx.DAQmx_Val_Rising, dac_mode, dac_count) 
            dac_rate = mx.float64(0)
            #exact rate depends on hardware timer properties, may be slightly different from requested rate
            self.task.GetSampClkRate(mx.byref(dac_rate))
            self._rate = dac_rate.value
            self._mode = 'buffered'
            
            #self.task.CfgOutputBuffer(count*30) #
            #print("set buffer size", count, "--> actual", x)
            
        except mx.DAQError as err:
            self.error(err)
            self._rate = 0
    
    def set_callback(self,source):
        self.data_buffer=np.zeros(self._count)
        self.task.EveryNCallback=self.EveryNCallback
        self.task.DoneCallback=self.DoneCallback
        self.task.AutoRegisterEveryNSamplesEvent(mx.DAQmx_Val_Transferred_From_Buffer,self._count,0)
        self.task.AutoRegisterDoneEvent(0)
        self._source=source
    
    def set_single(self):
        ''' single-value [multi channel] output, no clock or buffer
        
        For unbuffered output (one sample per channel no timing or clock) with autostart enabled,
            if task STARTed BEFORE writing, in tight loop overhead between consecutive writes 21 us with some jitter
                (no implicit mode transition)
            if task is COMMITted  before writing, overhead 40 us 
                (implicit transition back to COMMIT instead of staying in RUNNING)
            if task stopped, autostart takes ~ 5 ms per write
                (implicit start stop)
                
        No clean way to change from buffered to single point output without creating new task
         '''
        if self._mode != 'single':
            self.clear()    #delete old task
            self.make_task(self._task_name)
            self.set_channel(self._channel)
            self._mode = 'single'
              
    def load_buffer(self, data, auto = False, timeout=0 ):
        '''  writes data to output buffer, array-like objects converted to np arrays if required
            data is interleved, i.e. x1, y1, x2, y2, x3, y3... for output on x and y
            implicitly COMMITs task, also starts if autostart is True
        '''
        if not isinstance( data, np.ndarray ) or data.dtype != np.float64:
            data = np.asarray(data, dtype = np.float64 )
        dac_samples = mx.int32( int(len(data) / self._chan_count) )
        self._sample_count = dac_samples.value
        writeCount = mx.int32(0)
        if auto:
            auto_start = mx.bool32(1)
        else:
            auto_start = mx.bool32(0)       
        try:
            #  WriteAnalogF64 (int32 numSampsPerChan, bool32 autoStart, float64 timeout, 
            #    bool32 dataLayout, float64 writeArray[], int32 *sampsPerChanWritten, bool32 *reserved)
            #self.task.SetWriteRelativeTo(mx.DAQmx_Val_FirstSample)
            self.task.WriteAnalogF64(dac_samples, auto_start, timeout, mx.DAQmx_Val_GroupByScanNumber, 
                                  data, mx.byref(writeCount), None)
        except mx.DAQError as err:
            #print("sample load count {} transfer count {}".format( self._sample_count, writeCount.value ))
            self.error(err)
        #print "samples {} written {}".format( self._sample_count, writeCount.value)
        if writeCount.value != self._sample_count:
            "sample load count {} transfer count {}".format( self._sample_count, writeCount.value )

    def set(self, data):
        ''' writes one sample per channel in immediate (non buffered) mode, fastest if task pre-started'''
        if not isinstance( data, np.ndarray ) or data.dtype != np.float64:
            data = np.asarray(data, dtype = np.float64 )
        if self._mode != 'single':
            self.set_single()
            self.start()
        writeCount = mx.int32(0)
        auto_start = mx.bool32(1)
        try:
            #  WriteAnalogF64 (int32 numSampsPerChan, bool32 autoStart, float64 timeout, 
            #    bool32 dataLayout, float64 writeArray[], int32 *sampsPerChanWritten, bool32 *reserved)
            self.task.WriteAnalogF64(1, auto_start, 1.0, mx.DAQmx_Val_GroupByChannel, 
                                  data, mx.byref(writeCount), None)
        except mx.DAQError as err:
            self.error(err)
#        print "samples {} written {}".format( self._sample_count, writeCount.value)
        assert writeCount.value == 1, \
            "sample count {} transfer count {}".format( 1, writeCount.value )

#     def EveryNCallback(self):
#         #np.copyto(self.data_buffer,self._source,None)
#         self.load_buffer(self.data_buffer)
#         return 0 # The function should return an integer
#     
#     def DoneCallback(self, status):
#         #print "Status",status.value
#         return 0 # The function should return an integer


    def set_n_sample_callback(self, n_samples, cb_func):
        """
        Setup callback functions for EveryNSamplesEvent
        *cb_func* will be called with when new output data is needed
        after every *n_samples* are output.
        """
        self.cb_nSamples = n_samples
        self.cb_func = cb_func
        self.task.EveryNCallback = cb_func
        self.task.AutoRegisterEveryNSamplesEvent(
            everyNsamplesEventType=mx.DAQmx_Val_Transferred_From_Buffer, 
            nSamples=self.cb_nSamples,
            options=0)