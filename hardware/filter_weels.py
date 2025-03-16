from .common import Device
from PyQt5.QtCore import pyqtSignal, pyqtSlot
from PyQt5.QtCore import QThread

############################################################################### Dummy

class DummyFilterWheel(Device):
    
    ################################################################### Signals
    
    done = pyqtSignal(str)
    
    ############################################################# CTOR and DTOR
    
    def __init__(self,dev_name:str):
        super().__init__(dev_name,'FilterWheel','Thorslab','FW')
        
        self.num_pos = 6
        self.pos     = 0
        
    def free(self):
        super().free()

    ################################################################## Position

    @pyqtSlot(int)
    def set_position(self,pos:int):
        self.num_pos = min(max(pos,0),self.num_pos)
        print(f'[{self.thread_id}] {self.full_name}: set_position({pos})')
        
    def get_position(self) -> int:
        print(f'[{self.thread_id}] {self.full_name}: get_position()')
        return self.pos

############################################################################### Dummy

from microscope.filterwheels.thorlabs import ThorlabsFilterWheel as _thorlabss

class FilterWheel(QThread):
    
    ################################################################### Signals
    
    done = pyqtSignal(str)
    
    ############################################################# CTOR and DTOR
    
    def __init__(self,dev_name:str,com_port:str='COM8'):
        super().__init__(dev_name,'FilterWheel','Thorslab','FW')
        self.filterwheel = _thorlabss('COM8')
        
        self.num_pos = 6
        self.get_position()
        
    def free(self):
        self.filterwheel.disable()
        super().free()

    ################################################################## Position

    @pyqtSlot(int)
    def set_position(self,pos:int):
        self.num_pos = min(max(pos,0),self.num_pos)
        self.filterwheel.position = self.num_pos
        
    def get_position(self) -> int:
        self.num_pos = self.filterwheel.position
        return self.num_pos

    







