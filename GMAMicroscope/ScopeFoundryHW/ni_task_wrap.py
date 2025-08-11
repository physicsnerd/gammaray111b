import PyDAQmx as mx
import logging
logger = logging.getLogger(__name__)

class NamedTask(mx.Task):
    ''' replaces __init__ with one that accepts a name for the task, otherwise identical to PyDaqmx task
        override PyDAQmx definition, which does not support named tasks
        no special chars in names, space OK
    '''
    def __init__(self, name= ''):
        self.taskHandle = mx.TaskHandle(0)
        mx.DAQmxCreateTask(name, mx.byref(self.taskHandle))

class NI_TaskWrap(object):
    '''
    class to wrap National Instruments tasks using DAQmx drivers
    '''
    def __init__(self, name = '' ):
        '''
        Constructor
        '''
        self._error_list = []
        self._channel = self._task_name = self._mode = ''
        self._chan_count = self._rate = 0
        self.make_task( name )
    
    def make_task(self, name = '' ):
        ''' creates a [named] task, should not fail if DAQmx present'''
        # clean up name to remove unallowed characters (might be missing some)
        for char in '/,;':
            name = name.replace(char, "_")
        print("make_task", name)
        self._task_name = name
        try:
            self.task = NamedTask(name)        
        except mx.DAQError as err:
            self.error( err )
            self.task = None               
        
    def error(self, err ):
            self._error_list.append(err)
            logger.error('Error calling "{}": {}'.format( err.fname, err.mess ))

    def stop(self):
        try:
            self.task.StopTask()
        except mx.DAQError as err:
            self.error(err)
        
    def start(self):
        try:
            self.task.StartTask()
        except mx.DAQError as err:
            self.error(err)
    
    def clear(self):
        try:
            self.task.ClearTask()
        except mx.DAQError as err:
            self.error(err)
        finally:
            self.task = None
            
    def close(self):
        return self.clear()
    
    def unreserve(self):
        ''' releases resources for other tasks to use without destroying task'''
        try:
            self.task.TaskControl(mx.DAQmx_Val_Task_Unreserve)
        except mx.DAQError as err:
            self.error(err)
            
    def ready(self):
        ''' validates params, reserves resources, ready to start'''
        try:
            self.task.TaskControl(mx.DAQmx_Val_Task_Commit)
        except mx.DAQError as err:
            self.error(err)
        
    def is_done(self):
        ''' checks for task done'''
        status = mx.bool32(0)
        try:
            self.task.GetTaskComplete( mx.byref(status))
        except mx.DAQError as err:
            self.error(err)
        if status.value:
            return True
        else:
            return False
        
    def get_rate(self):
        return self._rate
    
    def get_chan_count(self):
        return self._chan_count
    
    def wait(self, timeout = 10.0 ):
        try:
            self.task.WaitUntilTaskDone( timeout)
        except mx.DAQError as err:
            self.error(err)        
    
    def get_devices(self):
        '''
        polls for installed NI devices
        '''
        buffSize = 2048
        buff = mx.create_string_buffer( buffSize )
        try:
            mx.DAQmxGetSysDevNames( buff, buffSize )
        except mx.DAQError as err:
            self.error( err )
        dev_list = buff.value.split(',')
        for i in range(len(dev_list)):
            dev_list[i] = dev_list[i].strip()
        self._device_list = dev_list       
        #mx.DAQmxGetDevAIPhysicalChans( AIdev, chanList, buffSize )