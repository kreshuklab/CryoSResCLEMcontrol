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

class TopticaIBeamLaser(QThread):
    
    ################################################################### Signals
    
    done = pyqtSignal(str)
    
    ############################################################# CTOR and DTOR
    
    def __init__(self,dev_name:str,com_port:str='COM3'):
        super().__init__(dev_name)
        self.iBeam = TopticaiBeam(com_port)
        
        self.power_status = False

        self.power_value       = 0.0
        self.power_value_range = (0.0,2.0)
        self.power_value_unit  = 'mW'
        self.power_value_step  = 0.01
    
    def free(self):
        self.set_power_value (None,0.0)
        self.set_power_status(None,False)
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

from pycromanager import Core, start_headless

class OmicronLaser_PycroManager(Device):
    
    ################################################################### Signals
    
    done = pyqtSignal(str)
    
    ############################################################# CTOR and DTOR
    
    def __init__(self,dev_name:str,cfg_file:str='\\omicron640nmLaser.cfg'):
        super().__init__(dev_name,'Laser','PycroManager','Omicron USB')
        
        self.power_ratio       = 0.0
        self.power_ratio_range = (0.0,1.0)
        
        self.power_status = False

        mm_app_path = 'C:\\Program Files\\Micro-Manager-2.0\\'
        config_file = mm_app_path + cfg_file

        # Start the headless process (Java backend)
        start_headless(mm_app_path, config_file, python_backend=False)
        self.mmcore = Core()
        
    def free(self):
        self.set_power_ratio (None,0.0)
        self.set_power_status(None,False)
        super().free()

    ############################################################### Power Ratio

    @pyqtSlot(int,float)
    def set_power_ratio(self,_subdevice_id:int,ratio:float):
        self.power_ratio = min(max(ratio,self.power_ratio_range[0]),self.power_ratio_range[1])
        self.mmcore.set_property('Omicron USB','Power Setpoint', self.power_ratio)
        
    def get_power_ratio(self,_subdevice_id:int) -> float:
        return self.power_ratio
    
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
                                    n_laser=1               # has 1 laser connected
                                    )
        
        assert self._ufpga.is_connected(), f'Problem connecting to the FPGA ({self._ufpga.device})'
        
        self.power_status = [False,]

        self.power_ratio       = [0.0,]
        self.power_ratio_range = [(0.0,1.0),]
        
        self.channels_conf = [
            {'pwm': 2, 'laser': 0 },
            ]
        
    def free(self):
        for dev_id in range(len(self.power_status)):
            self.set_power_ratio (dev_id,0.0)
            self.set_power_status(dev_id,False)
        self._ufpga.disconnect()
        super().free()

    ############################################################### Power Ratio

    @pyqtSlot(int,float)
    def set_power_ratio(self,subdevice_id:int,ratio:float):
        self.power_ratio[subdevice_id] = min(max(ratio,self.power_ratio_range[subdevice_id][0]),self.power_ratio_range[subdevice_id][1])
        value = int( np.round(255.0*self.power_ratio[subdevice_id]) )
        self._ufpga.set_pwm_state(self.channels_conf[subdevice_id]['pwm'],value)
        
        
        self.power_ratio = min(max(ratio,self.power_ratio_range[0]),self.power_ratio_range[1])
        print(f'[{self.thread_id}] {self.full_name}: set_power_ratio({ratio})')
        
    def get_power_ratio(self,subdevice_id:int) -> float:
        return self.power_ratio[subdevice_id]
    
    ############################################################## Power Status        
    
    @pyqtSlot(int,bool)
    def set_power_status(self,subdevice_id:int,status:bool):
        self.power_status[subdevice_id] = status
        on_or_off = _mode.MODE_ON if self.power_status[subdevice_id] else _mode.MODE_OFF
        self._ufpga._lasers[self.channels_conf[subdevice_id]['laser']].set_mode(on_or_off)
        
    def get_power_status(self,subdevice_id:int) -> bool:
        return self.power_status[subdevice_id]
    
# ###############################################################################
# ###############################################################################
# ###############################################################################

# ############################################################################### LaserDeviceBase

# class LaserDeviceBase(QObject):
    
#     ################################################################### Signals
    
#     failed = pyqtSignal(str)
#     done   = pyqtSignal(str)
    
#     ############################################################# CTOR and DTOR
    
#     def __init__(self,unique_id,vendor,model,n_devs=1,parent=None):
#         super().__init__(parent)
        
#         self.uid    = str(unique_id)
#         self.vendor = vendor
#         self.model  = model
#         self.power  = 0
#         self.status = False
#         self.n_devs = max(n_devs,1)
    
