from PyQt5.QtCore import Qt, QObject, QThread, pyqtSignal, pyqtSlot
from PyQt5.QtCore import QElapsedTimer, QPoint
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QFormLayout
from PyQt5.QtWidgets import QGraphicsScene, QGraphicsView, QGraphicsPixmapItem, QOpenGLWidget
from PyQt5.QtWidgets import QPushButton, QLabel, QLineEdit, QSpinBox, QComboBox
from PyQt5.QtWidgets import QSizePolicy, QFrame
from PyQt5.QtGui import QImage, QPixmap, QIcon, QFont, QPalette, QColor, QTransform, QFontMetrics,QIntValidator
import numpy as np
from core.utils import FixedSizeNumpyQueue,get_min_max_avg
from ndstorage import NDTiffDataset
from gui.ui_utils import IconProvider
from os.path import exists as _exists

############################################################################### Create Button with Icon

def _create_iconized_button(icon_file,text="",scale=1):
    button = QPushButton(text)
    button.setIcon( QIcon(icon_file) )
    button.setIconSize(scale*button.sizeHint())
    return button

############################################################################### Image to NDTiff helper

class ImageToNDTiff(QObject):
    finish_saving = pyqtSignal()
    
    def __init__(self,camera_thread):
        super().__init__()
        self._cam = camera_thread
        self.current_file = None
        self.is_acquiring = False
        self.frame_count  = 0
        self.max_count    = 0
    
    def save_snap(self,filename):
        if self._cam.frame_buffer.size > 0 and not self.is_acquiring:
            summary_metadata = {'CameraUniqueId': self._cam.uid,
                                'CameraVendor':   self._cam.vendor,
                                'CameraModel':    self._cam.model,
                                'PixelSizeNM':    self._cam.pix_size_nm}
            dataset = NDTiffDataset(filename,summary_metadata=summary_metadata,writable=True)
            image_coordinates = {'x': 0, 'y': 0} 
            image_metadata = {'timestamp': str(self._cam.timestamp),} 
            dataset.put_image(image_coordinates, self._cam.frame_buffer, image_metadata)
            dataset.finish()
    
    def start_acquisition(self,filename):
        if self.is_acquiring:
            return
        
        summary_metadata = {'CameraUniqueId': self._cam.uid,
                            'CameraVendor':   self._cam.vendor,
                            'CameraModel':    self._cam.model,
                            'PixelSizeNM':    self._cam.pix_size_nm}
        self.current_file = NDTiffDataset(filename,summary_metadata=summary_metadata,writable=True)
        self.is_acquiring = True
    
    def stop_acquisition(self):
        if not self.is_acquiring:
            return
        
        self.frame_count  = self.max_count # Force to end
    
    def push_frame(self):
        if not self.is_acquiring:
            return
        
        if self.current_file is not None:
            if self.frame_count < self.max_count:
                image_coordinates = {'x': 0, 'y': 0} 
                image_metadata = {'timestamp': str(self._cam.timestamp),} 
                self.current_file.put_image(image_coordinates, self._cam.frame_buffer, image_metadata)
                self.frame_count = self.frame_count + 1
            else:
                self.current_file.finish()
                del self.current_file
                self.current_file = None
                self.is_acquiring = False
                self.finish_saving.emit()
    
    @pyqtSlot()
    def got_frame(self):
        self.push_frame()

############################################################################### Image to QImage helper

class ImageToQImage(QObject):
    frame_ready = pyqtSignal()
    
    def __init__(self,camera_thread):
        super().__init__()
        self.frame_y_flipped = np.zeros((0,0))
        self.current_range   = 0
        
        self._cam = camera_thread
        
        self.w = 0
        self.h = 0
        
        self.v_min = 0
        self.v_max = 0
        self.v_avg = 0
        self.v_fps = 0
        
        self.timeout   = 1000
        self.fps_timer = QElapsedTimer()
        
        self.ms_queue = FixedSizeNumpyQueue(n_elements=5)
    
    def set_outlier_range(self,outlier_range):
        self.current_range = outlier_range
    
    @pyqtSlot()
    def got_frame(self):
        self.frame_y_flipped = np.float32( self._cam.frame_buffer )
        self.update_qimage()
        
    @pyqtSlot()
    def update_qimage(self):
        if self.current_range > 0:
            v_min,v_max = np.quantile(self.frame_y_flipped.ravel(),(self.current_range,1-self.current_range))
        else:
            v_min = self.frame_y_flipped.min()
            v_max = self.frame_y_flipped.max()
        
        self.v_min,self.v_max,self.v_avg = get_min_max_avg(self.frame_y_flipped)
        
        self.h,self.w = self.frame_y_flipped.shape
        
        buffer_f32  = (self.frame_y_flipped-v_min) / (v_max-v_min)
        buffer_u16  = np.uint16( np.round( 65535.0*buffer_f32.clip(0,1) ) )
        
        self.v_fps = 0
        
        time_in_ms = self.fps_timer.restart()
        if time_in_ms < self.timeout:
            self.ms_queue.push(time_in_ms)
        
        mean_ms = self.ms_queue.mean()
        if mean_ms > 0:
            self.v_fps = 1000/mean_ms
            
        
        self.qimage = QImage( buffer_u16.data, self.w, self.h, 2*self.w, QImage.Format.Format_Grayscale16 )
        self.frame_ready.emit()

