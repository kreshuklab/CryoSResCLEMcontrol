from PyQt5.QtCore import Qt, QObject, QThread, pyqtSignal, pyqtSlot
from PyQt5.QtCore import QElapsedTimer, QPoint, QRectF, QPointF, QTimer
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QFormLayout, QSpacerItem, QTabWidget
from PyQt5.QtWidgets import QGraphicsScene, QGraphicsView, QGraphicsPixmapItem, QOpenGLWidget, QGraphicsItem
from PyQt5.QtWidgets import QPushButton, QLabel, QLineEdit, QSpinBox, QComboBox, QDoubleSpinBox, QCheckBox
from PyQt5.QtWidgets import QSizePolicy, QFrame
from PyQt5.QtGui import QImage, QPixmap, QIcon, QFont, QPalette, QColor, QTransform
from PyQt5.QtGui import QFontMetrics, QIntValidator, QPainter, QPen, QBrush, QColor
import numpy as np
from core.utils import FixedSizeNumpyQueue,get_min_max_avg
from ndstorage import NDTiffDataset
from gui.ui_utils import IconProvider,ToogleButton,LogDoubleSpinBox
from gui.ui_utils import create_iconized_button,update_iconized_button
from gui.ui_utils import create_int_line_edit,create_combo_box,create_spinbox,create_doublespinbox
from os.path import exists as _exists

from core.z_lock import ZLock

_g_icon_prov = IconProvider()

############################################################################### Image to NDTiff helper

class ZLockWidget(QWidget):
    
    def __init__(self,zlock:ZLock,parent=None):
        super().__init__(parent)
        
        self._zlock_handler = zlock
        
        self.setLayout( QVBoxLayout() )

        z_lock_button = ToogleButton(on_text='Start Focus Lock',
                                     off_text='Stop Focus Lock',
                                     on_icon=_g_icon_prov.square,
                                     off_icon=_g_icon_prov.lock_z)
        z_lock_button.toogled.connect(self.button_toogled)
        
        
        conf_widget = QWidget()
        conf_layout = QGridLayout()
        
        self.coarse_low = QDoubleSpinBox()
        self.coarse_up = QDoubleSpinBox()
        conf_layout.addWidget(QLabel("<b>Coarse thresholds:</b>"), 0, 0)
        conf_layout.addWidget(QLabel("Lower"), 0, 1)
        conf_layout.addWidget(self.coarse_low, 0, 2)
        conf_layout.addWidget(QLabel("Upper"), 0, 3)
        conf_layout.addWidget(self.coarse_up , 0, 4)
        
        self.fine_check = QCheckBox("Fine thresholds:")
        font = self.fine_check.font()
        font.setBold(True)
        self.fine_check.setFont(font)
        self.fine_low = QDoubleSpinBox()
        self.fine_up  = QDoubleSpinBox()
        conf_layout.addWidget(self.fine_check, 1, 0)
        conf_layout.addWidget(QLabel("Lower"), 1, 1)
        conf_layout.addWidget(self.fine_low  , 1, 2)
        conf_layout.addWidget(QLabel("Upper"), 1, 3)
        conf_layout.addWidget(self.fine_up   , 1, 4)
        
        self.kalman_signal = LogDoubleSpinBox()
        self.kalman_noise  = LogDoubleSpinBox()
        conf_layout.addWidget(QLabel("<b>Kalman variances:</b>"), 2, 0)
        conf_layout.addWidget(QLabel("Signal")  , 2, 1)
        conf_layout.addWidget(self.kalman_signal, 2, 2)
        conf_layout.addWidget(QLabel("Noise")   , 2, 3)
        conf_layout.addWidget(self.kalman_noise , 2, 4)
        
        conf_widget.setLayout( conf_layout )
        
        self.layout().addWidget(z_lock_button)
        self.layout().addWidget(conf_widget)
        
        self.fine_check.toggled.connect( self.fine_checked )
        self.kalman_signal.valueChanged.connect( self.set_kalman_signal )
        self.kalman_noise .valueChanged.connect( self.set_kalman_noise  )
        self.coarse_low   .valueChanged.connect( self.set_coarse_low    )
        self.coarse_up    .valueChanged.connect( self.set_coarse_up     )
        self.fine_low     .valueChanged.connect( self.set_fine_low      )
        self.fine_up      .valueChanged.connect( self.set_fine_up       )
        
        self.fine_low.setEnabled( self.fine_check.checkState() )
        self.fine_up .setEnabled( self.fine_check.checkState() )
        
        self._zlock_handler.error_reporting.connect(self.report_message)
        
    @pyqtSlot(bool)
    def button_toogled(self,state):
        if state:
            self._zlock_handler.start()
        else:
            self._zlock_handler.stop()
            

    @pyqtSlot(bool)
    def fine_checked(self,state):
        self.fine_low.setEnabled(state)
        self.fine_up.setEnabled(state)
        self._zlock_handler.should_fine = state
    
    @pyqtSlot(float)
    def set_coarse_low(self,val):
        self._zlock_handler.coarse_low = val
        
    @pyqtSlot(float)
    def set_coarse_up(self,val):
        self._zlock_handler.coarse_up = val
        
    @pyqtSlot(float)
    def set_fine_low(self,val):
        self._zlock_handler.fine_low = val
        
    @pyqtSlot(float)
    def set_fine_up(self,val):
        self._zlock_handler.fine_up = val

    @pyqtSlot(float)
    def set_kalman_signal(self,_):
        self._zlock_handler.ratio_noise = self.kalman_signal.log_value()

    @pyqtSlot(float)
    def set_kalman_noise(self,_):
        self._zlock_handler.signal_noise = self.kalman_noise.log_value()
        
    @pyqtSlot(int,int,str)
    def report_message(self,report_type,report_code,report_message):
        print(report_type,report_code,report_message)