#     ####################################################### Log and Description
    
#     def _get_full_id(self,dev_id):
#         return f'{self.uid}.{self.vendor}.{self.model}.{dev_id}'
    
#     def log_message(self,dev_id:int,message:str,prefix=''):
#         print(f'{prefix}[{self._get_full_id(dev_id)}]: {message}')

#     def get_descriptor(self):
#         descriptor = {}
#         descriptor[f'{self.uid}.vendor'] = self.vendor
#         descriptor[f'{self.uid}.model' ] = self.model
#         descriptor[f'{self.uid}.power' ] = self.power
#         descriptor[f'{self.uid}.status'] = self.status
#         descriptor[f'{self.uid}.n_devs'] = self.n_devs
    
#     ############################################################ Power Fraction
    
#     @pyqtSlot(int,float)
#     def set_power_fraction(self,dev_id:int,fraction:float):
#         self.power = fraction
#         self._write_power_fraction(dev_id,self.power)
    
#     def get_power_fraction(self,dev_id:int):
#         power = self._read_power_fraction(dev_id)
#         self.power = power
#         return self.power
    
#     # To Be Implemented by Child
#     def _write_power_fraction(self,dev_id:int,fraction:float):
#         thread_id = int(QThread.currentThreadId())
#         self.log_message(dev_id,f'Setting power to {fraction:.3f}',prefix=f'[DUMMY {thread_id}] ')
    
#     # To Be Implemented by Child
#     def _read_power_fraction(self,dev_id:int):
#         thread_id = int(QThread.currentThreadId())
#         self.log_message(dev_id,f'Getting power as {self.power:.3f}',prefix=f'[DUMMY {thread_id}] ')
#         return self.power
    
#     ############################################################## Power Status
    
#     @pyqtSlot(int,bool)
#     def set_power_status(self,dev_id:int,status:bool):
#         self.status = status
#         self._write_power_status(dev_id,self.status)
    
#     def get_power_status(self,dev_id:int):
#         status = self._read_power_status(dev_id)
#         self.status = status
#         return self.status
        
#     # To Be Implemented by Child
#     def _write_power_status(self,dev_id:int,status:bool):
#         on_or_off = 'on' if status else 'off'
#         thread_id = int(QThread.currentThreadId())
#         self.log_message(dev_id,f'Setting power {on_or_off}',prefix=f'[DUMMY {thread_id}] ')
     
#     # To Be Implemented by Child
#     def _read_power_status(self,dev_id:int):
#         on_or_off = 'on' if self.status else 'off'
#         thread_id = int(QThread.currentThreadId())
#         self.log_message(dev_id,f'Getting power {on_or_off}',prefix=f'[DUMMY {thread_id}] ')
#         return self.status

# ############################################################################### Toptica iBeam

# from microscope.lights.toptica import TopticaiBeam

# class TopticaLaser(QThread):
#     laser_done = pyqtSignal()
    
#     def __init__(self):
#         super().__init__()
#         self.iBeam = TopticaiBeam('COM3')
        
#     def __del__(self):
#         self.iBeam._conn.command(b"channel 1 power 0.0")
#         self.iBeam.disable()
    
#     @pyqtSlot(int,float)
#     def set_pwm_percentage(self,device,pwm_value):
#         self.iBeam._conn.command(b"channel 1 power %f" % (2*pwm_value))
#         self.laser_done.emit()
    
#     @pyqtSlot(int)
#     def turn_on(self,device):
#         self.iBeam.enable()
#         self.laser_done.emit()
        
#     @pyqtSlot(int)
#     def turn_off(self,device):
#         self.iBeam.disable()
#         self.laser_done.emit()
        
# ############################################################################### Dummy

# class DummyLaser(QThread):
#     laser_done = pyqtSignal()
    
#     def __init__(self):
#         super().__init__()
    
#     @pyqtSlot(int,float)
#     def set_pwm_percentage(self,device,pwm_value):
#         print(f'DummyLaser.set_pwm_percentage({device},{pwm_value})')
#         self.laser_done.emit()
    
#     @pyqtSlot(int)
#     def turn_on(self,device):
#         print(f'DummyLaser.turn_on({device})')
#         self.laser_done.emit()
        
#     @pyqtSlot(int)
#     def turn_off(self,device):
#         print(f'DummyLaser.turn_off({device})')
#         self.laser_done.emit()

# ############################################################################### MicroFPGA

# import microfpga.controller as _cl
# from microfpga.signals import LaserTriggerMode as _mode

# class MicroFpga(QThread):
#     laser_done = pyqtSignal()
    
