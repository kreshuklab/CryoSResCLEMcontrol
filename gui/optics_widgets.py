from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QGridLayout
from PyQt5.QtWidgets import QDoubleSpinBox, QPushButton, QLabel, QAbstractButton
from PyQt5.QtCore import QTimer, QThread, pyqtSignal, Qt
# from PyQt5.QtGui import QFont
from gui import IconProvider

from gui.ui_utils import IconProvider
from gui.ui_utils import create_iconized_button,update_iconized_button

_g_icon_prov = IconProvider()

############################################################################### LaserWidget

class LaserVerticalWidget(QWidget):
    set_power_status   = pyqtSignal(int,bool)
    set_power_fraction = pyqtSignal(int,float)
    
    def __init__(self,laser_device,laser_name,hex_color='#E07070',device_id=0,parent=None):
        super().__init__(parent)
        
        self.laser_thread = QThread(self)
        self.laser_device = laser_device
        self.device_id    = device_id
        self.is_laser_on  = False
        
        self.title = self.create_title(laser_name,hex_color)
        
        self.percentage = QDoubleSpinBox()
        percentage = self.create_percentage(_g_icon_prov.dimmer_switch,self.percentage)
        
        self.power_button = create_iconized_button(_g_icon_prov.light_bulb_on,'Turn on')
        
        self._create_layout(self.title,percentage,self.power_button)
        
        self.power_button.clicked.connect(self.button_trigger)
        self.percentage.editingFinished.connect(self.editing_finished)
        
        self.set_power_status.connect  ( self.laser_device.set_power_status   )
        self.set_power_fraction.connect( self.laser_device.set_power_fraction )
        
        self.laser_device.moveToThread(self.laser_thread)
        self.laser_thread.start()
        
    def __del__(self):
        if self.laser_thread.isRunning():
            self.laser_thread.quit()
            self.laser_thread.wait()  
    
    def _create_layout(self,title,spin_box,power_button):
        layout = QGridLayout()
        layout.addWidget(title,0,0)
        layout.addWidget(spin_box,1,0)
        layout.addWidget(power_button,2,0)
        self.setLayout(layout)
    
    def create_title(self,name,hex_color):
        widget = QWidget()
        layout = QHBoxLayout()
        layout.setContentsMargins(0,0,0,0)
        
        title = QLabel(name)
        title_font = self.font()
        title_font.setBold(True)
        title.setFont(title_font)
        title.setAlignment( Qt.AlignmentFlag.AlignLeft )
        
        colorbar = QLabel()
        colorbar.setFixedHeight(7)
        colorbar.setStyleSheet(f'background-color: {hex_color}')
        
        layout.addWidget(title,0,Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(colorbar,1,Qt.AlignmentFlag.AlignVCenter)
        
        widget.setLayout(layout)
        return widget
    
    def create_percentage(self,icon,spin_box):
        widget = QWidget()
        layout = QHBoxLayout()
        layout.setContentsMargins(0,0,0,0)
        
        spin_box.setRange(0,100)
        spin_box.setValue(0)
        spin_box.setDecimals(2)
        spin_box.setSuffix('%')
        
        icon_tmp = QLabel()
        icon_tmp.setPixmap(icon.pixmap(24,24))
        
        layout.addWidget(icon_tmp,0,Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(spin_box,1,Qt.AlignmentFlag.AlignVCenter)
        
        widget.setLayout(layout)
        return widget
    
    def editing_finished(self):
        value = self.percentage.value()
        if value >= 0 and value <= 100.0:
            self.set_power_fraction.emit(self.device_id,value)
    
    def button_trigger(self):
        if self.is_laser_on:
            update_iconized_button(self.power_button,_g_icon_prov.light_bulb_on,'Turn on')
            self.is_laser_on = False
        else:
            update_iconized_button(self.power_button,_g_icon_prov.light_bulb_off,'Turn off')
            self.is_laser_on = True
        self.set_power_status.emit(self.device_id,self.is_laser_on)
        
class LaserHorizontalWidget(LaserVerticalWidget):
    def _create_layout(self,title,spin_box,power_button):
        layout = QGridLayout()
        layout.addWidget(title,0,0,1,2)
        layout.addWidget(spin_box,1,0)
        layout.addWidget(power_button,1,1)
        self.setLayout(layout)

############################################################################### LaserWidget

class LaserWidget(QWidget):
    turn_on  = pyqtSignal(int)
    turn_off = pyqtSignal(int)
    set_pwm_percentage = pyqtSignal(int,float)
    
    def __init__(self,manager,device,name,vertical=True,*args,**kwargs):
        super().__init__(*args,**kwargs)
        
        self.device = device
        self.name   = name
        self.is_laser_on = False
        
        self.percentage = QDoubleSpinBox()
        self.percentage.setRange(0,100)
        self.percentage.setValue(0)
        self.percentage.setDecimals(2)
        self.percentage.setSuffix('%')
        self.percentage.editingFinished.connect(self.editing_finished)
                
        self.button = QPushButton(f"Turn on\n{self.name}")
        self.button.clicked.connect(self.button_trigger)
        
        if vertical:
            layout = QVBoxLayout()
            layout.addWidget(self.percentage)
            layout.addWidget(self.button)
            
        else:
            layout = QHBoxLayout()
            layout.addWidget(self.button)
            layout.addWidget(self.percentage)
            
        self.setLayout(layout)
        
        self.turn_on.connect ( manager.turn_on  )
        self.turn_off.connect( manager.turn_off )
        self.set_pwm_percentage.connect( manager.set_pwm_percentage )
    
    def editing_finished(self):
        value = self.percentage.value()
        if value >= 0 and value <= 100.0:
            self.set_pwm_percentage.emit(self.device,value)
    
    def button_trigger(self):
        if self.is_laser_on:
            self.turn_off.emit(self.device)
            self.button.setText(f"Turn on\n{self.name}")
            self.is_laser_on = False
        else:
            self.turn_on.emit(self.device)
            self.button.setText(f"Turn off\n{self.name}")
            self.is_laser_on = True
            
############################################################################### PwmWidget

class PwmWidget(QWidget):
    turn_on  = pyqtSignal(int)
    turn_off = pyqtSignal(int)
    
    def __init__(self,manager,device,name,vertical=True,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.device = device
        self.name   = name
        
        self.button = QPushButton(f"Start pulsing\n{self.name}")
        self.button.clicked.connect(self.button_trigger)
        
        self.time_on = QDoubleSpinBox()
        self.time_on.setMinimum(0)
        self.time_on.setMaximum(float('inf'))
        self.time_on.setValue(1)
        self.time_on.setDecimals(3)
        self.time_on.setSuffix(' sec')
        
        self.time_off = QDoubleSpinBox()
        self.time_off.setMinimum(0)
        self.time_off.setMaximum(float('inf'))
        self.time_off.setValue(1)
        self.time_off.setDecimals(3)
        self.time_off.setSuffix(' sec')
        
        form_widget = QWidget()
        form_layout = QFormLayout()
        
        form_layout.addRow('Time ON:' ,self.time_on)
        form_layout.addRow('Time OFF:',self.time_off)
        
        form_widget.setLayout(form_layout)
        
        if vertical:
            layout = QVBoxLayout()
            layout.addWidget(form_widget)
            layout.addWidget(self.button)
            
        else:
            layout = QHBoxLayout()
            layout.addWidget(self.button)
            layout.addWidget(form_widget)
            
        self.setLayout(layout)
        
        self.status_on = False
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.timer_triggered)
        
        self.turn_on.connect ( manager.turn_on  )
        self.turn_off.connect( manager.turn_off )

    def timer_triggered(self):
        if self.status_on:
            # If the laser is ON and the timer timed-out:
            # - Turn off the laser
            # - Start the timer with OFF time
            self.turn_off.emit(self.device)
            self.status_on = False
            self.timer.start( int(self.time_off.value()*1e3) )
        else:
            # If the laser is OFF and the timer timed-out:
            # - Turn ob the laser
            # - Start the timer with ON time
            self.turn_on.emit(self.device)
            self.timer.start( int(self.time_on.value()*1e3) )
            self.status_on = True

    def button_trigger(self):
        if self.timer.isActive():
            # If we click the button and the timer is active:
            # - Stop the timer
            # - Set the button to start the PWM again
            # - Allow users to change the PWM parameters
            self.timer.stop()
            self.button.setText(f"Start pulsing\n{self.name}")
            self.time_on.setEnabled(True)
            self.time_off.setEnabled(True)
        else:
            # If we click the button and the timer is not active:
            # - Turn on laser
            # - Start the timer with ON time
            # - Set the button to stop the PWM
            # - Do not allow users to change the PWM parameters
            self.turn_on.emit(self.device)
            self.status_on = True
            self.timer.start( int(self.time_on.value()*1e3) )
            self.button.setText(f"Stop pulsing\n{self.name}")
            self.time_on.setEnabled(False)
            self.time_off.setEnabled(False)
            
############################################################################### FilterWheelWidget

class FilterWheelWidget(QWidget):
    move_to = pyqtSignal(int)
    
    def __init__(self,manager,names=('520/35','530/30','585/40','617/50','692/50','none'),vertical=True,*args,**kwargs):
        super().__init__(*args,**kwargs)
        
        self.manager = manager
        
        if vertical:
            self.layout = QVBoxLayout()
        else:
            self.layout = QHBoxLayout()
        
        for i,label in enumerate(names):
            button = QPushButton(label)
            button.setProperty('id',i)
            button.clicked.connect(lambda state: self.move_to.emit( self.sender().property('id') ))
            self.layout.addWidget(button)
        
        self.setLayout(self.layout)
        self.move_to.connect( self.manager.set_position )
        self.manager.filterwheel_done.connect( self.update_position )
        
        self.update_position()
        
    def update_position(self):
        position = self.manager.current_position
        
        for i in range(self.layout.count()):
            item = self.layout.itemAt(i)
            widget = item.widget()
            font = widget.font()
            font.setBold(i==position)
            widget.setFont(font)







