import sys
from PyQt5.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout, QMainWindow, QSlider, QPushButton, QMessageBox
from PyQt5.QtGui import QPainter, QColor
from PyQt5.QtCore import Qt, QSize, pyqtSignal, QThread

from hardware import HamamatsuCamera
from gui import CameraWidget, IconProvider
from core.utils import create_dark_iconoir

import qtmodern.styles

# def custom_assert_handler(exc_type, exc_value, exc_traceback):
#     if exc_type == AssertionError:
#         app = QApplication.instance() or QApplication(sys.argv)  # Ensure QApplication exists
#         QMessageBox.critical(None, "Assertion Failed", str(exc_value))
#         sys.exit(1)  # Optional: exit the app after showing the message box

# # Override default exception handler
# sys.excepthook = custom_assert_handler

# import qdarkstyle

class MainWindow(QMainWindow):
    
    def __init__(self):
        super().__init__()

        self.hcam_th = QThread()
        self.hcam = HamamatsuCamera("Main_Camera")
        
        self.setWindowTitle("Camera")
        self.setGeometry(1000, 100, 800, 800)

        # Main central widget
        main_widget = QWidget()
        layout = QVBoxLayout()
        
        hcam_widget = CameraWidget(self.hcam,"Main")
        
        layout.addWidget(hcam_widget)
        main_widget.setLayout(layout)
        self.setCentralWidget(main_widget)
    
    def closeEvent(self, event):
        self.hcam.stop_acquisition()
        event.accept()
        
create_dark_iconoir()

icon_prov = IconProvider()
icon_prov.set_dark_mode()

app = QApplication.instance()  # Check if QApplication is already running
if not app:  
    app = QApplication(sys.argv)

qtmodern.styles.dark(app)

# app.setStyleSheet(qdarkstyle.load_stylesheet_pyqt5())
# app.setStyleSheet(qdarkstyle.load_stylesheet(qt_api='pyqt5'))


window = MainWindow()



window.show()
app.exec_()

# %%