#     def __init__(self):
#         super().__init__()
        
#         self._ufpga = _cl.MicroFPGA(known_device=9,     # connectad at COM9
#                                     use_camera=False,   # not using camera
#                                     n_pwm=4,            # has 4 PWM channels
#                                     n_laser=1           # has 1 laser connected
#                                     )
        
#         assert self._ufpga.is_connected(), f'Problem connecting to the FPGA ({self._ufpga.device})'
        
#         # FPGA configurations
#         self.lasers = [
#             { 'Name': '405nm', 'pwm_channel': 2, 'laser_id': 0 },
#             ]

#     def __del__(self):
#         if self._ufpga.is_connected():
#             for device in range(len(self.lasers)):
#                 self._ufpga.set_pwm_state(self.lasers[device]['pwm_channel'],0)
#                 self._ufpga._lasers[self.lasers[device]['laser_id']].set_mode(_mode.MODE_OFF)
#             self._ufpga.disconnect()

#     @pyqtSlot(int,float)
#     def set_pwm_percentage(self,device,pwm_value):
#         value = int( np.round(255.0*pwm_value/100.0) )
#         self._ufpga.set_pwm_state(self.lasers[device]['pwm_channel'],value)
#         self.laser_done.emit()
    
#     @pyqtSlot(int)
#     def turn_on(self,device):
#         self._ufpga._lasers[self.lasers[device]['laser_id']].set_mode(_mode.MODE_ON)
#         self.laser_done.emit()
        
#     @pyqtSlot(int)
#     def turn_off(self,device):
#         self._ufpga._lasers[self.lasers[device]['laser_id']].set_mode(_mode.MODE_OFF)
#         self.laser_done.emit()

# ############################################################################### Omicron

# from pycromanager import Core, start_headless

# class OmicronLaser(QThread):
#     laser_done = pyqtSignal()
    
#     def __init__(self):
#         super().__init__()
        
#         mm_app_path = 'C:\\Program Files\\Micro-Manager-2.0\\'
#         config_file = mm_app_path + "\\omicron640nmLaser.cfg"

#         # Start the headless process (Java backend)
#         start_headless(mm_app_path, config_file, python_backend=False)
#         self.mmcore = Core()
        
#         devices = self.mmcore.get_loaded_devices()
#         for i in range(devices.size()):
#             print( devices.get(i) )
    
#     def __del__(self):
#         self.mmcore.set_property("Omicron USB","Power Setpoint", 0.0)
#         self.mmcore.set_property("Omicron USB","Power","Off")
    
#     @pyqtSlot(int,float)
#     def set_pwm_percentage(self,device,pwm_value):
#         self.mmcore.set_property("Omicron USB","Power Setpoint", pwm_value)
#         self.laser_done.emit()
    
#     @pyqtSlot(int)
#     def turn_on(self,device):
#         self.mmcore.set_property("Omicron USB","Power","On")
#         self.laser_done.emit()
        
#     @pyqtSlot(int)
#     def turn_off(self,device):
#         self.mmcore.set_property("Omicron USB","Power","Off")
#         self.laser_done.emit()

# ############################################################################### Dummy

# from microscope.lights.toptica import TopticaiBeam

# class TopticaLaser(QThread):
#     laser_done = pyqtSignal()
    
#     def __init__(self):
#         super().__init__()
#         self.iBeam = TopticaiBeam('COM3')
        
#     def __del__(self):
#         self.iBeam._conn.command(b"channel 1 power 0.0")
#         self.iBeam.disable()
    
#     @pyqtSlot(int,float)
#     def set_pwm_percentage(self,device,pwm_value):
#         self.iBeam._conn.command(b"channel 1 power %f" % (2*pwm_value))
#         self.laser_done.emit()
    
#     @pyqtSlot(int)
#     def turn_on(self,device):
#         self.iBeam.enable()
#         self.laser_done.emit()
        
#     @pyqtSlot(int)
#     def turn_off(self,device):
#         self.iBeam.disable()
#         self.laser_done.emit()

############################################################################### Dummy

from microscope.filterwheels.thorlabs import ThorlabsFilterWheel

class FilterWheel(QThread):
    filterwheel_done = pyqtSignal()
    
    def __init__(self):
        super().__init__()
        self.filterwheel = ThorlabsFilterWheel('COM8')
        self.current_position = self.filterwheel.position
        
    def __del__(self):
        self.filterwheel.disable()
    
    @pyqtSlot(int)
    def set_position(self,position):
        if position >=0 and position < 6:
            self.current_position = position
            self.filterwheel.position = position
            self.filterwheel_done.emit()
    
    