############################################################################### Custom GraphicsScene

class CameraScene(QGraphicsScene):
    
    def __init__(self, parent=None):
        QGraphicsScene.__init__(self, parent)
        
        self.image = None
        self.W = 0
        self.H = 0
        self.Wh = 0
        self.Hh = 0
        
    def has_image(self):
        return self.image is not None
        
    def set_frame(self,qimg:QImage):
        should_fit = False
        if self.image is None:
            self.image = QGraphicsPixmapItem()
            self.addItem(self.image)
            self.image.setZValue(-1)
            self.image.setPos(0,0)
            self.image.setTransformationMode( Qt.TransformationMode.SmoothTransformation )
            # self.image.setTransformationMode( Qt.TransformationMode.FastTransformation )
            should_fit = True
            
        pixmap = QPixmap.fromImage(qimg)
        self.image.setPixmap(pixmap)
        self.W = self.sceneRect().width()
        self.H = self.sceneRect().height()
        
        return should_fit

###############################################################################

class CameraViewer(QGraphicsView):
    
    def __init__(self, qimg_provider, parent=None, useOpenGL=True, background='black'):
        
        QGraphicsScene.__init__(self,parent)
        
        self.do_pan    = False
        self.start_pos = QPoint()
        self._qimg_provider = qimg_provider
        
        if useOpenGL:
            self.setViewport( QOpenGLWidget() )
        
        self.setBackgroundRole(QPalette.ColorRole.NoRole)
        self.setBackgroundBrush(QColor(background))
        
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.MinimalViewportUpdate)
        
        self.scene_handler = CameraScene(self)
        self.setScene(self.scene_handler)
        
        self._qimg_provider.frame_ready.connect( self.got_frame )
    
    @pyqtSlot()
    def got_frame(self):
        if self.scene_handler.set_frame(self._qimg_provider.qimage):
            self.fitScale()
    
    @pyqtSlot()
    def fitScale(self):
        if self.scene_handler.has_image():
            v_rect = self.viewport().rect()
            self.setTransform( QTransform.fromScale(1,1) )
            scale_x = v_rect.width() / self.scene_handler.W
            scale_y = v_rect.height() / self.scene_handler.H
            scale = min(scale_x,scale_y)
            self.scale(scale,scale)
            self.centerOn(self.scene_handler.Wh,self.scene_handler.Hh)
    
    def resetScale(self):
        if self.scene_handler.has_main_image():
            self.setTransform( QTransform.fromScale(1,1) )
            self.centerOn(self.scene_handler.Wh,self.scene_handler.Hh)
    
    def mousePressEvent(self,event):
        super().mousePressEvent(event)
        
        if event.button() == Qt.LeftButton or event.button() == Qt.MiddleButton:
            self.do_pan = True
            self.start_pos = event.pos()
        
    def mouseReleaseEvent(self,event):
        super().mousePressEvent(event)
        
        if event.button() == Qt.LeftButton or event.button() == Qt.MiddleButton:
            self.do_pan = False
    
    def mouseMoveEvent(self,event):
        if self.do_pan:
            delta = self.start_pos - event.pos()
            hBar = self.horizontalScrollBar()
            vBar = self.verticalScrollBar()
            vBar.setValue(vBar.value() + delta.y())
            hBar.setValue(hBar.value() + delta.x())
            self.start_pos = event.pos()
        super().mouseMoveEvent(event)
        
    @pyqtSlot()
    def zoom_in(self):
        factor = 1.25
        self.scale(factor,factor)
    
    @pyqtSlot()
    def zoom_out(self):
        factor = 0.8
        self.scale(factor,factor)
        
    def wheelEvent(self, event):
        if event.angleDelta().y() > 0:
            self.zoom_in()
        else:
            self.zoom_out()

