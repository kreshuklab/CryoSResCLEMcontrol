import os
os.environ["KMP_DUPLICATE_LIB_OK"]="TRUE"

import sys
from PyQt5.QtWidgets import QApplication, QWidget, QMainWindow
from PyQt5.QtWidgets import QMessageBox, QSplitter, QGroupBox, QTabWidget
from PyQt5.QtWidgets import QVBoxLayout, QHBoxLayout, QGridLayout, QFormLayout
from PyQt5.QtWidgets import QLineEdit,QLabel,QPushButton,QCheckBox,QComboBox
from PyQt5.QtWidgets import QFileDialog,QTableWidget,QHeaderView,QTableWidgetItem
from PyQt5.QtCore import Qt, pyqtSlot, pyqtSignal
from PyQt5.QtGui import QIcon

from hardware import DeviceManager
from hardware import DummyLaser,MicroFPGALaser,TopticaIBeamLaser,OmicronLaser_PycroManager
from hardware import FilterWheel, DummyFilterWheel
from hardware import AttoCubeStage, DummyStage
from hardware import HamamatsuCamera,PySpinCamera,DummyCamera

from gui import StageWidget,CameraWidget,LaserWidget,FilterWheelWidget,PwmWidget
from gui import IconProvider,create_iconized_button,create_spinbox,create_doublespinbox,update_iconized_button

from core import Worker, ZLock
from os.path import join,normpath

import numpy as np

import qtmodern.styles

def custom_assert_handler(exc_type, exc_value, exc_traceback):
    if exc_type == AssertionError:
        QMessageBox.critical(None, "Assertion Failed", str(exc_value))
        sys.exit(1)

sys.excepthook = custom_assert_handler

