import sys
from PyQt5.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout, QMainWindow, QSlider, QPushButton, QMessageBox
from PyQt5.QtGui import QPainter, QColor
from PyQt5.QtCore import Qt, QSize, pyqtSignal

from hardware import MicroFpga
from hardware import DummyLaser
from hardware import TopticaLaser
from hardware import OmicronLaser
from hardware import FilterWheel
from gui import LaserWidget,PwmWidget,FilterWheelWidget

def custom_assert_handler(exc_type, exc_value, exc_traceback):
    if exc_type == AssertionError:
        app = QApplication.instance() or QApplication(sys.argv)  # Ensure QApplication exists
        QMessageBox.critical(None, "Assertion Failed", str(exc_value))
        sys.exit(1)  # Optional: exit the app after showing the message box

# Override default exception handler
sys.excepthook = custom_assert_handler


class MainWindow(QMainWindow):
    
    def __init__(self):
        super().__init__()

        self.ufpga = MicroFpga()
        self.ufpga.start()

        self.omicron = OmicronLaser()
        self.omicron.start()
        
        self.toptica = TopticaLaser()
        self.toptica.start()
        
        self.dummy = DummyLaser()
        self.dummy.start()
        
        self.filterwheel = FilterWheel()
        self.filterwheel.start()
        
        self.setWindowTitle("Lasers")
        self.setGeometry(100, 100, 200, 400)

        # Main central widget
        main_widget = QWidget()
        layout = QVBoxLayout()
        
        laser_405 = LaserWidget(self.ufpga  ,0,"405 nm",vertical=False)
        laser_488 = LaserWidget(self.toptica,0,"488 nm",vertical=False)
        laser_561 = LaserWidget(self.dummy  ,0,"561 nm",vertical=False)
        laser_640 = LaserWidget(self.omicron,0,"640 nm",vertical=False)
        
        layout.addWidget(laser_405)
        layout.addWidget(laser_488)
        layout.addWidget(laser_561)
        layout.addWidget(laser_640)
        
        pwm_widget = PwmWidget(self.ufpga  ,0,"405 nm",vertical=False)
        layout.addWidget(pwm_widget)
        
        fw_widget = FilterWheelWidget(self.filterwheel,vertical=False)
        layout.addWidget(fw_widget)
        
        main_widget.setLayout(layout)
        self.setCentralWidget(main_widget)
        


app = QApplication.instance()  # Check if QApplication is already running
if not app:  
    app = QApplication(sys.argv)

window = MainWindow()
window.show()
app.exec_()

# %%