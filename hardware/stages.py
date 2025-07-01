from .common import Device
from PyQt5.QtCore import pyqtSignal, pyqtSlot
from time import sleep
import serial

############################################################################### Dummy

class DummyStage(Device):
    done = pyqtSignal(str)
    
    def __init__(self,dev_name:str):
        super().__init__(dev_name,'Stage','Dummy','StdIO')
        self.axis_dict = {'x':2,'y':1,'z':3}
        self.axis_x = self.axis_dict['x']
        self.axis_y = self.axis_dict['y']
        self.axis_z = self.axis_dict['z']
        self.show_commands = True
        
        self.x_steps = 0
        self.y_steps = 0
        self.z_steps = 0
        
    def free(self):
        self.set_mode_ground()
        super().free()
        
    def set_configuration(self,init_voltage_offset=65):
        self.init_voltage_offset = init_voltage_offset
        self.set_mode_mixed()
        self.positioning_fine_absolute(1,init_voltage_offset)
        self.positioning_fine_absolute(2,init_voltage_offset)
        self.positioning_fine_absolute(3,init_voltage_offset)
    
    @pyqtSlot()
    def reset_configuration(self):
        self.set_mode_ground()
        self.set_configuration(self.init_voltage_offset)
    
    def set_position_counter(self,x=0,y=0,z=0):
        self.x_steps = x
        self.y_steps = y
        self.z_steps = z
    
    @pyqtSlot(int,int)
    def set_voltage(self,axis_id,volt_value):
        print(f'[{self.thread_id}] {self.full_name}: set_voltage({axis_id},{volt_value})')
        
    @pyqtSlot(int)
    def set_frequencies(self,freq_value):
        for axis in self.axis_dict.values():
            self.set_frequency(axis,freq_value)
        
    def set_frequency(self,axis_id,freq_value):
        print(f'[{self.thread_id}] {self.full_name}: set_frequency({axis_id},{freq_value})')
    
    def set_mode_mixed(self,axis_id=None):
        if axis_id is None:
            for axis in self.axis_dict.values():
                self.set_mode_mixed(axis)
        else:
            print(f'[{self.thread_id}] {self.full_name}: set_mode_mixed({axis_id})')
    
    def set_mode_step(self,axis_id=None):
        if axis_id is None:
            for axis in self.axis_dict.values():
                self.set_mode_step(axis)
        else:
            print(f'[{self.thread_id}] {self.full_name}: set_mode_step({axis_id})')
    
    def set_mode_offset(self,axis_id=None):
        if axis_id is None:
            for axis in self.axis_dict.values():
                self.set_mode_offset(axis)
        else:
            print(f'[{self.thread_id}] {self.full_name}: set_mode_offset({axis_id})')
            
    def set_mode_ground(self,axis_id=None):
        if axis_id is None:
            for axis in self.axis_dict.values():
                self.set_mode_ground(axis)
        else:
            print(f'[{self.thread_id}] {self.full_name}: set_mode_ground({axis_id})')
    
    @pyqtSlot(int,bool,int)
    def positioning_coarse(self,axis_id,is_up,n_steps):
        axis_name = list( self.axis_dict.keys() )[ list(self.axis_dict.values()).index(axis_id) ]
        if is_up:
            print(f'[{self.thread_id}] {self.full_name}: step_up({axis_id},{n_steps})')
            self.step_counter[axis_name] = self.step_counter[axis_name] + int(n_steps)
        else:
            print(f'[{self.thread_id}] {self.full_name}: step_down({axis_id},{n_steps})')
            self.step_counter[axis_name] = self.step_counter[axis_name] - int(n_steps)

    @pyqtSlot(int,float)
    def positioning_fine_delta(self,axis_id,delta_voltage):
        print(f'[{self.thread_id}] {self.full_name}: delta_pos({axis_id},{delta_voltage})')
    
    def positioning_fine_absolute(self,axis_id,voltage):
        print(f'[{self.thread_id}] {self.full_name}: set_pos({axis_id},{voltage})')
        
    def wait_axis(self,axis_id):
        sleep(0.05)
        self.done.emit(self.name)

############################################################################### AttoCubeStage