############################################################################### Camera Viewer

class CameraWidget(QWidget):
    start_acquiring = pyqtSignal()
    stop_acquiring  = pyqtSignal()
    
    def __init__(self,camera_handler,camera_name,*args,**kwargs):
        super().__init__(*args,**kwargs)
        
        self.is_live = False
        self.working_dir = ""
        
        self.cam_handler = camera_handler
        self.cam_thread  = QThread(self)
        self.cam_handler.moveToThread(self.cam_thread)
        
        # self.cam_handler.set_exposure_time(0.1)
        
        self.img2qimg    = ImageToQImage(self.cam_handler)
        self.img2qimg.set_outlier_range(0.002)
        self.img2qimg_th = QThread(self)
        self.img2qimg.moveToThread(self.img2qimg_th)
        
        self.img2tiff    = ImageToNDTiff(self.cam_handler)
        self.img2tiff_th = QThread(self)
        self.img2tiff.moveToThread(self.img2tiff_th)
        
        self.upper_bar = self.create_upper_bar(camera_name)
        
        self.image = CameraViewer(self.img2qimg)
        
        self.lower_panel = self.create_lower_panel()                
               
        layout = QVBoxLayout()
        layout.addWidget(self.upper_bar  , stretch=0)
        layout.addWidget(self.image      , stretch=1)
        layout.addWidget(self.lower_panel, stretch=0)
        self.setLayout(layout)
        
        self.snap_button.clicked.connect(self.cam_handler.snap_frame)
        self.live_button.clicked.connect(self.clicked_live)
        self.save_button.clicked.connect(self.clicked_save)
        
        self.btn_zoom_full.clicked.connect(self.image.fitScale)
        self.btn_zoom_in.clicked.connect(self.image.zoom_in)
        self.btn_zoom_out.clicked.connect(self.image.zoom_out)
        
        self.start_acquiring.connect(self.cam_handler.acquire_frames)
        
        self.in_exp_time.editingFinished.connect( self.exposure_time_changed )
        
        self.cam_handler.frame_ready.connect(self.img2qimg.got_frame)
        self.cam_handler.frame_ready.connect(self.img2tiff.got_frame)
        
        self.img2qimg.frame_ready.connect( self.update_image )
        self.img2tiff.finish_saving.connect( self.saving_finished )
        
        self.cam_thread.start()
        self.img2qimg_th.start()
        self.img2tiff_th.start()
        
    
    def create_upper_bar(self,camera_name):
        widget = QWidget()
        layout = QVBoxLayout()
        
        icon_prov = IconProvider()
        
        name_label = QLabel(f'<strong>{camera_name}</strong> [{self.cam_handler.vendor} - {self.cam_handler.model}]')
        name_label.setAlignment(Qt.AlignCenter | Qt.AlignVCenter)
        
        stat_widget = QWidget()
        stat_layout = QHBoxLayout()
        
        self.btn_zoom_full = _create_iconized_button(icon_prov.expand)
        self.btn_zoom_in   = _create_iconized_button(icon_prov.zoom_in)
        self.btn_zoom_out  = _create_iconized_button(icon_prov.zoom_out)
        
        stat_layout.addWidget(self.btn_zoom_full)
        stat_layout.addWidget(self.btn_zoom_in  )
        stat_layout.addWidget(self.btn_zoom_out )
        
        stat_layout.addStretch()

        self.display_img_size = QLabel("?x? pixels")
        self.display_img_size.setAlignment(Qt.AlignRight | Qt.AlignVCenter)        
        stat_layout.addWidget(self.display_img_size )
        
        grid_widget = QWidget()
        grid_layout = QGridLayout()
        grid_layout.setContentsMargins(3,0,3,0)

        font = QFont()
        font.setBold(True)
        
        label = QLabel("MIN:")
        label.setFont(font)
        grid_layout.addWidget(label,0,0)
        
        label = QLabel("MAX:")
        label.setFont(font)
        grid_layout.addWidget(label,1,0)
        
        label = QLabel("AVG:")
        label.setFont(font)
        grid_layout.addWidget(label,0,2)
        
        label = QLabel("FPS:")
        label.setFont(font)
        grid_layout.addWidget(label,1,2)
        
        self.display_min = QLabel("-")
        self.display_max = QLabel("-")
        self.display_avg = QLabel("-")
        self.display_fps = QLabel("-")
        
        grid_layout.addWidget(self.display_min,0,1)
        grid_layout.addWidget(self.display_max,1,1)
        grid_layout.addWidget(self.display_avg,0,3)
        grid_layout.addWidget(self.display_fps,1,3)
        
        grid_widget.setLayout(grid_layout)
        
        stat_layout.addWidget(grid_widget)
        
        stat_widget.setLayout(stat_layout)
        
        layout.addWidget(name_label)
        layout.addWidget(stat_widget)
        
        widget.setLayout(layout)
        
        return widget

    def create_lower_panel(self):
        
        icon_prov = IconProvider()
        
        widget = QWidget()
        layout = QGridLayout()
        layout.setContentsMargins(0,0,0,0)
        
        buttons_widget = QWidget()
        buttons_layout = QHBoxLayout()
        buttons_layout.setContentsMargins(0,0,0,0)
        
        self.snap_button = _create_iconized_button(icon_prov.camera)
        self.live_button = _create_iconized_button(icon_prov.video_camera)
        buttons_layout.addStretch(0)
        buttons_layout.addWidget(self.snap_button)
        buttons_layout.addWidget(self.live_button)
        buttons_layout.addStretch(0)
        buttons_widget.setLayout(buttons_layout)
        
        layout.addWidget(buttons_widget,0,0,1,1)
        layout.addWidget(self.create_saving_panel(),1,0,1,1)
        layout.addWidget(self.create_configuration_panel(),0,1,2,1)
        
        widget.setLayout(layout)
        return widget
    
    def create_saving_panel(self):
        
        icon_prov = IconProvider()
        
        widget = QWidget()
        layout = QHBoxLayout()
        
        input_widget = QWidget()
        input_layout = QFormLayout()
        
        self.filename = QLineEdit()
        
        self.num_frames = QSpinBox()
        self.num_frames.setRange(0,2147483647)
        self.num_frames.setSingleStep(10)
        self.num_frames.setValue(0)
        
        self.save_button = _create_iconized_button(icon_prov.floppy_disk_arrow_in)
        
        input_layout.addRow('Save to:',self.filename)
        input_layout.addRow('Num. Frames:',self.num_frames)
        
        input_widget.setLayout(input_layout)
        
        layout.addWidget(input_widget)
        layout.addWidget(self.save_button)
        
        widget.setLayout(layout)
        return widget
    
    def create_configuration_panel(self):
        
        icon_prov = IconProvider()
        
        widget = QWidget()
        layout = QVBoxLayout()
        
        ########
        
        roi_button_widget = QWidget()
        roi_button_layout = QHBoxLayout()
        roi_button_layout.setContentsMargins(0,0,0,0)
        self.roi_button_show = _create_iconized_button(icon_prov.iris_scan)
        self.roi_button_pick = _create_iconized_button(icon_prov.border_out)
        self.roi_button_in   = _create_iconized_button(icon_prov.scale_frame_reduce)
        self.roi_button_out  = _create_iconized_button(icon_prov.scale_frame_enlarge)
        roi_button_layout.addWidget(self.roi_button_show)
        roi_button_layout.addWidget(self.roi_button_pick)
        roi_button_layout.addWidget(self.roi_button_in  )
        roi_button_layout.addWidget(self.roi_button_out )
        roi_button_widget.setLayout(roi_button_layout)
        
        ########
        
        int_validator = QIntValidator(0,9999)
        roi_config_widget = QWidget()
        roi_config_layout = QHBoxLayout()
        roi_config_layout.setContentsMargins(0,0,0,0)
        self.roi_config_pos_x = QLineEdit()
        self.roi_config_pos_y = QLineEdit()
        self.roi_config_size  = QSpinBox()
        self.roi_config_size.setRange(0,4000)
        self.roi_config_size.setSingleStep(4)
        self.roi_config_size.setValue(512)
        font_metrics = QFontMetrics(self.roi_config_pos_x.font())
        self.roi_config_pos_x.setPlaceholderText('X')
        self.roi_config_pos_y.setPlaceholderText('Y')
        self.roi_config_pos_x.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.roi_config_pos_y.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.roi_config_pos_x.setValidator(int_validator)
        self.roi_config_pos_y.setValidator(int_validator)
        self.roi_config_pos_x.setMinimumWidth( 5*font_metrics.horizontalAdvance('0') )
        self.roi_config_pos_y.setMinimumWidth( 5*font_metrics.horizontalAdvance('0') )
        roi_config_layout.addWidget(QLabel('ROI X/Y:'))
        roi_config_layout.addWidget(self.roi_config_pos_x)
        roi_config_layout.addWidget(self.roi_config_pos_y)
        roi_config_layout.addWidget(QLabel('Size:'))
        roi_config_layout.addWidget(self.roi_config_size )
        roi_config_widget.setLayout(roi_config_layout)
        
        ########
        
        parameters_widget = QWidget()
        parameters_layout = QFormLayout()
        parameters_layout.setContentsMargins(0,0,0,0)
        
        # Exposure time
        exp_values    = self.cam_handler.get_exp_time_range()
        exp_cur_value = self.cam_handler.get_exp_time()
        if isinstance(exp_values, tuple):
            self.in_exp_time = QSpinBox()
            self.in_exp_time.setRange( exp_values[0], exp_values[1] )
            self.in_exp_time.setSingleStep(10)
            self.in_exp_time.setValue( int(exp_cur_value) )
        elif isinstance(exp_values, list):
            # ToDo: Further test
            self.in_exp_time = QComboBox(exp_values)
        
        parameters_layout.addRow('Exposure time (ms):',self.in_exp_time)
        parameters_layout.addRow('Binning:',QLabel('Unsupported'))
        parameters_layout.addRow('Gain (dB):',QLabel('Unsupported'))
        
        parameters_widget.setLayout(parameters_layout)
        
        ########
        
        layout.addWidget(roi_button_widget)
        layout.addWidget(roi_config_widget)
        layout.addWidget(parameters_widget)
        widget.setLayout(layout)
        return widget
    
    @pyqtSlot()
    def start_acquisition(self):
        icon_prov = IconProvider()
        self.is_live = True
        self.live_button.setIcon(QIcon(icon_prov.video_camera_off))
        self.start_acquiring.emit()
    
    @pyqtSlot()
    def stop_acquisition(self):
        icon_prov = IconProvider()
        self.is_live = False
        self.live_button.setIcon(QIcon(icon_prov.video_camera))
        self.cam_handler.stop_acquisition()
        self.img2tiff.stop_acquisition()
        self.stop_acquiring.emit()
    
    @pyqtSlot()
    def clicked_live(self):
        if self.is_live:
            self.stop_acquisition()
        else:
            self.start_acquisition()
    
    @pyqtSlot()
    def clicked_save(self):
        file_name = self.filename.text()
        file_name = file_name.strip()
        if file_name == '':
            return
        if not self.is_live:
            self.img2tiff.save_snap(file_name)
        else:
            self.img2tiff.max_count = self.num_frames.value()
            self.img2tiff.start_acquisition(file_name)
            self.filename.setEnabled(False)
            self.num_frames.setEnabled(False)
            self.save_button.setEnabled(False)
    
    @pyqtSlot()
    def saving_finished(self):
        self.filename.setEnabled(True)
        self.num_frames.setEnabled(True)
        self.save_button.setEnabled(True)
        
    @pyqtSlot()
    def exposure_time_changed(self):
        self.cam_handler.set_exp_time( int(self.in_exp_time.value()) )
    
    @pyqtSlot()
    def update_image(self):
        self.display_img_size.setText( f'{self.img2qimg.w}x{self.img2qimg.h} pixeles' )
        self.display_min.setText(f'{self.img2qimg.v_min:.0f}')
        self.display_max.setText(f'{self.img2qimg.v_max:.0f}')
        self.display_avg.setText(f'{self.img2qimg.v_avg:.0f}')
        
        if self.img2qimg.v_fps > 0:
            self.display_fps.setText(f'{self.img2qimg.v_fps:.0f}')
        else:
            self.display_fps.setText('-')
    
    def __del__(self):
        
        print('Waiting for Img2Tiff')
        if self.img2tiff_th and self.img2tiff_th.isRunning():
            self.img2tiff_th.quit()
            self.img2tiff_th.wait()  # Ensure thread stops before deleting
        
        print('Waiting for Img2QImg')
        if self.img2qimg_th and self.img2qimg_th.isRunning():
            self.img2qimg_th.quit()
            self.img2qimg_th.wait()  # Ensure thread stops before deleting
        
        print('Waiting for CameraThread')
        if self.cam_thread and self.cam_thread.isRunning():
            self.cam_thread.quit()
            self.cam_thread.wait()  # Ensure thread stops before deleting
        
        
    

