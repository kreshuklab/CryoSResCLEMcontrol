from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QFormLayout
from PyQt5.QtWidgets import QDoubleSpinBox, QPushButton
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QFont

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







