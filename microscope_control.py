import sys
from PyQt5.QtWidgets import QApplication, QWidget, QMainWindow
from PyQt5.QtWidgets import QMessageBox, QSplitter, QGroupBox, QTabWidget
from PyQt5.QtWidgets import QVBoxLayout, QHBoxLayout, QGridLayout
from PyQt5.QtWidgets import QLineEdit,QLabel,QFileDialog
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon

from hardware import DeviceManager
from hardware import DummyLaser
from hardware import DummyFilterWheel
from hardware import AttoCom,HamamatsuCamera,DummyCamera,DummyStage

from gui import StageWidget, IconProvider, CameraWidget, LaserWidget,FilterWheelWidget,PwmWidget
from gui import create_iconized_button

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
        
        self.dev_manager = DeviceManager()
        
        ########################################################### TOP
        
        self.main_cam   = HamamatsuCamera("Main_Camera")
        self.main_cam_widget = CameraWidget(self.main_cam,"Main")
        
        self.aux_cam   = DummyCamera("Aux_Camera")
        self.aux_cam_widget = CameraWidget(self.aux_cam,"Auxiliar")
        
        top_widget   = QWidget(self)
        top_layout   = QHBoxLayout()
        top_splitter = QSplitter(Qt.Horizontal)
        
        top_splitter.addWidget(self.main_cam_widget)
        top_splitter.addWidget(self.aux_cam_widget)
        top_layout.addWidget(top_splitter)
        top_widget.setLayout(top_layout)
        
        ########################################################### BOTTOM
        
        commands     = self._create_commands()
        lasers       = self._create_lasers()
        pwm          = self._create_pwm()
        filter_wheel = self._create_filterwheel()
        stage        = self._create_stage()
        
        block_widget = QWidget()
        block_layout = QVBoxLayout()
        block_layout.setContentsMargins(0,0,0,0)
        block_layout.addWidget(pwm)
        block_layout.addWidget(filter_wheel)
        block_widget.setLayout(block_layout)
        
        bottom_widget = QWidget(self)
        bottom_layout = QHBoxLayout()
        bottom_layout.setContentsMargins(0,0,0,0)
        
        bottom_layout.addWidget(commands,1)
        bottom_layout.addWidget(lasers,0)
        bottom_layout.addWidget(block_widget,0)
        bottom_layout.addWidget(stage,0)
        
        bottom_widget.setLayout(bottom_layout)
        
        ###########################################################s
        
        # Main central widget
        main_widget = QWidget(self)
        layout      = QVBoxLayout()
        splitter    = QSplitter(Qt.Vertical)

        
        splitter.addWidget(top_widget)
        splitter.addWidget(bottom_widget)
        splitter.setStretchFactor(0,1)
        splitter.setStretchFactor(1,0)
        
        layout.addWidget(splitter)
        main_widget.setLayout(layout)
        self.setCentralWidget(main_widget)
        
        self.resize(2000,1200)
        
    def closeEvent(self, event):
        self.main_cam.stop_acquisition()
        self.aux_cam.stop_acquisition()
        self.dev_manager.free()
        self.main_cam_widget.free()
        self.aux_cam_widget.free()
        event.accept()
        
    def _create_commands(self):
        icon_prov = IconProvider()
        
        widget = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(0,0,0,0)
        
        ###########################################################
        
        folder_widget = QWidget()
        folder_layout = QHBoxLayout()
        folder_layout.setContentsMargins(5,5,5,5)
        
        from os import getcwd
        self.folder = QLineEdit()
        self.set_folder( getcwd() )
        folder_button = create_iconized_button(icon_prov.folder,tooltip='Select folder...')
        folder_button.clicked.connect(lambda: self.set_folder( QFileDialog.getExistingDirectory(self,'Select working folder') ) )
        
        folder_layout.addWidget(QLabel('Working directory: '),0)
        folder_layout.addWidget(self.folder,1)
        folder_layout.addWidget(folder_button,0)
        
        folder_widget.setLayout(folder_layout)
        
        ###########################################################
        
        self.cmd_widget = QTabWidget()
        # cmd_widget.setContentsMargins(0,0,0,0)
        
        self.cmd_widget.addTab(self._focus_lock(),'Focus Lock')
        self.cmd_widget.addTab(self._z_sweep_coarse(),'Z-sweep coarse')
        self.cmd_widget.addTab(self._z_sweep_fine(),'Z-sweep fine')
        
        ###########################################################
        
        layout.addWidget(folder_widget,0)
        layout.addWidget(self.cmd_widget,1)
        
        widget.setLayout(layout)
        
        return widget
    
    def set_folder(self,working_dir):
        if working_dir:
            self.folder.setText(working_dir)
            self.update_folder()
        
    def update_folder(self):
        self.main_cam_widget.working_dir = self.folder.text()
        self.aux_cam_widget.working_dir = self.folder.text()
    
    def _focus_lock(self):
        widget = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(0,0,0,0)
        
        widget.setLayout(layout)
        return widget
    
    def _z_sweep_coarse(self):
        widget = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(0,0,0,0)
        
        widget.setLayout(layout)
        return widget

    def _z_sweep_fine(self):
        widget = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(0,0,0,0)
        
        widget.setLayout(layout)
        return widget
        
    def _create_lasers(self):
        laser_405 = DummyLaser('Laser405')
        laser_488 = DummyLaser('Laser488')
        laser_561 = DummyLaser('Laser561')
        laser_640 = DummyLaser('Laser640')
        
        self.dev_manager.add(laser_405)
        self.dev_manager.add(laser_488)
        self.dev_manager.add(laser_561)
        self.dev_manager.add(laser_640)
        
        widget = QGroupBox()
        layout = QGridLayout()
        layout.setContentsMargins(0,0,0,0)
        
        layout.addWidget(LaserWidget(laser_405,'405 nm','#C8B3E1',vertical=False),0,0)
        layout.addWidget(LaserWidget(laser_488,'488 nm','#B7FFFA',vertical=False),0,1)
        layout.addWidget(LaserWidget(laser_561,'561 nm','#FDFC96',vertical=False),1,0)
        layout.addWidget(LaserWidget(laser_640,'640 nm','#FF746C',vertical=False),1,1)
        
        widget.setTitle('Lasers')
        widget.setLayout(layout)
        
        return widget
    
    def _create_pwm(self):
        widget = QGroupBox()
        layout = QVBoxLayout()
        layout.setContentsMargins(0,0,0,0)
        
        layout.addWidget(PwmWidget(self.dev_manager.Laser405,'405 nm','#C8B3E1',vertical=False))
        
        widget.setTitle('PWM')
        widget.setLayout(layout)
        
        return widget
    
    def _create_filterwheel(self):
        widget = QGroupBox()
        layout = QVBoxLayout()
        layout.setContentsMargins(0,0,0,0)
        
        filterwheel = DummyFilterWheel('FilterWheel')
        self.dev_manager.add(filterwheel)
        
        names  = ('520/35','530/30','585/40','617/50','692/50','none')
        colors = ('#80EF80','#E5F489','#FFEE8C','#FF9D37','#FF6060','#BEBEBE')
        layout.addWidget(FilterWheelWidget(filterwheel,'Filter Wheel',names,colors,vertical=False))
        
        widget.setTitle('Filter Wheel')
        widget.setLayout(layout)
        
        return widget
    
    def _create_stage(self):
        widget = QGroupBox()
        layout = QVBoxLayout()
        layout.setContentsMargins(3,3,3,3)
        
        #stage_driver = AttoCom(com_port='COM5')
        stage_driver = DummyStage('Stage')
        stage_driver.show_commands = True
        stage_driver.set_mode_mixed(1)
        stage_driver.set_mode_mixed(2)
        stage_driver.set_mode_mixed(3)
        stage_driver.positioning_fine_absolute(1,75)
        stage_driver.positioning_fine_absolute(2,75)
        stage_driver.positioning_fine_absolute(3,75)
        
        self.dev_manager.add(stage_driver)
        layout.addWidget(StageWidget(stage_driver,"AttoCube"))
        
        widget.setTitle('Stage Controller')
        widget.setLayout(layout)
        
        return widget
    
app = QApplication.instance()  # Check if QApplication is already running
if not app:  
    app = QApplication(sys.argv)
qtmodern.styles.dark(app)
app.setWindowIcon( QIcon('resources/microscope.svg') )

icon_prov = IconProvider()
icon_prov.load_dark_mode()

window = MainWindow()

window.show()
app.exec_()

# %%