from PyQt5.QtCore import Qt, QObject, QThread, pyqtSignal, pyqtSlot
from PyQt5.QtCore import QElapsedTimer, QPoint, QRectF, QPointF
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QFormLayout, QSpacerItem, QTabWidget
from PyQt5.QtWidgets import QGraphicsScene, QGraphicsView, QGraphicsPixmapItem, QOpenGLWidget, QGraphicsItem
from PyQt5.QtWidgets import QPushButton, QLabel, QLineEdit, QSpinBox, QComboBox
from PyQt5.QtWidgets import QSizePolicy, QFrame
from PyQt5.QtGui import QImage, QPixmap, QIcon, QFont, QPalette, QColor, QTransform
from PyQt5.QtGui import QFontMetrics, QIntValidator, QPainter, QPen, QBrush, QColor
import numpy as np
from core.utils import FixedSizeNumpyQueue,get_min_max_avg
from ndstorage import NDTiffDataset
from gui.ui_utils import IconProvider
from gui.ui_utils import create_iconized_button,update_iconized_button
from gui.ui_utils import create_int_line_edit,create_combo_box,create_spinbox,create_doublespinbox
from os.path import exists as _exists

_g_icon_prov = IconProvider()

############################################################################### Image to NDTiff helper

class _DPadWidget(QWidget):
    got_focus    = pyqtSignal()
    lost_focus   = pyqtSignal()
    send_commit  = pyqtSignal()
    send_command = pyqtSignal(str,int)
    
    def __init__(self,parent=None):
        super().__init__(parent)
        self.setFocusPolicy( Qt.FocusPolicy.StrongFocus )

    def focusInEvent(self, event):
        self.got_focus.emit()
        super().focusInEvent(event)

    def focusOutEvent(self, event):
        self.lost_focus.emit()
        super().focusOutEvent(event)

    def keyPressEvent(self,event):
        key = event.key()
        
        if   key in (Qt.Key_A,Qt.Key_Left):
            self.send_command.emit('x',-1)
            
        elif key in (Qt.Key_D,Qt.Key_Right):
            self.send_command.emit('x', 1)
            
        elif key in (Qt.Key_W,Qt.Key_Up):
            self.send_command.emit('y', 1)
            
        elif key in (Qt.Key_S,Qt.Key_Down):
            self.send_command.emit('y',-1)
            
        elif key in (Qt.Key_Q,Qt.Key_PageUp):
            self.send_command.emit('z', 1)
            
        elif key in (Qt.Key_E,Qt.Key_PageDown):
            self.send_command.emit('z',-1)
        
        elif key in (Qt.Key_Space,Qt.Key_Enter):
            self.send_commit.emit()
        
        else:
            super().keyPressEvent(event)

