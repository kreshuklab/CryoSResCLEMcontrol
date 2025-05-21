from .common import Device
from PyQt5.QtCore import pyqtSignal, pyqtSlot
import numpy as np

from PyQt5.QtCore import QThread

############################################################################### Dummy

class DummyLaser(Device):
    
    ################################################################### Signals
    
    done = pyqtSignal(str)
    
    ############################################################# CTOR and DTOR
    
    def __init__(self,dev_name:str):
        super().__init__(dev_name,'Laser','Dummy','StdIO')
        
        self.power_status = False

        self.power_ratio       = 0.0
        self.power_ratio_range = (0.0,1.0)
        
    def free(self):
        self.set_power_ratio (None,0.0)
        self.set_power_status(None,False)
        super().free()

    ############################################################### Power Ratio

    @pyqtSlot(int,float)
    def set_power_ratio(self,_subdevice_id:int,ratio:float):
        self.power_ratio = min(max(ratio,self.power_ratio_range[0]),self.power_ratio_range[1])
        print(f'[{self.thread_id}] {self.full_name}: set_power_ratio({ratio})')
        
    def get_power_ratio(self,_subdevice_id:int) -> float:
        print(f'[{self.thread_id}] {self.full_name}: get_power_ratio()')
        return self.power_ratio
    
    ############################################################## Power Status        
    
    @pyqtSlot(int,bool)
    def set_power_status(self,_subdevice_id:int,status:bool):
        self.power_status = status
        on_or_off = 'on' if self.power_status else 'off'
        print(f'[{self.thread_id}] {self.full_name}: set_power_status({status}) [{on_or_off}]')
        
    def get_power_status(self,_subdevice_id:int) -> bool:
        on_or_off = 'on' if self.power_status else 'off'
        print(f'[{self.thread_id}] {self.full_name}: get_power_status() [{on_or_off}]')
        return self.power_status

############################################################################### Toptica iBeam

from microscope.lights.toptica import TopticaiBeam

class TopticaIBeamLaser(Device):
    
    ################################################################### Signals
    
    done = pyqtSignal(str)
    
    ############################################################# CTOR and DTOR
    
    def __init__(self,dev_name:str,com_port:str='COM3'):
        super().__init__(dev_name,'Laser','Toptica','iBeam')
        self.iBeam = TopticaiBeam(com_port)
        
        self.power_status = False

        self.power_value       = 0.0
        self.power_value_range = (0.0,200.0)
        self.power_value_unit  = 'mW'
        self.power_value_step  = 0.01
    
    def free(self):
        self.set_power_value (None,0.0)
        self.set_power_status(None,False)
        self.iBeam.shutdown()
        super().free()
    
    ############################################################### Power Value
    
    @pyqtSlot(int,float)
    def set_power_value(self,_subdevice:int,value:float):
        self.power_value = min(max(value,self.power_value_range[0]),self.power_value_range[1])
        self.iBeam._conn.command(b"channel 1 power %f" % (self.power_value))
    
    def get_power_value(self,_subdevice_id:int) -> float:
        return self.power_value
    
    ############################################################## Power Status
    
    @pyqtSlot(int,bool)
    def set_power_status(self,_subdevice_id:int,status:bool):
        self.power_status = status
        if self.power_status:
            self.iBeam.enable()
        else:
            self.iBeam.disable()
            
    def get_power_status(self,_subdevice_id:int) -> bool:
        return self.power_status
    
############################################################################### OmicronPycroManager

from pycromanager import Core, start_headless, stop_headless
from mmpycorex import terminate_core_instances
import atexit

