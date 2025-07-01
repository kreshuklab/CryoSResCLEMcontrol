from PyQt5.QtCore import Qt, QObject, QThread, pyqtSignal, pyqtSlot
from PyQt5.QtCore import QElapsedTimer, QPoint, QRectF, QPointF, QTimer
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QFormLayout, QSpacerItem, QTabWidget
from PyQt5.QtWidgets import QGraphicsScene, QGraphicsView, QGraphicsPixmapItem, QOpenGLWidget, QGraphicsItem
from PyQt5.QtWidgets import QPushButton, QLabel, QLineEdit, QSpinBox, QComboBox, QDoubleSpinBox, QCheckBox
from PyQt5.QtWidgets import QSizePolicy, QFrame
from PyQt5.QtGui import QImage, QPixmap, QIcon, QFont, QPalette, QColor, QTransform
from PyQt5.QtGui import QFontMetrics, QIntValidator, QPainter, QPen, QBrush, QColor
from PyQt5.QtChart import QChart, QChartView, QLineSeries, QValueAxis
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

        z_lock_button = ToogleButton(on_text='Stop Focus Lock',
                                     off_text='Start Focus Lock',
                                     on_icon=_g_icon_prov.square,
                                     off_icon=_g_icon_prov.lock_z)
        z_lock_button.toogled.connect(self.button_toogled)
        
        self.color_line_coarse = Qt.blue
        self.color_line_fine   = Qt.blue
        
        self.coarse_max = 2
        self.coarse_min = 0
        
        conf_widget = QWidget()
        conf_layout = QGridLayout()
        conf_layout.setContentsMargins(0,0,0,0)
        
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
        
        self.data_raw = []
        self.data_flt = []
        self.max_points = 100
        
        self.series_raw = QLineSeries()
        pen = self.series_raw.pen()
        pen.setColor(Qt.gray)            # RAW line color
        pen.setWidth(2)
        self.series_raw.setPen(pen)
                
        self.series_flt = QLineSeries()
        pen = self.series_flt.pen()
        pen.setColor(Qt.blue)            # DENOISED line color
        pen.setWidth(2)
        self.series_flt.setPen(pen)
        
        self.base_line = QLineSeries()
        self.base_line.append(0,1)
        self.base_line.append(self.max_points,1)
        pen = self.base_line.pen()
        pen.setColor(Qt.black)
        pen.setWidth(2)
        self.base_line.setPen(pen)
        
        self.line_coarse_up = QLineSeries()
        self.line_coarse_up.append(0,1.5)
        self.line_coarse_up.append(self.max_points,1.5)
        pen = self.line_coarse_up.pen()
        pen.setColor(self.color_line_coarse)
        pen.setStyle(Qt.DashLine)
        pen.setWidth(1)
        self.line_coarse_up.setPen(pen)
        
        self.line_coarse_low = QLineSeries()
        self.line_coarse_low.append(0,0.5)
        self.line_coarse_low.append(self.max_points,0.5)
        pen = self.line_coarse_low.pen()
        pen.setColor(self.color_line_coarse)
        pen.setStyle(Qt.DashLine)
        pen.setWidth(1)
        self.line_coarse_low.setPen(pen)
        
        self.line_fine_up = QLineSeries()
        self.line_fine_up.append(0,1.2)
        self.line_fine_up.append(self.max_points,1.2)
        pen = self.line_fine_up.pen()
        pen.setColor(self.color_line_fine)
        pen.setStyle(Qt.DotLine)
        pen.setWidth(1)
        self.line_fine_up.setPen(pen)
        
        self.line_fine_low = QLineSeries()
        self.line_fine_low.append(0,0.8)
        self.line_fine_low.append(self.max_points,0.8)
        pen = self.line_fine_low.pen()
        pen.setColor(self.color_line_fine)
        pen.setStyle(Qt.DotLine)
        pen.setWidth(1)
        self.line_fine_low.setPen(pen)

        self.chart = QChart()
        self.chart.legend().hide()
        self.chart.setContentsMargins(-15,-15,-15,-15)

        self.axis_y = QValueAxis()
        self.axis_y.setRange(0, 2)
        self.chart.addAxis(self.axis_y, Qt.AlignLeft)
        
        self.axis_x = QValueAxis()
        self.axis_x.setRange(0, self.max_points)
        self.axis_x.setLabelsVisible(False)
        self.chart.addAxis(self.axis_x, Qt.AlignBottom)
        
        
        self.chart.addSeries(self.base_line)
        self.base_line.attachAxis(self.axis_x)
        self.base_line.attachAxis(self.axis_y)
        
        self.chart.addSeries(self.line_coarse_up)
        self.line_coarse_up.attachAxis(self.axis_x)
        self.line_coarse_up.attachAxis(self.axis_y)
        
        self.chart.addSeries(self.line_coarse_low)
        self.line_coarse_low.attachAxis(self.axis_x)
        self.line_coarse_low.attachAxis(self.axis_y)

        self.chart.addSeries(self.line_fine_up)
        self.line_fine_up.attachAxis(self.axis_x)
        self.line_fine_up.attachAxis(self.axis_y)
        
        self.chart.addSeries(self.line_fine_low)
        self.line_fine_low.attachAxis(self.axis_x)
        self.line_fine_low.attachAxis(self.axis_y)

        self.chart.addSeries(self.series_raw)
        self.series_raw.attachAxis(self.axis_x)
        self.series_raw.attachAxis(self.axis_y)
        
        self.chart.addSeries(self.series_flt)
        self.series_flt.attachAxis(self.axis_x)
        self.series_flt.attachAxis(self.axis_y)

        self.chart_view = QChartView(self.chart)
        self.chart_view.setRenderHint(QPainter.Antialiasing)
                
        self.layout().addWidget(z_lock_button,0)
        self.layout().addWidget(conf_widget,0)
        self.layout().addWidget(self.chart_view,1)
        
        self.fine_check.toggled.connect( self.fine_checked )
        self.kalman_signal.valueChanged.connect( self.set_kalman_signal )
        self.kalman_noise .valueChanged.connect( self.set_kalman_noise  )
        self.coarse_low   .valueChanged.connect( self.set_coarse_low    )
        self.coarse_up    .valueChanged.connect( self.set_coarse_up     )
        self.fine_low     .valueChanged.connect( self.set_fine_low      )
        self.fine_up      .valueChanged.connect( self.set_fine_up       )
        
        self.fine_low.setEnabled( self.fine_check.checkState() )
        self.fine_up .setEnabled( self.fine_check.checkState() )
        self.line_fine_low.setVisible(self.fine_check.checkState())
        self.line_fine_up.setVisible( self.fine_check.checkState())
        
        self._zlock_handler.error_reporting.connect(self.report_message)
        self._zlock_handler.ratios_broadcast.connect(self.got_data)
        
        
    def _update_line(self,line,val):
        line.clear()
        line.append(0,val)
        line.append(self.max_points,val)

    def update_y_range(self):
        lo_value = 0
        if len(self.data_flt)>0:
            lo_value = min(np.array(self.data_flt).min(),self.coarse_min)
            lo_value = min(np.array(self.data_raw).min(),lo_value)
        
        hi_value = 2
        if len(self.data_flt)>0:
            hi_value = max(np.array(self.data_flt).max(),self.coarse_max)
            hi_value = max(np.array(self.data_raw).max(),hi_value)
        
        self.axis_y.setRange(lo_value,hi_value)

    @pyqtSlot(bool)
    def button_toogled(self,state):
        if state:
            self._zlock_handler.start()
            self.data_raw.clear()
            self.data_flt.clear()
            self.series_raw.clear()
            self.series_flt.clear()
        else:
            self._zlock_handler.stop()
            

    @pyqtSlot(bool)
    def fine_checked(self,state):
        self.fine_low.setEnabled(state)
        self.fine_up.setEnabled(state)
        self.line_fine_low.setVisible(state)
        self.line_fine_up.setVisible(state)
        self._zlock_handler.should_fine = state
    
    @pyqtSlot(float)
    def set_coarse_low(self,val):
        self._zlock_handler.coarse_low = val
        self._update_line(self.line_coarse_low,val)
        self.coarse_min = val-0.1
        self.update_y_range()
        
    @pyqtSlot(float)
    def set_coarse_up(self,val):
        self._zlock_handler.coarse_up = val
        self._update_line(self.line_coarse_up,val)
        self.coarse_max = val+0.1
        self.update_y_range()
        
    @pyqtSlot(float)
    def set_fine_low(self,val):
        self._zlock_handler.fine_low = val
        self._update_line(self.line_fine_low,val)
        
    @pyqtSlot(float)
    def set_fine_up(self,val):
        self._zlock_handler.fine_up = val
        self._update_line(self.line_fine_up,val)

    @pyqtSlot(float)
    def set_kalman_signal(self,_):
        self._zlock_handler.ratio_noise = self.kalman_signal.log_value()

    @pyqtSlot(float)
    def set_kalman_noise(self,_):
        self._zlock_handler.signal_noise = self.kalman_noise.log_value()
        
    @pyqtSlot(float,float)
    def got_data(self,data_raw,filtered):
        self.data_raw.append(data_raw)
        if len(self.data_raw) > self.max_points:
            self.data_raw.pop(0)

        self.data_flt.append(filtered)
        if len(self.data_flt) > self.max_points:
            self.data_flt.pop(0)
    
        self.series_raw.clear()
        for i, val in enumerate(self.data_raw):
            self.series_raw.append(i, val)
            
        self.series_flt.clear()
        for i, val in enumerate(self.data_flt):
            self.series_flt.append(i, val)
            
        self.update_y_range()
        
    @pyqtSlot(int,int,str)
    def report_message(self,report_type,report_code,report_message):
        print(report_type,report_code,report_message)