class StageWidget(QWidget):
    send_command = pyqtSignal(str,int)
    
    send_move = pyqtSignal(int,bool,int) # axis_id,is_up,n_step
    send_ofst = pyqtSignal(int,float) # axis_id,delta_offset
    send_vltg = pyqtSignal(int,int)
    send_freq = pyqtSignal(int)
    
    def __init__(self,stage_device,stage_name,parent=None):
        super().__init__(parent)
        
        self.stage_device = stage_device
        # self.stage_thread = QThread(self)
        # self.stage_device.moveToThread(self.stage_thread)
        
        self.axis = {'x':2, 'y':1, 'z':3}
        self.dpad_widget = self._create_d_pad()
        
        self.config_tabs = QTabWidget()
        self.config_tabs.tabBar().setExpanding(True)
        self.config_tabs.addTab(self._create_coarse_config(),'Coarse Conf.')
        self.config_tabs.addTab(self._create_fine_config()  ,'Fine Conf.'  )
        
        layout = QHBoxLayout()
        layout.setContentsMargins(0,0,0,0)
        layout.addWidget( self.dpad_widget )
        layout.addWidget( self.config_tabs )
        self.setLayout(layout)
        
        self.dpad_widget.got_focus.connect( self.got_focus )
        self.dpad_widget.lost_focus.connect( self.lost_focus )
        
        self.volts_x.editingFinished.connect(lambda: self.send_vltg.emit(self.axis['x'], self.volts_x.value() ))
        self.volts_y.editingFinished.connect(lambda: self.send_vltg.emit(self.axis['y'], self.volts_y.value() ))
        self.volts_z.editingFinished.connect(lambda: self.send_vltg.emit(self.axis['z'], self.volts_z.value() ))
        
        self.freq.editingFinished.connect(lambda: self.send_freq.emit(self.freq.value() ))
        
        self.btn_x_neg.released.connect(lambda: self.send_command.emit('x',-1))
        self.btn_x_pos.released.connect(lambda: self.send_command.emit('x', 1))
        self.btn_y_neg.released.connect(lambda: self.send_command.emit('y',-1))
        self.btn_y_pos.released.connect(lambda: self.send_command.emit('y', 1))
        self.btn_z_neg.released.connect(lambda: self.send_command.emit('z',-1))
        self.btn_z_pos.released.connect(lambda: self.send_command.emit('z', 1))
        
        self.send_command.connect(self.send_move_offset_command)
        self.dpad_widget.send_command.connect(self.send_move_offset_command)
        
        # Init AttoCube
        self.stage_device.set_frequencies(self.freq.value())
        self.stage_device.set_voltage(self.axis['x'], self.volts_x.value())
        self.stage_device.set_voltage(self.axis['y'], self.volts_y.value())
        self.stage_device.set_voltage(self.axis['z'], self.volts_z.value())
        
        self.send_move.connect( self.stage_device.positioning_coarse     )
        self.send_ofst.connect( self.stage_device.positioning_fine_delta )
        self.send_vltg.connect( self.stage_device.set_voltage            )
        self.send_freq.connect( self.stage_device.set_frequencies        )
        
    def __del__(self):
        print('hi?')
        if self.stage_thread and self.stage_thread.isRunning():
            self.stage_thread.quit()
            self.stage_thread.wait()  # Ensure thread stops before deleting
    
    def _create_d_pad(self):
        self.btn_x_neg = create_iconized_button(_g_icon_prov.dot_arrow_x_neg)
        self.btn_x_pos = create_iconized_button(_g_icon_prov.dot_arrow_x_pos)
        self.btn_y_neg = create_iconized_button(_g_icon_prov.dot_arrow_y_neg)
        self.btn_y_pos = create_iconized_button(_g_icon_prov.dot_arrow_y_pos)
        self.btn_z_neg = create_iconized_button(_g_icon_prov.dot_arrow_z_neg)
        self.btn_z_pos = create_iconized_button(_g_icon_prov.dot_arrow_z_pos)
        self.lbl_focus = QLabel(self)
        self.lbl_focus.setPixmap( _g_icon_prov.input_field.pixmap(16,16,mode=QIcon.Mode.Normal) )
        
        self.btn_x_neg.setFocusPolicy( Qt.FocusPolicy.NoFocus )
        self.btn_x_pos.setFocusPolicy( Qt.FocusPolicy.NoFocus )
        self.btn_y_neg.setFocusPolicy( Qt.FocusPolicy.NoFocus )
        self.btn_y_pos.setFocusPolicy( Qt.FocusPolicy.NoFocus )
        self.btn_z_neg.setFocusPolicy( Qt.FocusPolicy.NoFocus )
        self.btn_z_pos.setFocusPolicy( Qt.FocusPolicy.NoFocus )
        self.lbl_focus.setFocusPolicy( Qt.FocusPolicy.NoFocus )
        
        widget = _DPadWidget(self)
        layout = QGridLayout()
        layout.setContentsMargins(0,0,0,0)
        layout.addWidget(self.btn_x_neg,2,1)
        layout.addWidget(self.btn_x_pos,2,3)
        layout.addWidget(self.btn_y_neg,3,2)
        layout.addWidget(self.btn_y_pos,1,2)
        layout.addWidget(self.btn_z_neg,3,5)
        layout.addWidget(self.btn_z_pos,1,5)
        layout.addWidget(self.lbl_focus,4,6,Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignBottom)
        
        layout.setColumnStretch(0,1)
        layout.setColumnStretch(1,0)
        layout.setColumnStretch(2,0)
        layout.setColumnStretch(3,0)
        layout.setColumnStretch(4,1)
        layout.setColumnStretch(5,0)
        layout.setColumnStretch(6,1)
        
        layout.setRowStretch(0,1)
        layout.setRowStretch(1,0)
        layout.setRowStretch(2,0)
        layout.setRowStretch(3,0)
        layout.setRowStretch(4,1)
        
        widget.setLayout(layout)
        
        return widget
    
    def _create_coarse_config(self):
        widget = QWidget()
        layout = QFormLayout()
        
        self.volts_x = create_spinbox(1,150,cur_val=20,step=5)
        self.volts_y = create_spinbox(1,150,cur_val=20,step=5)
        self.volts_z = create_spinbox(1,150,cur_val=20,step=5)
        self.freq    = create_spinbox(1,2500,cur_val=1000,step=100)
        self.n_steps = create_combo_box((1,2,3,5,7,10,15,20,40),1)
        
        layout.addRow('Volts.X: '   ,self.volts_x)
        layout.addRow('Volts.Y: '   ,self.volts_y)
        layout.addRow('Volts.Z: '   ,self.volts_z)
        layout.addRow('Frquency: '  ,self.freq   )
        layout.addRow('Num. Steps: ',self.n_steps)
        
        widget.setLayout(layout)
        return widget
    
    def _create_fine_config(self):
        widget = QWidget()
        layout = QFormLayout()
        
        self.offsets = {}
        self.offsets['x'] = create_doublespinbox(0.1,20.0,cur_val=0.1,step=0.1,decimals=1)
        self.offsets['y'] = create_doublespinbox(0.1,20.0,cur_val=0.1,step=0.1,decimals=1)
        self.offsets['z'] = create_doublespinbox(0.1,20.0,cur_val=0.1,step=0.1,decimals=1)
        
        layout.addRow('DeltaVolts.X: ',self.offsets['x'])
        layout.addRow('DeltaVolts.Y: ',self.offsets['y'])
        layout.addRow('DeltaVolts.Z: ',self.offsets['z'])
        
        widget.setLayout(layout)
        return widget
    
    def _is_coarse(self):
        return self.config_tabs.currentIndex() == 0
    
    def _is_fine(self):
        return self.config_tabs.currentIndex() == 1
    
    @pyqtSlot(str,int)
    def send_move_offset_command(self,axis_name,direction):
        if self._is_coarse():
            self.send_move.emit(self.axis[axis_name],direction>0,self.n_steps.currentData())
        else:
            offset = np.sign(direction)*self.offsets[axis_name].value()
            self.send_ofst.emit(self.axis[axis_name],offset)
    
    @pyqtSlot()
    def got_focus(self):
        self.lbl_focus.setPixmap( _g_icon_prov.input_field.pixmap(16,16,mode=QIcon.Mode.Normal) )
        self.lbl_focus.setToolTip('Using Keyboard bindings: WASD+QE / ArrowKeys+PageUp+PageDown')
        
    @pyqtSlot()
    def lost_focus(self):
        self.lbl_focus.setPixmap( _g_icon_prov.input_field.pixmap(16,16,mode=QIcon.Mode.Disabled) )
        self.lbl_focus.setToolTip('Keyboard binding disabled')
        


