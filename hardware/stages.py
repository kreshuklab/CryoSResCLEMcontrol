from PyQt5.QtCore import QObject, QThread, pyqtSignal, pyqtSlot
import numpy as np
import serial

############################################################################### AttoCom

class AttoCom(QObject):
    
    show_commands = True
    
    def __init__(self,com_port='COM5',baudrate=38400,parent=None):
        super().__init__(parent)
        self.com = serial.Serial(com_port,baudrate,parity=serial.PARITY_NONE)
        self.disable_echo()
    
    def _send_command(self,command):
        self.com.write( command.encode('ascii') )
        for _ in range(2):
            check = self.com.readline()
            check_val = check.strip().decode('ascii')
            if check_val == 'OK':
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
    
    def set_mode_mixed(self,axis_id):
        if self.read_mode(axis_id) != b'stp+':
            self._send_command( f'setm {axis_id} stp+\r\n' )
    
    def set_mode_step(self,axis_id):
        if self.read_mode(axis_id) != b'stp':
            self._send_command( f'setm {axis_id} stp\r\n' )
    
    def set_mode_offset(self,axis_id):
        if self.read_mode(axis_id) != b'off':
            self._send_command( f'setm {axis_id} off\r\n' )
            
    def set_mode_ground(self,axis_id):
        self._send_command( f'setm {axis_id} gnd\r\n' )
        
    
    @pyqtSlot(int,bool,int)
    def positioning_coarse(self,axis_id,is_up,n_steps):
        if is_up:
            self._send_command( f'stepu {int(axis_id)} {int(n_steps)}\r\n' )
        else:
            self._send_command( f'stepd {int(axis_id)} {int(n_steps)}\r\n' )

    @pyqtSlot(int,float)
    def positioning_fine_delta(self,axis_id,delta_voltage):
        current_voltage = self.read_offset_voltage( axis_id )
        new_voltage = max(current_voltage + delta_voltage,0)
        self._send_command( f'seta {axis_id} {new_voltage}\r\n' )
    
    def positioning_fine_absolute(self,axis_id,voltage):
        self._send_command( f'seta {axis_id} {voltage}\r\n' )
        
    def wait_axis(self,axis_id):
        self._send_command( f'stepw {axis_id}\r\n' )