class AttoCubeStage(Device):
    done = pyqtSignal(str)
    
    def __init__(self,dev_name:str,com_port:str='COM5',baudrate=38400):
        super().__init__(dev_name,'Stage','AttoCube','ANP')
        self.axis_dict = {'x':2,'y':1,'z':3}
        self.axis_x = self.axis_dict['x']
        self.axis_y = self.axis_dict['y']
        self.axis_z = self.axis_dict['z']
        self.show_commands = False
        
        self.offset_tracker = {'x':0,'y':0,'z':0}
        
        self.com = serial.Serial(com_port,baudrate,parity=serial.PARITY_NONE)
        self.disable_echo()
        
        self.step_counter = {'x':0,'y':0,'z':0}
        self.is_busy = False
        
        self.init_voltage_offset = 65
        
    def free(self):
        self.set_mode_ground()
        # self.enable_echo()
        super().free()
        
    def set_configuration(self,init_voltage_offset=65):
        self.init_voltage_offset = init_voltage_offset
        self.set_mode_mixed()
        self.positioning_fine_absolute(1,init_voltage_offset)
        self.positioning_fine_absolute(2,init_voltage_offset)
        self.positioning_fine_absolute(3,init_voltage_offset)
    
    @pyqtSlot()
    def reset_configuration(self):
        self.set_mode_ground()
        self.set_configuration(self.init_voltage_offset)
    
    def set_position_counter(self,x=0,y=0,z=0):
        self.step_counter['x'] = x
        self.step_counter['y'] = y
        self.step_counter['z'] = z
    
    def _send_command(self,command):
        self.com.write( command.encode('ascii') )
        for _ in range(2):
            check = self.com.readline()
            check_val = check.strip().decode('ascii')
            if check_val == 'OK':
                break
            elif check_val == 'ERROR':
                print('An error happened')
                break
            else:
                print('Ignoring ',check_val)
        if self.show_commands:
            print(command.strip(),check.strip())
            
    def _read_command(self,command):
        self.com.write( command.encode('ascii') )
        read_val = self.com.readline()
        for _ in range(2):
            check = self.com.readline()
            check_val = check.strip().decode('ascii')
            if check_val == 'OK':
                break
            else:
                print('Ignoring ',check_val)
        if self.show_commands:
            print(command.strip(),read_val.strip(),check.strip())
        return read_val
    
    def disable_echo(self):
        self._send_command( 'echo off\r\n' )

    def enable_echo(self):
        self._send_command( 'echo on\r\n' )

    def read_mode(self,axis_id):
        read_value = self._read_command( f'getm {axis_id}\r\n' )
        return read_value[7:-2]
        
    def read_offset_voltage(self,axis_id):
        read_value = self._read_command( f'geta {axis_id}\r\n' )
        return float(read_value[10:-4])
    
    @pyqtSlot(int,int)
    def set_voltage(self,axis_id,volt_value):
        self._send_command( f'setv {axis_id} {volt_value}\r\n' )
        
    @pyqtSlot(int)
    def set_frequencies(self,freq_value):
        self.set_frequency(1,freq_value)
        self.set_frequency(2,freq_value)
        self.set_frequency(3,freq_value)
        
    def set_frequency(self,axis_id,freq_value):
        self._send_command( f'setf {axis_id} {freq_value}\r\n' )
    
    def set_mode_mixed(self,axis_id=None):
        if axis_id is None:
            for axis in self.axis_dict.values():
                self.set_mode_mixed(axis)
        else:
            if self.read_mode(axis_id) != b'stp+':
                self._send_command( f'setm {axis_id} stp+\r\n' )
    
    def set_mode_step(self,axis_id=None):
        if axis_id is None:
            for axis in self.axis_dict.values():
                self.set_mode_mixed(axis)
        else:
            if self.read_mode(axis_id) != b'stp':
                self._send_command( f'setm {axis_id} stp\r\n' )
    
    def set_mode_offset(self,axis_id=None):
        if axis_id is None:
            for axis in self.axis_dict.values():
                self.set_mode_mixed(axis)
        else:
            if self.read_mode(axis_id) != b'off':
                self._send_command( f'setm {axis_id} off\r\n' )
            
    def set_mode_ground(self,axis_id=None):
        if axis_id is None:
            for axis in self.axis_dict.values():
                self.set_mode_ground(axis)
        else:
            if self.read_mode(axis_id) != b'gnd':
                self._send_command( f'setm {axis_id} gnd\r\n' )
        
    @pyqtSlot(int,bool,int)
    def positioning_coarse(self,axis_id,is_up,n_steps):
        if self.is_busy:
            return
        self.is_busy = True
        axis_name = list( self.axis_dict.keys() )[ list(self.axis_dict.values()).index(axis_id) ]
        if is_up:
            self._send_command( f'stepu {int(axis_id)} {int(n_steps)}\r\n' )
            self.step_counter[axis_name] = self.step_counter[axis_name] + int(n_steps)
        else:
            self._send_command( f'stepd {int(axis_id)} {int(n_steps)}\r\n' )
            self.step_counter[axis_name] = self.step_counter[axis_name] - int(n_steps)
        self.wait_axis(axis_id)
        self.is_busy = False
        
    @pyqtSlot(int,float)
    def positioning_fine_delta(self,axis_id,delta_voltage):
        if self.is_busy:
            return
        self.is_busy = True
        axis_name = list( self.axis_dict.keys() )[ list(self.axis_dict.values()).index(axis_id) ]
        current_voltage = self.read_offset_voltage( axis_id )
        new_voltage = max(current_voltage + delta_voltage,0)
        self.offset_tracker[axis_name] = new_voltage
        self._send_command( f'seta {axis_id} {new_voltage}\r\n' )
        self.is_busy = False
        
    def positioning_fine_absolute(self,axis_id,voltage):
        try:
            axis_name = list( self.axis_dict.keys() )[ list(self.axis_dict.values()).index(axis_id) ]
            self.offset_tracker[axis_name] = voltage
        except Exception as e: print(e)
        self._send_command( f'seta {axis_id} {voltage}\r\n' )
        
    def wait_axis(self,axis_id):
        self._send_command( f'stepw {axis_id}\r\n' )
        self.done.emit(self.name)

