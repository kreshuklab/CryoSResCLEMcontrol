from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QGridLayout
from PyQt5.QtWidgets import QDoubleSpinBox, QLabel
from PyQt5.QtCore import QTimer, pyqtSignal, pyqtSlot, Qt
# from PyQt5.QtGui import QFont

from gui.ui_utils import IconProvider
from gui.ui_utils import create_iconized_button,update_iconized_button
from gui.ui_utils import create_doublespinbox,colorbar_style_sheet

_g_icon_prov = IconProvider()

############################################################################### LaserWidget

class LaserWidget(QWidget):
    set_status = pyqtSignal(int,bool)
    set_power  = pyqtSignal(int,float)
    
    def __init__(self,laser_device,laser_name,hex_color='#E07070',device_id=0,vertical=True,parent=None):
        super().__init__(parent)
        
        self.laser_device = laser_device
        self.device_id    = device_id
        self.is_laser_on  = False
        
        list_widgets = []
        
        list_widgets.append(self.create_title(laser_name,hex_color))
        
        if hasattr(self.laser_device,'power_ratio'):
            if type(self.laser_device.power_status) is list:
                min_val = self.laser_device.power_ratio_range[self.device_id][0]
                max_val = self.laser_device.power_ratio_range[self.device_id][1]
            else:
                min_val = self.laser_device.power_ratio_range[0]
                max_val = self.laser_device.power_ratio_range[1]
            self.ratio = create_doublespinbox(min_val,max_val,min_val,step=0.05,decimals=4)
        else:
            if type(self.laser_device.power_status) is list:
                min_val = self.laser_device.power_value_range[self.device_id][0]
                max_val = self.laser_device.power_value_range[self.device_id][1]
            else:
                min_val = self.laser_device.power_value_range[0]
                max_val = self.laser_device.power_value_range[1]
            self.ratio = create_doublespinbox(min_val,max_val,min_val,self.laser_device.power_value_step,decimals=4)
            self.ratio.setSuffix(f' {self.laser_device.power_value_unit}')
        
        list_widgets.append(self.create_percentage(_g_icon_prov.dimmer_switch,self.ratio))

        self.power_button = create_iconized_button(_g_icon_prov.light_bulb_on,'Turn on')
        
        list_widgets.append(self.power_button)
        
        if vertical:
            self._create_vertical_layout(list_widgets)
        else:
            self._create_horizontal_layout(list_widgets)
        
        self.colorbar.setEnabled(self.is_laser_on)
        
        self.power_button.clicked.connect(self.button_trigger)
        self.ratio.editingFinished.connect(self.editing_finished)
        
        self.set_status.connect( self.laser_device.set_power_status   )
        if hasattr(self.laser_device,'power_ratio'):
            self.set_power.connect ( self.laser_device.set_power_ratio )
        else:
            self.set_power.connect ( self.laser_device.set_power_value )
        
    def _create_vertical_layout(self,list_widgets):
        layout = QGridLayout()
        for i,widget in enumerate(list_widgets):
            layout.addWidget(widget,i,0)
        self.setLayout(layout)
        
    def _create_horizontal_layout(self,list_widgets):
        layout = QGridLayout()
        for i,widget in enumerate(list_widgets):
            if i == 0:
                layout.addWidget(widget,0,0,1,len(list_widgets))
            else:
                layout.addWidget(widget,1,i-1)
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
        
        self.colorbar = QLabel()
        self.colorbar.setFixedHeight(7)
        self.colorbar.setStyleSheet(colorbar_style_sheet(hex_color))
        
        layout.addWidget(title,0,Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self.colorbar,1,Qt.AlignmentFlag.AlignVCenter)
        
        widget.setLayout(layout)
        return widget
    
    def create_percentage(self,icon,spin_box):
        widget = QWidget()
        layout = QHBoxLayout()
        layout.setContentsMargins(0,0,0,0)
        
        # spin_box.setRange(0,100)
        # spin_box.setValue(0)
        # spin_box.setDecimals(2)
        # spin_box.setSuffix('%')
        
        icon_tmp = QLabel()
        icon_tmp.setPixmap(icon.pixmap(24,24))
        
        layout.addWidget(icon_tmp,0,Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(spin_box,1,Qt.AlignmentFlag.AlignVCenter)
        
        widget.setLayout(layout)
        return widget
    
    @pyqtSlot()
    def editing_finished(self):
        value = self.ratio.value()
        self.set_power.emit(self.device_id,value)
    
    @pyqtSlot()
    def button_trigger(self):
        if self.is_laser_on:
            update_iconized_button(self.power_button,_g_icon_prov.light_bulb_on,'Turn on')
            self.is_laser_on = False
        else:
            update_iconized_button(self.power_button,_g_icon_prov.light_bulb_off,'Turn off')
            self.is_laser_on = True
        self.colorbar.setEnabled(self.is_laser_on)
        self.set_status.emit(self.device_id,self.is_laser_on)

# ############################################################################### LaserWidget

# class LaserWidget(QWidget):
#     turn_on  = pyqtSignal(int)
#     turn_off = pyqtSignal(int)
#     set_pwm_percentage = pyqtSignal(int,float)
    
#     def __init__(self,manager,device,name,vertical=True,*args,**kwargs):
#         super().__init__(*args,**kwargs)
        
#         self.device = device
#         self.name   = name
#         self.is_laser_on = False
        
#         self.percentage = QDoubleSpinBox()
#         self.percentage.setRange(0,100)
#         self.percentage.setValue(0)
#         self.percentage.setDecimals(2)
#         self.percentage.setSuffix('%')
#         self.percentage.editingFinished.connect(self.editing_finished)
                
#         self.button = QPushButton(f"Turn on\n{self.name}")
#         self.button.clicked.connect(self.button_trigger)
        
#         if vertical:
#             layout = QVBoxLayout()
#             layout.addWidget(self.percentage)
#             layout.addWidget(self.button)
            
#         else:
#             layout = QHBoxLayout()
#             layout.addWidget(self.button)
#             layout.addWidget(self.percentage)
            
#         self.setLayout(layout)
        
#         self.turn_on.connect ( manager.turn_on  )
#         self.turn_off.connect( manager.turn_off )
#         self.set_pwm_percentage.connect( manager.set_pwm_percentage )
    
#     def editing_finished(self):
#         value = self.percentage.value()
#         if value >= 0 and value <= 100.0:
#             self.set_pwm_percentage.emit(self.device,value)
    
#     def button_trigger(self):
#         if self.is_laser_on:
#             self.turn_off.emit(self.device)
#             self.button.setText(f"Turn on\n{self.name}")
#             self.is_laser_on = False
#         else:
#             self.turn_on.emit(self.device)
#             self.button.setText(f"Turn off\n{self.name}")
#             self.is_laser_on = True
            
############################################################################### PwmWidget

class PwmWidget(QWidget):
    set_power_status  = pyqtSignal(int,bool)
    
    def __init__(self,laser_device,laser_name,laser_color,device_id=0,vertical=True,parent=None):
        super().__init__(parent)
        self.laser  = laser_device
        self.name   = laser_name
        self.device = device_id
        #self.button = QPushButton(f"Start pulsing\n{self.name}")
        self.button = create_iconized_button(_g_icon_prov.square_wave,f'Start pulsing\n{self.name}')
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
            self.colorbar = QLabel()
            self.colorbar.setFixedHeight(5)
            self.colorbar.setStyleSheet(colorbar_style_sheet(laser_color))
            
            layout = QVBoxLayout()
            layout.setContentsMargins(0,0,0,0)
            layout.addWidget(form_widget,1)
            layout.addWidget(self.button,1)
            layout.addWidget(self.colorbar,0)
            
        else:
            self.colorbar = QLabel()
            self.colorbar.setFixedHeight(5)
            self.colorbar.setStyleSheet(colorbar_style_sheet(laser_color))
            button_widget = QWidget()
            button_layout = QVBoxLayout()
            button_layout.addWidget(self.button,1)
            button_layout.addWidget(self.colorbar,0)
            button_widget.setLayout(button_layout)

            layout = QHBoxLayout()
            layout.setContentsMargins(0,0,0,0)
            layout.addWidget(button_widget)
            layout.addWidget(form_widget)
        
        
        self.setLayout(layout)
        
        self.status_on = False
        self.colorbar.setEnabled(self.status_on)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.timer_triggered)
        
        self.set_power_status.connect( self.laser.set_power_status )

    def timer_triggered(self):
        if self.status_on:
            # If the laser is ON and the timer timed-out:
            # - Turn off the laser
            # - Start the timer with OFF time
            self.set_power_status.emit(self.device,False)
            self.status_on = False
            self.timer.start( int(self.time_off.value()*1e3) )
        else:
            # If the laser is OFF and the timer timed-out:
            # - Turn ob the laser
            # - Start the timer with ON time
            self.set_power_status.emit(self.device,True)
            self.timer.start( int(self.time_on.value()*1e3) )
            self.status_on = True
        self.colorbar.setEnabled(self.status_on)

    def button_trigger(self):
        if self.timer.isActive():
            # If we click the button and the timer is active:
            # - Stop the timer
            # - Set the button to start the PWM again
            # - Allow users to change the PWM parameters
            self.timer.stop()
            update_iconized_button(self.button,_g_icon_prov.square_wave,f'Start pulsing\n{self.name}')
            self.time_on.setEnabled(True)
            self.time_off.setEnabled(True)
            self.status_on = False
        else:
            # If we click the button and the timer is not active:
            # - Turn on laser
            # - Start the timer with ON time
            # - Set the button to stop the PWM
            # - Do not allow users to change the PWM parameters
            self.status_on = True
            self.timer.start( int(self.time_on.value()*1e3) )
            update_iconized_button(self.button,_g_icon_prov.continuous_wave,f'Stop pulsing\n{self.name}')
            self.time_on.setEnabled(False)
            self.time_off.setEnabled(False)
        self.set_power_status.emit(self.device,self.status_on)
        self.colorbar.setEnabled(self.status_on)
            

