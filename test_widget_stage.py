import sys
from PyQt5.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout, QMainWindow, QSlider, QPushButton, QMessageBox
from PyQt5.QtGui import QPainter, QColor
from PyQt5.QtCore import Qt, QSize, pyqtSignal, QThread

from hardware import AttoCom
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
        main_widget = QWidget(self)
        layout = QVBoxLayout()
        
        self.stage_driver = AttoCom(com_port='COM5')
        self.stage_driver.show_commands = True
        self.stage_driver.set_mode_mixed(1)
        self.stage_driver.set_mode_mixed(2)
        self.stage_driver.set_mode_mixed(3)
        self.stage_driver.positioning_fine_absolute(1,75)
        self.stage_driver.positioning_fine_absolute(2,75)
        self.stage_driver.positioning_fine_absolute(3,75)
        
        stage_widget = StageWidget(self.stage_driver,"AttoCube")
        
        layout.addWidget(stage_widget)
        main_widget.setLayout(layout)
        self.setCentralWidget(main_widget)
        
    def __del__(self):
        #self.stage_driver.about_to_quit()
        print('lalala')
        
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