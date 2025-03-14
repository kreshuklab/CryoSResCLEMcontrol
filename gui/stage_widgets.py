from PyQt5.QtCore import Qt, QObject, QThread, pyqtSignal, pyqtSlot
from PyQt5.QtCore import QElapsedTimer, QPoint, QRectF, QPointF
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QFormLayout, QSpacerItem
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
from gui.ui_utils import create_int_line_edit,create_combo_box
from os.path import exists as _exists

_g_icon_prov = IconProvider()

############################################################################### Image to NDTiff helper

class DPadWidget(QWidget):
    got_focus = pyqtSignal()
    lost_focus = pyqtSignal()
    
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
        print(key)
        if key == Qt.Key_Up:
            print("Up arrow key pressed!")
        elif key == Qt.Key_Down:
            print("Down arrow key pressed!")
        else:
            super().keyPressEvent(event)

class StageWidget(QWidget):
    
    def __init__(self,stage_device,stage_name,parent=None):
        super().__init__(parent)
        
        self.dpad_widget = self._create_d_pad()
        
        layout = QHBoxLayout()
        layout.addWidget( self.dpad_widget )
        self.setLayout(layout)
        
        self.dpad_widget.got_focus.connect( self.got_focus )
        self.dpad_widget.lost_focus.connect( self.lost_focus )
        
    def __del__(self):
        pass
    
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
        
        widget = DPadWidget(self)
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
    
    @pyqtSlot()
    def got_focus(self):
        self.lbl_focus.setPixmap( _g_icon_prov.input_field.pixmap(16,16,mode=QIcon.Mode.Normal) )
        
    @pyqtSlot()
    def lost_focus(self):
        self.lbl_focus.setPixmap( _g_icon_prov.input_field.pixmap(16,16,mode=QIcon.Mode.Disabled) )
        


