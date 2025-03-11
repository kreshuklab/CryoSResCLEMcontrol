from PyQt5.QtCore import QThread, pyqtSignal, pyqtSlot
import numpy as np

############################################################################### Dummy

class DummyLaser(QThread):
    laser_done = pyqtSignal()
    
    def __init__(self):
        super().__init__()
    
    @pyqtSlot(int,float)
    def set_pwm_percentage(self,device,pwm_value):
        print(f'DummyLaser.set_pwm_percentage({device},{pwm_value})')
        self.laser_done.emit()
    
    @pyqtSlot(int)
    def turn_on(self,device):
        print(f'DummyLaser.turn_on({device})')
        self.laser_done.emit()
        
    @pyqtSlot(int)
    def turn_off(self,device):
        print(f'DummyLaser.turn_off({device})')
        self.laser_done.emit()

############################################################################### MicroFPGA

import microfpga.controller as _cl
from microfpga.signals import LaserTriggerMode as _mode

class MicroFpga(QThread):
    laser_done = pyqtSignal()
    
    def __init__(self):
        super().__init__()
        
        self._ufpga = _cl.MicroFPGA(known_device=9,     # connectad at COM9
                                    use_camera=False,   # not using camera
                                    n_pwm=4,            # has 4 PWM channels
                                    n_laser=1           # has 1 laser connected
                                    )
        
        assert self._ufpga.is_connected(), f'Problem connecting to the FPGA ({self._ufpga.device})'
        
        # FPGA configurations
        self.lasers = [
            { 'Name': '405nm', 'pwm_channel': 2, 'laser_id': 0 },
            ]

    def __del__(self):
        if self._ufpga.is_connected():
            for device in range(len(self.lasers)):
                self._ufpga.set_pwm_state(self.lasers[device]['pwm_channel'],0)
                self._ufpga._lasers[self.lasers[device]['laser_id']].set_mode(_mode.MODE_OFF)
            self._ufpga.disconnect()

    @pyqtSlot(int,float)
    def set_pwm_percentage(self,device,pwm_value):
        value = int( np.round(255.0*pwm_value/100.0) )
        self._ufpga.set_pwm_state(self.lasers[device]['pwm_channel'],value)
        self.laser_done.emit()
    
    @pyqtSlot(int)
    def turn_on(self,device):
        self._ufpga._lasers[self.lasers[device]['laser_id']].set_mode(_mode.MODE_ON)
        self.laser_done.emit()
        
    @pyqtSlot(int)
    def turn_off(self,device):
        self._ufpga._lasers[self.lasers[device]['laser_id']].set_mode(_mode.MODE_OFF)
        self.laser_done.emit()

############################################################################### Omicron

from pycromanager import Core, start_headless

class OmicronLaser(QThread):
    laser_done = pyqtSignal()
    
    def __init__(self):
        super().__init__()
        
        mm_app_path = 'C:\\Program Files\\Micro-Manager-2.0\\'
        config_file = mm_app_path + "\\omicron640nmLaser.cfg"

        # Start the headless process (Java backend)
        start_headless(mm_app_path, config_file, python_backend=False)
        self.mmcore = Core()
        
        devices = self.mmcore.get_loaded_devices()
        for i in range(devices.size()):
            print( devices.get(i) )
    
    def __del__(self):
        self.mmcore.set_property("Omicron USB","Power Setpoint", 0.0)
        self.mmcore.set_property("Omicron USB","Power","Off")
    
    @pyqtSlot(int,float)
    def set_pwm_percentage(self,device,pwm_value):
        self.mmcore.set_property("Omicron USB","Power Setpoint", pwm_value)
        self.laser_done.emit()
    
    @pyqtSlot(int)
    def turn_on(self,device):
        self.mmcore.set_property("Omicron USB","Power","On")
        self.laser_done.emit()
        
    @pyqtSlot(int)
    def turn_off(self,device):
        self.mmcore.set_property("Omicron USB","Power","Off")
        self.laser_done.emit()

############################################################################### Dummy

from microscope.lights.toptica import TopticaiBeam

class TopticaLaser(QThread):
    laser_done = pyqtSignal()
    
    def __init__(self):
        super().__init__()
        self.iBeam = TopticaiBeam('COM3')
        
    def __del__(self):
        self.iBeam._conn.command(b"channel 1 power 0.0")
        self.iBeam.disable()
    
    @pyqtSlot(int,float)
    def set_pwm_percentage(self,device,pwm_value):
        self.iBeam._conn.command(b"channel 1 power %f" % (2*pwm_value))
        self.laser_done.emit()
    
    @pyqtSlot(int)
    def turn_on(self,device):
        self.iBeam.enable()
        self.laser_done.emit()
        
    @pyqtSlot(int)
    def turn_off(self,device):
        self.iBeam.disable()
        self.laser_done.emit()

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
    
    







