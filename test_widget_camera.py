import sys
from PyQt5.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout, QMainWindow, QSlider, QPushButton, QMessageBox
from PyQt5.QtGui import QPainter, QColor
from PyQt5.QtCore import Qt, QSize, pyqtSignal, QThread

from hardware import HamamatsuCamera,DummyCamera,PySpinCamera
from gui import CameraWidget, IconProvider
from core.utils import create_dark_iconoir

import qtmodern.styles

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

        # self.hcam = HamamatsuCamera("Main_Camera")
        # self.hcam = DummyCamera("Main_Camera")
        try:
            self.hcam = PySpinCamera("Aux_Camera")
        except Exception as e: print('Ctor',e)
        
        self.setWindowTitle("Camera")
        self.setGeometry(1000, 100, 800, 800)

        # Main central widget
        main_widget = QWidget()
        layout = QVBoxLayout()
        
        self.hcam_widget = CameraWidget(self.hcam,"Main")
        self.hcam_widget.img2qimg.do_rot180 = True
        
        layout.addWidget(self.hcam_widget)
        main_widget.setLayout(layout)
        self.setCentralWidget(main_widget)
    
    def closeEvent(self, event):
        self.hcam.stop_acquisition()
        self.hcam_widget.free()
        event.accept()
        
create_dark_iconoir()

app = QApplication.instance()  # Check if QApplication is already running
if not app:  
    app = QApplication(sys.argv)

qtmodern.styles.dark(app)

# app.setStyleSheet(qdarkstyle.load_stylesheet_pyqt5())
# app.setStyleSheet(qdarkstyle.load_stylesheet(qt_api='pyqt5'))

icon_prov = IconProvider()
icon_prov.load_dark_mode()

window = MainWindow()



window.show()
app.exec_()

# %%