class OmicronLaser_PycroManager(Device):
    
    ################################################################### Signals
    
    done = pyqtSignal(str)
    
    ############################################################# CTOR and DTOR
    
    def __init__(self,dev_name:str,cfg_file:str='\\omicron640nmLaser.cfg'):
        super().__init__(dev_name,'Laser','PycroManager','Omicron USB')
        
        self.power_value       = 0.0
        self.power_value_range = (0.0,100.0)
        self.power_value_unit  = '%'
        self.power_value_step  = 0.01

        self.power_status = False

        mm_app_path = 'C:\\Program Files\\Micro-Manager-2.0\\'
        config_file = mm_app_path + cfg_file
        
        
        # Start the headless process (Java backend)
        start_headless(mm_app_path, config_file, python_backend=False)
        self.mmcore = Core()
        
        # Fix stop_headless
        atexit.unregister(stop_headless)
        #atexit.register(terminate_core_instances,False)
        
    def free(self):
        self.set_power_value (None,0.0)
        self.set_power_status(None,False)
        # try:
        #     terminate_core_instances(False)
        # except Exception as e: print(e)
        super().free()
        

    ############################################################### Power Ratio

    @pyqtSlot(int,float)
    def set_power_value(self,_subdevice_id:int,value:float):
        self.power_value = min(max(value,self.power_value_range[0]),self.power_value_range[1])
        self.mmcore.set_property('Omicron USB','Power Setpoint', self.power_value)
        
    def get_power_value(self,_subdevice_id:int) -> float:
        return self.power_value
    
    ############################################################## Power Status        
    
    @pyqtSlot(int,bool)
    def set_power_status(self,_subdevice_id:int,status:bool):
        self.power_status = status
        on_or_off = 'On' if self.power_status else 'Off'
        self.mmcore.set_property('Omicron USB','Power',on_or_off)
    
    def get_power_status(self,_subdevice_id:int) -> bool:
        return self.power_status

############################################################################### MicroFPGA

import microfpga.controller as _cl
from microfpga.signals import LaserTriggerMode as _mode

class MicroFPGALaser(Device):
    
    ################################################################### Signals
    
    done = pyqtSignal(str)
    
    ############################################################# CTOR and DTOR
    
    def __init__(self,dev_name:str,com_index:int=9):
        super().__init__(dev_name,'Laser','MicroFPGA','1-channels')
        
        self._ufpga = _cl.MicroFPGA(known_device=com_index, # connectad at COM9
                                    use_camera=False,       # not using camera
                                    n_pwm=4,                # has 4 PWM channels
                                    n_laser=4               # has 1 laser connected
                                    )
        
        assert self._ufpga.is_connected(), f'Problem connecting to the FPGA ({self._ufpga.device})'
        
        self.power_status = [False,]

        self.power_value       = [0.0,]
        self.power_value_range = [(0.0,100.0),]
        self.power_value_unit  = '%'
        self.power_value_step  = 0.01
        
        self.channels_conf = [
            {'pwm': 3, 'laser': 3 },
            ]
        
    def free(self):
        for dev_id in range(len(self.power_status)):
            self.set_power_value (dev_id,0.0)
            self.set_power_status(dev_id,False)
        self._ufpga.disconnect()
        super().free()

    ############################################################### Power Ratio

    @pyqtSlot(int,float)
    def set_power_value(self,subdevice_id:int,value:float):
        self.power_value[subdevice_id] = min(max(value,self.power_value_range[subdevice_id][0]),self.power_value_range[subdevice_id][1])
        uint8_value = int( np.round(255.0*self.power_value[subdevice_id])/100.0 )
        self._ufpga.set_pwm_state(self.channels_conf[subdevice_id]['pwm'],uint8_value)
        
    def get_power_value(self,subdevice_id:int) -> float:
        return self.power_value[subdevice_id]
    
    ############################################################## Power Status        
    
    @pyqtSlot(int,bool)
    def set_power_status(self,subdevice_id:int,status:bool):
        print('sup: ',status)
        self.power_status[subdevice_id] = status
        on_or_off = _mode.MODE_ON if self.power_status[subdevice_id] else _mode.MODE_OFF
        self._ufpga._lasers[self.channels_conf[subdevice_id]['laser']].set_mode(on_or_off)
        
    def get_power_status(self,subdevice_id:int) -> bool:
        return self.power_status[subdevice_id]

    







