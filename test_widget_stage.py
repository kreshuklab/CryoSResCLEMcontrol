import sys
from PyQt5.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout, QMainWindow, QSlider, QPushButton, QMessageBox
from PyQt5.QtGui import QPainter, QColor
from PyQt5.QtCore import Qt, QSize, pyqtSignal, QThread

from hardware import HamamatsuCamera
from gui import StageWidget, IconProvider
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

        self.setWindowTitle("Stage")
        
        # Main central widget
        main_widget = QWidget()
        layout = QVBoxLayout()
        
        stage_widget = StageWidget(None,"AttoCube")
        
        layout.addWidget(stage_widget)
        main_widget.setLayout(layout)
        self.setCentralWidget(main_widget)
        
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