class MainWindow(QMainWindow):
    
    _start_z_coarse = pyqtSignal(int,int,str,str,float)
    _start_z_fine   = pyqtSignal(int,float,str,str,float)
    
    restart_main_live = pyqtSignal()
    restart_aux_live  = pyqtSignal()
    
    def __init__(self,dummies=False):
        super().__init__()
        self.dummies = dummies

        self.setWindowTitle("CryoSResCLEMcontrol")
        
        self.dev_manager = DeviceManager()
        
        ########################################################### TOP
        
        self.main_cam   = DummyCamera("Main_Camera") if self.dummies else HamamatsuCamera("Main_Camera")
        # self.main_cam   = DummyCamera("Main_Camera")
        self.main_cam_widget = CameraWidget(self.main_cam,"Main")
        self.main_cam_widget.img2tiff.dev_manager = self.dev_manager
        
        self.aux_cam   = DummyCamera("Aux_Camera") if self.dummies else PySpinCamera("Aux_Camera")
        # self.aux_cam   = DummyCamera("Aux_Camera")
        self.aux_cam_widget = CameraWidget(self.aux_cam,"Auxiliar")
        self.aux_cam_widget.img2qimg.do_rot180 = True
        self.aux_cam_widget.img2tiff.dev_manager = self.dev_manager
        
        top_widget   = QWidget(self)
        top_layout   = QHBoxLayout()
        top_splitter = QSplitter(Qt.Horizontal)
        
        top_splitter.addWidget(self.main_cam_widget)
        top_splitter.addWidget(self.aux_cam_widget)
        top_layout.addWidget(top_splitter)
        top_widget.setLayout(top_layout)
        
        ########################################################### BOTTOM
        
        self.wgt_commands     = self._create_commands()
        self.wgt_lasers       = self._create_lasers()
        self.wgt_pwm          = self._create_pwm()
        self.wgt_filter_wheel = self._create_filterwheel()
        self.wgt_stage        = self._create_stage()
        
        block_widget = QWidget()
        block_layout = QVBoxLayout()
        block_layout.setContentsMargins(0,0,0,0)
        block_layout.addWidget(self.wgt_pwm)
        block_layout.addWidget(self.wgt_filter_wheel)
        block_widget.setLayout(block_layout)
        
        bottom_widget = QWidget(self)
        bottom_layout = QHBoxLayout()
        bottom_layout.setContentsMargins(0,0,0,0)
        
        bottom_layout.addWidget(self.wgt_lasers,0)
        bottom_layout.addWidget(block_widget,0)
        bottom_layout.addWidget(self.wgt_stage,0)
        bottom_layout.addWidget(self.wgt_commands,1)
        
        bottom_widget.setLayout(bottom_layout)
        
        ###########################################################s
        
        self.restart_main_live.connect( self.main_cam_widget.clicked_live )
        self.restart_aux_live .connect( self.aux_cam_widget.clicked_live  )
        
        self.worker = Worker()
        self.worker.dev_manager = self.dev_manager
        self.worker.set_main_cam( self.main_cam_widget )
        self.worker.set_aux_cam ( self.aux_cam_widget  )
        self._start_z_coarse.connect( self.worker.start_coarse_z_sweep )
        self._start_z_fine.connect( self.worker.start_fine_z_sweep )
        
        ###########################################################
        
        self.z_locker = ZLock()
        self.z_locker.dev_manager = self.dev_manager
        self.z_locker.set_aux_cam( self.aux_cam_widget )
        
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
        
        self.folder_widget = QWidget()
        folder_layout = QHBoxLayout()
        folder_layout.setContentsMargins(5,5,5,5)
        
        from os import getcwd
        self.folder = QLineEdit()
        self.set_folder( getcwd() )
        folder_button = create_iconized_button(icon_prov.folder,tooltip='Select folder...')
        folder_button.clicked.connect(lambda: self.set_folder( QFileDialog.getExistingDirectory(self,'Select working folder') ) )
        
        self.focus_lock_button = create_iconized_button(icon_prov.lock_z,'Start focus lock') #QPushButton('Focus lock')
        self.focus_lock_button.clicked.connect( self.z_lock_start )
        
        folder_layout.addWidget(QLabel('Working directory: '),0)
        folder_layout.addWidget(self.folder,1)
        folder_layout.addWidget(folder_button,0)
        folder_layout.addSpacing(10)
        folder_layout.addWidget(self.focus_lock_button,0)
        
        self.folder_widget.setLayout(folder_layout)
        
        ###########################################################
        
        self.cmd_widget = QTabWidget()
        # cmd_widget.setContentsMargins(0,0,0,0)
        
        self.cmd_widget.addTab(self._z_sweep_coarse(),'Z-sweep coarse')
        self.cmd_widget.addTab(self._z_sweep_fine(),'Z-sweep fine')
        
        # self.cmd_widget.addTab(self._z_sweep(), 'Z-sweep')
        self.cmd_widget.addTab(self._create_navigator(), 'Navigator')
        
        ###########################################################
        
        # cmd_exec_widget = QWidget()
        # cmd_exec_layout = QHBoxLayout()
        # cmd_exec_layout.setContentsMargins(0,0,0,0)
        
        # self.cmd_exec_button = create_iconized_button(icon_prov.play,'Start script')
        
        # cmd_exec_layout.addStretch(1)
        # cmd_exec_layout.addWidget(self.cmd_exec_button,0)
        # cmd_exec_widget.setLayout(cmd_exec_layout)
        
        ###########################################################
        
        layout.addWidget(self.folder_widget,0)
        layout.addWidget(self.cmd_widget,1)
        # layout.addWidget(cmd_exec_widget,1)
        
        widget.setLayout(layout)
        
        return widget
    
    def set_folder(self,working_dir):
        if working_dir:
            self.folder.setText(working_dir)
            self.update_folder()
        
    def update_folder(self):
        self.main_cam_widget.working_dir = self.folder.text()
        self.aux_cam_widget.working_dir = self.folder.text()
        
    @pyqtSlot()
    def z_lock_start(self):
        icon_prov = IconProvider()
        
        self.z_locker.start()
        
        self.focus_lock_button.clicked.disconnect() 
        self.focus_lock_button.clicked.connect(self.z_lock_stop)
        update_iconized_button(self.focus_lock_button,icon_prov.square,'Stop focus lock')
        
    @pyqtSlot()
    def z_lock_stop(self):
        icon_prov = IconProvider()
        
        self.z_locker.stop()
        
        self.focus_lock_button.clicked.disconnect() 
        self.focus_lock_button.clicked.connect(self.z_lock_start)
        update_iconized_button(self.focus_lock_button,icon_prov.lock_z,'Start focus lock')
        
    def _z_sweep(self):
        widget = QWidget()
        widget.setProperty('command','z-sweep')
        self.zsweep_layout = QGridLayout()
        self.zsweep_layout.setContentsMargins(0,0,0,0)
        
        self.zsweep_n_steps    = create_spinbox(1,100,20)
        self.zsweep_type       = QComboBox()
        
        self.zsweep_use_main   = QCheckBox('Save Main camera')
        self.zsweep_use_aux    = QCheckBox('Save Auxiliar camera.')
        self.zsweep_delay      = create_doublespinbox(0,1,0.05,step=0.01)
        
        self.zsweep_use_main.setChecked(True)
        self.zsweep_use_aux .setChecked(True)
        self.zsweep_delay.setSuffix(' sec')
        self.zsweep_type.addItem('[Coarse] Step size (volts +/-):','coarse')
        self.zsweep_type.addItem('[Fine] Delta voltage (+/-):','fine')
        self.zsweep_type.setCurrentIndex(0)
        self.zsweep_type.currentIndexChanged.connect( self._z_sweep_change_type )
        
        self.zsweep_layout.addWidget(QLabel('Number of steps:'), 0,0)
        self.zsweep_layout.addWidget(self.zsweep_n_steps, 0,1)
        
        self.zsweep_layout.addWidget(self.zsweep_type, 1,0)
        if self.zsweep_type.currentIndex() == 0:
            self.zsweep_volts = create_spinbox(-100,100,20)
            self.zsweep_layout.addWidget(self.zsweep_volts, 1,1)
        else:
            self.zsweep_delta_v = create_doublespinbox(-15,15,0.1,step=0.1)
            self.zsweep_layout.addWidget(self.zsweep_delta_v, 1,1)
        
        self.zsweep_layout.addWidget(self.zsweep_use_main, 0,2)
        self.zsweep_layout.addWidget(self.zsweep_use_aux , 0,3)
        
        self.zsweep_layout.addWidget(QLabel('Delay step/save:'), 1,2)
        self.zsweep_layout.addWidget(self.zsweep_delay, 1,3)
        
        widget.setLayout(self.zsweep_layout)
        
        return widget
    
    @pyqtSlot(int)
    def _z_sweep_change_type(self,index):
        if index == 0:
            self.zsweep_layout.removeWidget( self.zsweep_delta_v )
            self.zsweep_volts = create_spinbox(-100,100,20)
            self.zsweep_layout.addWidget( self.zsweep_volts,1,1 )
        else:
            self.zsweep_layout.removeWidget( self.zsweep_volts )
            self.zsweep_delta_v = create_doublespinbox(-15,15,0.1,step=0.1)
            self.zsweep_layout.addWidget( self.zsweep_delta_v,1,1 )
        self.zsweep_layout.update()
    
    
    def _z_sweep_coarse(self):
        widget = QWidget()
        layout = QHBoxLayout()
        layout.setContentsMargins(0,0,0,0)

        params_widget = QWidget()
        params_layout = QFormLayout()
        
        self.z_coarse_n_steps  = create_spinbox(1,100,20)
        self.z_coarse_volts    = create_spinbox(-100,100,20)
        self.z_coarse_use_main = QCheckBox('Save Main camera')
        self.z_coarse_use_aux  = QCheckBox('Save Auxiliar camera.')
        self.z_coarse_use_main.setChecked(True)
        self.z_coarse_use_aux .setChecked(True)
        self.z_coarse_delay    = create_doublespinbox(0,1,0.05,step=0.01)
        self.z_coarse_delay.setSuffix(' sec')
        self.z_coarse_button   = QPushButton('Start Z-sweep')
        self.z_coarse_button.clicked.connect(self.coarse_z_start)
        
        params_layout.addRow( 'Number of steps:'  , self.z_coarse_n_steps  )
        params_layout.addRow( 'Step size (volts +/-):', self.z_coarse_volts    )
        params_layout.addRow( self.z_coarse_use_main, self.z_coarse_use_aux )
        params_layout.addRow( 'Delay between step and save: ', self.z_coarse_delay  )
        params_layout.addRow( self.z_coarse_button  )

        params_widget.setLayout(params_layout)

        buttons_widget = QWidget()
        buttons_layout = QVBoxLayout()

        buttons_layout.addStretch(1)
        buttons_widget.setLayout(buttons_layout)
        
        layout.addWidget(params_widget)
        layout.addWidget(buttons_widget)
        widget.setLayout(layout)
        return widget
    
    @pyqtSlot()
    def coarse_z_start(self):
        if self.z_coarse_use_main.isChecked():
            self.main_cam_widget.stop_acquisition()
        
        if self.z_coarse_use_aux.isChecked():
            self.aux_cam_widget.stop_acquisition()
        
        self.z_coarse_button.clicked.disconnect() 
        self.z_coarse_button.clicked.connect(self.coarse_z_stop)
        self.z_coarse_button.setText('Stop Z-sweep')
        
        self.main_cam_widget.setEnabled(False)
        self.aux_cam_widget.setEnabled(False)
        self.wgt_lasers.setEnabled(False)
        self.wgt_pwm.setEnabled(False)
        self.wgt_filter_wheel.setEnabled(False)
        self.wgt_stage.setEnabled(False)
        self.folder_widget.setEnabled(False)
        
        try: self.worker.done.disconnect() 
        except Exception: pass
        self.worker.done.connect( self.coarse_z_finished )
        
        n_steps = self.z_coarse_n_steps.value()
        volts   = self.z_coarse_volts.value()
        delay   = self.z_coarse_delay.value()
        main_file = ''
        if self.z_coarse_use_main.isChecked():
            file = self.main_cam_widget.filename.text()
            if file:
                main_file = normpath(join(self.folder.text(),file))
        aux_file = ''
        if self.z_coarse_use_aux.isChecked():
            file = self.aux_cam_widget.filename.text()
            if file:
                aux_file = normpath(join(self.folder.text(),file))

        self._start_z_coarse.emit(n_steps,volts,main_file,aux_file,delay)

    @pyqtSlot()
    def coarse_z_stop(self):
        self.worker.should_process = False
        
    @pyqtSlot()
    def coarse_z_finished(self):
        self.z_coarse_button.clicked.disconnect() 
        self.z_coarse_button.clicked.connect(self.coarse_z_start)
        self.z_coarse_button.setText('Start Z-sweep')
        
        self.main_cam_widget.setEnabled(True)
        self.aux_cam_widget.setEnabled(True)
        self.wgt_lasers.setEnabled(True)
        self.wgt_pwm.setEnabled(True)
        self.wgt_filter_wheel.setEnabled(True)
        self.wgt_stage.setEnabled(True)
        self.folder_widget.setEnabled(True) 
        
        if self.main_was_live:
           self.restart_main_live.emit() 
           self.main_was_live = False

        if self.aux_was_live:
           self.restart_aux_live.emit()
           self.aux_was_live = False

    def _z_sweep_fine(self):
        
        widget = QWidget()
        layout = QHBoxLayout()
        layout.setContentsMargins(0,0,0,0)
        
        params_widget = QWidget()
        params_layout = QFormLayout()
        
        self.z_fine_n_steps  = create_spinbox(1,100,20)
        self.z_fine_volts    = create_doublespinbox(-15,15,0.1,step=0.1)
        self.z_fine_use_main = QCheckBox('Save Main camera')
        self.z_fine_use_aux  = QCheckBox('Save Auxiliar camera.')
        self.z_fine_use_main.setChecked(True)
        self.z_fine_use_aux .setChecked(True)
        self.z_fine_delay    = create_doublespinbox(0,1,0.05,step=0.01)
        self.z_fine_delay.setSuffix(' sec')
        self.z_fine_button   = QPushButton('Start Z-sweep')
        self.z_fine_button.clicked.connect(self.fine_z_start)
        
        params_layout.addRow( 'Number of steps:'  , self.z_fine_n_steps  )
        params_layout.addRow( 'Delta voltage (+/-):', self.z_fine_volts    )
        params_layout.addRow( self.z_fine_use_main, self.z_fine_use_aux )
        params_layout.addRow( 'Delay between step and save: ', self.z_fine_delay  )
        params_layout.addRow( self.z_fine_button  )

        params_widget.setLayout(params_layout)

        buttons_widget = QWidget()
        buttons_layout = QVBoxLayout()

        buttons_layout.addStretch(1)
        buttons_widget.setLayout(buttons_layout)
        
        layout.addWidget(params_widget)
        layout.addWidget(buttons_widget)
        
        widget.setLayout(layout)
        return widget
    
    @pyqtSlot()
    def fine_z_start(self):
        if self.z_fine_use_main.isChecked():
            self.main_was_live = self.main_cam.do_image
            self.main_cam_widget.stop_acquisition()
        
        if self.z_fine_use_aux.isChecked():
            self.aux_was_live = self.aux_cam.do_image
            self.aux_cam_widget.stop_acquisition()
        
        self.z_fine_button.clicked.disconnect() 
        self.z_fine_button.clicked.connect(self.fine_z_stop)
        self.z_fine_button.setText('Stop Z-sweep')
        
        self.main_cam_widget.setEnabled(False)
        self.aux_cam_widget.setEnabled(False)
        self.wgt_lasers.setEnabled(False)
        self.wgt_pwm.setEnabled(False)
        self.wgt_filter_wheel.setEnabled(False)
        self.wgt_stage.setEnabled(False)
        self.folder_widget.setEnabled(False)
        
        try: self.worker.done.disconnect() 
        except Exception: pass
        self.worker.done.connect( self.fine_z_finished )
        
        n_steps = self.z_fine_n_steps.value()
        volts   = self.z_fine_volts.value()
        delay   = self.z_fine_delay.value()
        main_file = ''
        if self.z_fine_use_main.isChecked():
            file = self.main_cam_widget.filename.text()
            if file:
                main_file = normpath( join(self.folder.text(),file) )
        aux_file = ''
        if self.z_fine_use_aux.isChecked():
            file = self.aux_cam_widget.filename.text()
            if file:
                aux_file = normpath( join(self.folder.text(),file) )
        
        self._start_z_fine.emit(n_steps,volts,main_file,aux_file,delay)

    @pyqtSlot()
    def fine_z_stop(self):
        self.worker.should_process = False
        
    @pyqtSlot()
    def fine_z_finished(self):
        self.z_fine_button.clicked.disconnect() 
        self.z_fine_button.clicked.connect(self.fine_z_start)
        self.z_fine_button.setText('Start Z-sweep')
        
        self.main_cam_widget.setEnabled(True)
        self.aux_cam_widget.setEnabled(True)
        self.wgt_lasers.setEnabled(True)
        self.wgt_pwm.setEnabled(True)
        self.wgt_filter_wheel.setEnabled(True)
        self.wgt_stage.setEnabled(True)
        self.folder_widget.setEnabled(True) 
        
        if self.main_was_live:
           self.restart_main_live.emit() 
           self.main_was_live = False

        if self.aux_was_live:
           self.restart_aux_live.emit() 
           self.aux_was_live = False
    
    def _create_navigator(self):
        widget = QWidget()
        widget.setProperty('command','navigator')
        layout = QVBoxLayout()
        layout.setContentsMargins(1,1,1,1)
        
        self.nav_table = QTableWidget()
        
        self.nav_table.setColumnCount(4)
        self.nav_table.setHorizontalHeaderLabels(('Name','X (steps)','Y (steps)','Z (steps)'))
        self.nav_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch) 
        self.nav_table.cellChanged.connect(self.nav_renamed)
        
        self.nav_count_id = 0
        
        nav_add  = QPushButton('Add Position')
        nav_rmv  = QPushButton('Remove')
        nav_goto = QPushButton('Go To')
        nav_save = QPushButton('Save Table')
        
        nav_add .clicked.connect(self.nav_add)
        nav_rmv .clicked.connect(self.nav_remove)
        nav_goto.clicked.connect(self.nav_goto)
        nav_save.clicked.connect(self.nav_save)
        
        button_box = QWidget()
        button_box.setLayout( QHBoxLayout() )
        button_box.layout().setContentsMargins(1,1,1,1)
        button_box.layout().addWidget(nav_add )
        button_box.layout().addWidget(nav_rmv )
        button_box.layout().addWidget(nav_goto)
        button_box.layout().addWidget(nav_save)
        
        layout.addWidget(self.nav_table)
        layout.addWidget(button_box)
        
        widget.setLayout(layout)
        return widget
    
    def nav_get_data(self,row_index):
        if row_index < 0:
            return None
        entry_type = self.nav_table.item(row_index,0).text()
        pos_x = int(self.nav_table.item(row_index,1).text())
        pos_y = int(self.nav_table.item(row_index,2).text())
        pos_z = int(self.nav_table.item(row_index,3).text())
        return entry_type,pos_x,pos_y,pos_z
    
    def nav_renamed(self,r,c):
        if c == 0:
            entry_type = self.nav_table.item(r,c).text()
            self.main_cam_widget.filename.setText(entry_type)
            self.aux_cam_widget.filename.setText(entry_type)
    
    def nav_add(self):
        stage = self.dev_manager.Stage
        row_count = self.nav_table.rowCount()
        if row_count == 0:
            stage.set_position_counter()
            self.nav_count_id = 1
        self.nav_table.insertRow(row_count)
        
        x = stage.step_counter['x']
        y = stage.step_counter['y']
        z = stage.step_counter['z']
        
        x_item = QTableWidgetItem(f'{x}')
        y_item = QTableWidgetItem(f'{y}')
        z_item = QTableWidgetItem(f'{z}')
        x_item.setFlags( x_item.flags() ^ Qt.ItemIsEditable )
        y_item.setFlags( y_item.flags() ^ Qt.ItemIsEditable )
        z_item.setFlags( z_item.flags() ^ Qt.ItemIsEditable )
        roi_name = f'ROI_{self.nav_count_id:03d}'
        self.main_cam_widget.filename.setText(roi_name)
        self.aux_cam_widget.filename.setText(roi_name)
        self.nav_table.setItem(row_count,0,QTableWidgetItem(roi_name))
        self.nav_table.setItem(row_count,1,x_item)
        self.nav_table.setItem(row_count,2,y_item)
        self.nav_table.setItem(row_count,3,z_item)
        
        self.nav_count_id += 1
    
    def nav_remove(self):
        if self.nav_table.rowCount() > 0:
            row_idx = self.nav_table.currentRow()
            if row_idx >= 0:
                t,x,y,z = self.nav_get_data(row_idx)
                # message_text = f'Are you sure you want to remove the entry {row_idx+1}: '
                # message_text += f'{t} @ {x},{y},{z}'
            
                # result = QtWidgets.QMessageBox.question(self,'Removing entry',message_text,QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No )
                # if result == QtWidgets.QMessageBox.Yes:
                self.nav_table.removeRow(row_idx)
    
    def nav_goto(self):
        if self.nav_table.rowCount() > 0:
            stage = self.dev_manager.Stage
            row_idx = self.nav_table.currentRow()
            if row_idx >= 0:
                t,x,y,z = self.nav_get_data(row_idx)
                dx = x - stage.step_counter['x']
                dy = y - stage.step_counter['y']
                dz = z - stage.step_counter['z']
                sx,vx = dx>0, np.abs(dx)
                sy,vy = dy>0, np.abs(dy)
                sz,vz = dz>0, np.abs(dz)
                
                print('old pos: ', stage.step_counter)
                
                if vx > 0: 
                    stage.positioning_coarse(stage.axis_x, sx, vx) # X
                if vy > 0: 
                    stage.positioning_coarse(stage.axis_y, sy, vy) # Y
                if vz > 0: 
                    stage.positioning_coarse(stage.axis_z, sz, vz) # Z
                
                print('new pos: ', stage.step_counter)
                
    def nav_save(self):
        if self.nav_table.rowCount() > 0:
            name,_ = QFileDialog.getSaveFileName(self, 'Save File', self.folder.text(), 'CSV file (*.csv);;All Files (*)')
            if name:
                if name[-4:] == '.csv':
                    fp = open(name,'w')
                    for i in range(self.nav_table.rowCount()):
                        t,x,y,z = self.nav_get_data(i)
                        fp.write(f'{t},{x},{y},{z}\n')
                    fp.close()
    
    def _create_lasers(self):
        # laser_405 = DummyLaser('Laser405')
        # laser_488 = DummyLaser('Laser488')
        laser_405 = DummyLaser('Laser405') if self.dummies else MicroFPGALaser('Laser405') # uFPGA
        laser_488 = DummyLaser('Laser488') if self.dummies else TopticaIBeamLaser('Laser488') # Toptica iBeam
        laser_561 = DummyLaser('Laser561')
        # laser_640 = DummyLaser('Laser640')
        # laser_640 = DummyLaser('Laser640')
        laser_640 = DummyLaser('Laser640') if self.dummies else OmicronLaser_PycroManager('Laser640') # Omicron PycroManager
        
        self.dev_manager.add(laser_405)
        self.dev_manager.add(laser_488)
        self.dev_manager.add(laser_561)
        self.dev_manager.add(laser_640)
        
        widget = QGroupBox()
        layout = QGridLayout()
        layout.setContentsMargins(0,0,0,0)
        
        layout.addWidget(LaserWidget(laser_405,'405 nm','#C8B3E1',vertical=False),0,0)
        layout.addWidget(LaserWidget(laser_488,'488 nm','#B7FFFA',vertical=False),0,1)
        #layout.addWidget(LaserWidget(laser_561,'561 nm','#FDFC96',vertical=False),1,0)
        layout.addWidget(LaserWidget(laser_561,'561 nm','#C6FF00',vertical=False),1,0)
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
        
        filterwheel = DummyFilterWheel('FilterWheel') if self.dummies else FilterWheel('FilterWheel')
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
        
        stage_driver = DummyStage('Stage') if self.dummies else AttoCubeStage('Stage',com_port='COM5')
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
app.setKeyboardInputInterval(60)
app.setWindowIcon( QIcon('resources/microscope.svg') )

icon_prov = IconProvider()
icon_prov.load_dark_mode()

window = MainWindow(dummies=False)

window.show()
app.exec_()

# %%