import sys
from PyQt5.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout, QMainWindow, QSlider, QPushButton, QMessageBox
from PyQt5.QtGui import QPainter, QColor
from PyQt5.QtCore import Qt, QSize, pyqtSignal

import qtmodern.styles
from gui.ui_utils import IconProvider

from hardware import DeviceManager
from hardware import DummyLaser
from hardware import MicroFPGALaser
# from hardware import DummyLaser
from hardware import TopticaIBeamLaser
from hardware import OmicronLaser_PycroManager
from hardware import FilterWheel
# from hardware import LaserDeviceBase
#from gui import LaserVerticalWidget,LaserHorizontalWidget,LaserWidget,PwmWidget,FilterWheelWidget
from gui import LaserWidget,FilterWheelWidget,PwmWidget

# def custom_assert_handler(exc_type, exc_value, exc_traceback):
#     if exc_type == AssertionError:
#         app = QApplication.instance() or QApplication(sys.argv)  # Ensure QApplication exists
#         QMessageBox.critical(None, "Assertion Failed", str(exc_value))
#         sys.exit(1)  # Optional: exit the app after showing the message box

# # Override default exception handler
# sys.excepthook = custom_assert_handler


class MainWindow(QMainWindow):
    
    def __init__(self):
        super().__init__()
        
        self.dev_manager = DeviceManager()
        
        # self.filterwheel = FilterWheel()
        # self.filterwheel.start()
        
        
        self.setWindowTitle("Lasers")
        # self.setGeometry(100, 100, 200, 400)

        # Main central widget
        main_widget = QWidget()
        layout = QVBoxLayout()
        
        self.laser_405 = MicroFPGALaser('Laser405') # uFPGA
        self.laser_488 = TopticaIBeamLaser('Laser488') # Toptica iBeam
        self.laser_561 = DummyLaser('Laser561') # TBD
        self.laser_640 = OmicronLaser_PycroManager('Laser640') # Omicron PycroManager
        
        self.filterwheel = FilterWheel('FilterWheel')
        
        self.dev_manager.add(self.laser_405)
        self.dev_manager.add(self.laser_488)
        self.dev_manager.add(self.laser_561)
        self.dev_manager.add(self.laser_640)
        self.dev_manager.add(self.filterwheel)
        
        laser_405 = LaserWidget(self.laser_405,'405 nm','#C8B3E1',vertical=False)
        laser_488 = LaserWidget(self.laser_488,'488 nm','#B7FFFA',vertical=False)
        laser_561 = LaserWidget(self.laser_561,'561 nm','#FDFC96',vertical=False)
        laser_640 = LaserWidget(self.laser_640,'640 nm','#FF746C',vertical=False)
        
        pwm = PwmWidget(self.laser_405,'405 nm','#C8B3E1',vertical=False)
        
        fw_names  = ('520/35','530/30','585/40','617/50','692/50','none')
        fw_colors = ('#E07070','#70E070','#E07070','#70E070','#E07070','#70E070')
        filterwheel = FilterWheelWidget(self.filterwheel,'Filter Wheel',fw_names,fw_colors)
        
        layout.addWidget(laser_405)
        layout.addWidget(laser_488)
        layout.addWidget(laser_561)
        layout.addWidget(laser_640)
        
        layout.addWidget(pwm)
        
        layout.addWidget(filterwheel)
        
        # pwm_widget = PwmWidget(self.ufpga  ,0,"405 nm",vertical=False)
        # layout.addWidget(pwm_widget)
        
        main_widget.setLayout(layout)
        self.setCentralWidget(main_widget)
        
    def closeEvent(self,event):
        self.dev_manager.free()
        event.accept()
        
from core.utils import create_dark_iconoir

create_dark_iconoir()

app = QApplication.instance()  # Check if QApplication is already running
if not app:  
    app = QApplication(sys.argv)

icon_prov = IconProvider()
icon_prov.load_dark_mode()

qtmodern.styles.dark(app)

window = MainWindow()
window.show()
app.exec_()

# %%