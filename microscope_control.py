import sys
from PyQt5.QtWidgets import QApplication, QWidget, QMainWindow
from PyQt5.QtWidgets import QVBoxLayout, QHBoxLayout, QMessageBox, QSplitter
from PyQt5.QtCore import Qt
from hardware import AttoCom,HamamatsuCamera,DummyCamera
from gui import StageWidget, IconProvider, CameraWidget


import qtmodern.styles

def custom_assert_handler(exc_type, exc_value, exc_traceback):
    if exc_type == AssertionError:
        QMessageBox.critical(None, "Assertion Failed", str(exc_value))
        sys.exit(1)

sys.excepthook = custom_assert_handler

class MainWindow(QMainWindow):
    
    def __init__(self):
        super().__init__()

        self.setWindowTitle("CryoSResCLEMcontrol")
        
        ########################################################### TOP
        
        self.main_cam   = HamamatsuCamera("Main_Camera")
        main_cam_widget = CameraWidget(self.main_cam,"Main")
        
        # self.aux_cam   = DummyCamera("Aux_Camera")
        # aux_cam_widget = CameraWidget(self.aux_cam,"Auxiliar")
        
        top_widget   = QWidget(self)
        top_layout   = QHBoxLayout()
        top_splitter = QSplitter(Qt.Horizontal)
        
        top_splitter.addWidget(main_cam_widget)
        # top_splitter.addWidget(aux_cam_widget)
        top_layout.addWidget(top_splitter)
        top_widget.setLayout(top_layout)
        
        ########################################################### BOTTOM
        
        self.stage_driver = AttoCom(com_port='COM5')
        self.stage_driver.show_commands = True
        self.stage_driver.set_mode_mixed(1)
        self.stage_driver.set_mode_mixed(2)
        self.stage_driver.set_mode_mixed(3)
        self.stage_driver.positioning_fine_absolute(1,75)
        self.stage_driver.positioning_fine_absolute(2,75)
        self.stage_driver.positioning_fine_absolute(3,75)
        
        stage_widget = StageWidget(self.stage_driver,"AttoCube")
        
        bottom_widget = QWidget(self)
        bottom_layout = QHBoxLayout()
        
        bottom_layout.addStretch(0)
        bottom_layout.addWidget(stage_widget)
        bottom_widget.setLayout(bottom_layout)
        
        ###########################################################s
        
        # Main central widget
        main_widget = QWidget(self)
        layout      = QVBoxLayout()
        splitter    = QSplitter(Qt.Vertical)

        
        splitter.addWidget(top_widget)
        splitter.addWidget(bottom_widget)
        
        layout.addWidget(splitter)
        main_widget.setLayout(layout)
        self.setCentralWidget(main_widget)
        
        self.resize(2000,1200)
    
    def closeEvent(self, event):
        print('Close Event??')
        self.stage_driver.set_mode_ground(1)
        self.stage_driver.set_mode_ground(2)
        self.stage_driver.set_mode_ground(3)
        
        self.main_cam.stop_acquisition()
        event.accept()
    
    def __del__(self):
        #self.stage_driver.about_to_quit()
        print('lalala')
        
app = QApplication.instance()  # Check if QApplication is already running
if not app:  
    app = QApplication(sys.argv)

qtmodern.styles.dark(app)

icon_prov = IconProvider()
icon_prov.load_dark_mode()

window = MainWindow()

window.show()
app.exec_()

# %%