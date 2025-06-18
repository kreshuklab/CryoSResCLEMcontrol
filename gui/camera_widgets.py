from PyQt5.QtCore import Qt, QObject, QThread, pyqtSignal, pyqtSlot
from PyQt5.QtCore import QElapsedTimer, QPoint, QRectF, QPointF
from PyQt5.QtWidgets import QWidget, QOpenGLWidget
from PyQt5.QtWidgets import QVBoxLayout, QHBoxLayout, QGridLayout, QFormLayout
from PyQt5.QtWidgets import QGraphicsScene, QGraphicsView, QGraphicsPixmapItem, QGraphicsItem
from PyQt5.QtWidgets import QLabel, QLineEdit, QSpinBox, QPushButton
from PyQt5.QtWidgets import QFrame
from PyQt5.QtGui import QImage, QPixmap, QFont, QPalette, QColor, QTransform
from PyQt5.QtGui import QPainter, QPen, QBrush, QWheelEvent
import numpy as np
from core.utils import FixedSizeNumpyQueue,get_min_max_avg
from ndstorage import NDTiffDataset
from gui.ui_utils import IconProvider,IntMultipleOfValidator, SteppingSpinBox
from gui.ui_utils import create_iconized_button,update_iconized_button
from gui.ui_utils import create_int_line_edit,create_combo_box,create_doublespinbox
from gui.ui_utils import StyledFrame
from os.path import join,normpath
from os import makedirs

############################################################################### Image to NDTiff helper

class ImageToNDTiff(QObject):
    finish_saving   = pyqtSignal()
    saving_progress = pyqtSignal(str)
    
    def __init__(self,camera_thread):
        super().__init__()
        self._cam = camera_thread
        self.current_file  = None
        self.metadata_file = None
        self.is_acquiring  = False
        self.process       = True
        self.frame_count   = 0
        self.max_count     = 0
        
        self.skip_counter = 0
        self.skip_limit   = 0
        
        self.dev_manager = None
    
    def enable_autosave(self):
        self.process = True
        
    def disable_autosave(self):
        self.process = False
    
    def dataset_start(self,filename,num_frames=-1):
        if self.is_acquiring:
            return
        
        self.is_acquiring = True
        self.max_count    = num_frames
        self.frame_count  = 0
        self.skip_counter = 0
        
        print(f'Starting {filename}')
        summary_metadata  = {'CameraUniqueId': self._cam.uid,
                             'CameraVendor':   self._cam.vendor,
                             'CameraModel':    self._cam.model,
                             'PixelSizeNM':    self._cam.pix_size_nm}
        makedirs(filename,exist_ok=True)
        self.current_file  = NDTiffDataset(filename,summary_metadata=summary_metadata,writable=True)
        self.metadata_file = open(filename+'\\NDTiff.csv','w')
        self.metadata_file.write('#N_FRAME,TIMESTAMP,X,Y,Z,LASER_INDEX,LASER_ON_NAME,LASER_VALUE,LASER_UNIT,FILTER_WHEEL_POS,FILTER_WHEEL_NAME\n')
        
    def dataset_push_frame(self):
        if self.current_file is None:
            name = f'{self._cam.uid}: [{self._cam.vendor} - {self._cam.model}'
            print(f'[{name}]: pushing frame to invalid dataset')
            return
        
        if self.dev_manager and hasattr(self.dev_manager,'Stage'):
            md_coord = {'x': self.dev_manager.Stage.step_counter['x'],
                        'y': self.dev_manager.Stage.step_counter['y'],
                        'z': self.dev_manager.Stage.step_counter['z']}
        else:
            md_coord = {'x': 0, 'y': 0, 'z': 0}
        md_img = {'timestamp': str(self._cam.timestamp),
                  'frame_count': self.frame_count}
        self.current_file.put_image(md_coord,self._cam.frame_buffer,md_img)
        laser_index,laser_name,laser_power,laser_units = self.dev_manager.get_active_laser()
        x = self.dev_manager.Stage.step_counter['x']
        y = self.dev_manager.Stage.step_counter['y']
        z = self.dev_manager.Stage.step_counter['z']
        self.metadata_file.write(f'{self.frame_count},{str(self._cam.timestamp)},')
        self.metadata_file.write(f'{x},{y},{z},')
        self.metadata_file.write(f'{laser_index},{laser_name},{laser_power},{laser_units},')
        self.metadata_file.write(f'{self.dev_manager.FilterWheel.pos},{self.dev_manager.FilterWheel.current_position_name()}\n')
        self.frame_count = self.frame_count + 1
        
    def dataset_check_done_state(self):
        if self.max_count < 0:
            return False
        return self.frame_count >= self.max_count
        
    def dataset_finish(self):
        if self.current_file is None:
            return
        
        self.current_file.finish()
        del self.current_file
        self.current_file = None
        self.max_count    = 0
        self.frame_count  = 0
        self.is_acquiring = False
        self.skip_counter = 0
        self.skip_limit   = 0
        self.metadata_file.close()
    
    def save_snap(self,filename):
        if self._cam.frame_buffer.size > 0:
            self.dataset_start(filename)
            self.dataset_push_frame()
            self.dataset_finish()
            self.saving_progress.emit('')
            
    def start_acquisition(self,filename,num_frames,skip_limit=0):
        self.skip_limit = skip_limit
        self.dataset_start(filename,num_frames)
        if self.max_count > 0:
            self.saving_progress.emit(f'{self.frame_count}/{self.max_count}')
        else:
            self.saving_progress.emit(f'{self.frame_count}')
        
    def stop_acquisition(self):
        if self.is_acquiring:
            self.frame_count = self.max_count # Force to end
    
    def push_frame(self):
        if self.is_acquiring:
            if self.skip_limit > 0:
                if (self.skip_counter % self.skip_limit ) != 0:
                    self.skip_counter += 1
                    return

            self.skip_counter += 1
            self.dataset_push_frame()
            if self.dataset_check_done_state():
                self.dataset_finish()
                self.saving_progress.emit('')
                self.finish_saving.emit()
            else:
                self.saving_progress.emit(f'{self.frame_count}/{self.max_count}')
    
    @pyqtSlot()
    def got_frame(self):
        if self.process:
            self.push_frame()

############################################################################### Image to QImage helper

class ImageToQImage(QObject):
    frame_ready = pyqtSignal()
    
    def __init__(self,camera_thread):
        super().__init__()
        self.frame_fixed = np.zeros((0,0))
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
        
        self.do_flip   = False
        self.do_rot180 = False
    
    def set_outlier_range(self,outlier_range):
        self.current_range = outlier_range
    
    @pyqtSlot()
    def got_frame(self):
        if self.do_flip:
            self.frame_fixed = np.float32( self._cam.frame_buffer[::-1,:] )
        elif self.do_rot180:
            self.frame_fixed = np.float32( self._cam.frame_buffer[::-1,::-1] )
        else:
            self.frame_fixed = np.float32( self._cam.frame_buffer )
        self.update_qimage()
        
    @pyqtSlot()
    def update_qimage(self):
        if self.current_range > 0:
            v_min,v_max = np.quantile(self.frame_fixed.ravel(),(self.current_range,1-self.current_range))
        else:
            v_min = self.frame_fixed.min()
            v_max = self.frame_fixed.max()
        
        self.v_min,self.v_max,self.v_avg = get_min_max_avg(self.frame_fixed)
        
        self.h,self.w = self.frame_fixed.shape
        
        self.v_fps = 0
        
        time_in_ms = self.fps_timer.restart()
        if time_in_ms < self.timeout:
            self.ms_queue.push(time_in_ms)
        
        mean_ms = self.ms_queue.mean()
        if mean_ms > 0:
            self.v_fps = 1000/mean_ms
        
        buffer_f32  = (self.frame_fixed-v_min) / (v_max-v_min)
        buffer_u16  = np.uint16( np.round( 65535.0*buffer_f32.clip(0,1) ) )
        self.qimage = QImage( buffer_u16.data, self.w, self.h, 2*self.w, QImage.Format.Format_Grayscale16 )
        # buffer_u16  = np.uint8( np.round( 255.0*buffer_f32.clip(0,1) ) )
        # self.qimage = QImage( buffer_u16.data, self.w, self.h, self.w, QImage.Format.Format_Grayscale8 )
        self.frame_ready.emit()

############################################################################### Custom GraphicsScene

_g_icon_prov = IconProvider()

class ROIItem(QGraphicsItem):
    def __init__(self,color_hex,outer_box=128,halo=0,parent=None):
        super().__init__(parent)
        
        self.color = color_hex
        self.set_box_size(outer_box,halo)

    def set_box_size(self,box_size,halo):
        self.outer_box = box_size
        self.inner_box = 0
        
        self.outer_half = self.outer_box/2 
        self.inner_half = 0

    def boundingRect(self):
        return QRectF(-self.outer_half,-self.outer_half,self.outer_box,self.outer_box)
    
    def paint(self, painter: QPainter, option, widget=None):
        outer_pen = QPen(QColor(self.color),2)
        outer_pen.setCosmetic(True)
        
        painter.setPen(outer_pen)
        painter.setBrush(QBrush(Qt.NoBrush))

        # Outer square
        outer_rect = QRectF(-self.outer_half,-self.outer_half,self.outer_box,self.outer_box)
        painter.drawRect(outer_rect)
 
class CameraScene(QGraphicsScene):
    
    def __init__(self, parent=None):
        QGraphicsScene.__init__(self, parent)
        
        self.image = None
        self.W = 0
        self.H = 0
        self.Wh = 0
        self.Hh = 0
        
        self.halo_size = 0
        
        self.current_roi = ROIItem('#FFD700')
        self.current_roi.setVisible(False)
        self.current_roi.setZValue(0)
        self.addItem(self.current_roi)
        
        # self.moving_roi = ROIItem('#FF1493')
        self.moving_roi = ROIItem('#DB7093')
        self.moving_roi.setVisible(False)
        self.moving_roi.setZValue(0)
        self.addItem(self.moving_roi)
        
    def has_image(self):
        return self.image is not None
        
    def set_frame(self,qimg:QImage):
        should_fit = False
        if self.image is None:
            self.image = QGraphicsPixmapItem()
            self.addItem(self.image)
            self.image.setZValue(-1)
            self.image.setPos(0,0)
            # self.image.setTransformationMode( Qt.TransformationMode.SmoothTransformation )
            self.image.setTransformationMode( Qt.TransformationMode.FastTransformation )
            should_fit = True
            
        pixmap = QPixmap.fromImage(qimg)
        self.image.setPixmap(pixmap)
        self.setSceneRect( self.image.boundingRect())
        self.W = self.sceneRect().width()
        self.H = self.sceneRect().height()
        
        return should_fit

    def show_current_roi(self,x,y,box_size):
        self.current_roi.set_box_size(box_size,self.halo_size)
        self.current_roi.setPos(x,y)
        self.current_roi.setVisible(True)
    
    def hide_current_roi(self):
        self.current_roi.setVisible(False)
        
    def config_moving_roi(self,box_size):
        self.moving_roi.set_box_size(box_size,self.halo_size)
        self.moving_roi.setPos(0,0)
        self.moving_roi.setVisible(False)
    
    def hide_moving_roi(self):
        self.moving_roi.setVisible(False)
        
    def try_move_moving_roi(self,new_pos:QPointF):
        x = new_pos.x()
        y = new_pos.y()
        
        in_range = (x > self.moving_roi.outer_half)
        in_range = (y > self.moving_roi.outer_half) and in_range
        in_range = (x < self.W-self.moving_roi.outer_half) and in_range
        in_range = (y < self.H-self.moving_roi.outer_half) and in_range
        
        if in_range:
            self.moving_roi.setVisible(True)
            self.moving_roi.setPos(x,y)
        else:
            self.moving_roi.setVisible(False)

###############################################################################

class CameraViewer(QGraphicsView):
    new_position = pyqtSignal(int,int)
    set_roi_up   = pyqtSignal()
    set_roi_down = pyqtSignal()
    
    def __init__(self, qimg_provider, parent=None, useOpenGL=True, background='#202020'):
        
        QGraphicsScene.__init__(self,parent)
        
        self.do_pan    = False
        self.start_pos = QPoint()
        self._qimg_provider = qimg_provider
        
        self.track_roi = False
        
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
        
        if event.button() in  (Qt.MiddleButton,Qt.RightButton):
            self.do_pan = True
            self.start_pos = event.pos()
        
        if event.button() == Qt.LeftButton:
            if self.track_roi:
                x = int( self.scene_handler.moving_roi.pos().x() )
                y = int( self.scene_handler.moving_roi.pos().y() )
                self.new_position.emit(x,y)
        
    def mouseReleaseEvent(self,event):
        super().mousePressEvent(event)
        
        if event.button() in  (Qt.MiddleButton,Qt.RightButton):
            self.do_pan = False
    
    def mouseMoveEvent(self,event):
        if self.do_pan:
            delta = self.start_pos - event.pos()
            hBar = self.horizontalScrollBar()
            vBar = self.verticalScrollBar()
            vBar.setValue(vBar.value() + delta.y())
            hBar.setValue(hBar.value() + delta.x())
            self.start_pos = event.pos()
            
        if self.track_roi:
            scene_pos = self.mapToScene(event.pos())
            self.scene_handler.try_move_moving_roi(scene_pos)
            
        super().mouseMoveEvent(event)
        
    def wheelEvent(self, event:QWheelEvent):
        if event.modifiers() == Qt.ControlModifier:
            if event.angleDelta().y() > 0:
                self.set_roi_up.emit()
            else:
                self.set_roi_down.emit()
        else:
            if event.angleDelta().y() > 0:
                self.zoom_in()
            else:
                self.zoom_out()
    
    @pyqtSlot(int,int)
    def roi_new_pos(self,x,y):
        self.scene_handler.current_roi.setPos(x,y)
    
    @pyqtSlot(int,int)
    def roi_new_siz(self,N,halo):
        self.scene_handler.halo_size = halo
        self.scene_handler.current_roi.set_box_size(N,halo)
        self.scene_handler.moving_roi.set_box_size(N,halo)
        self.scene_handler.current_roi.update()
        self.scene_handler.moving_roi.update()
    
    @pyqtSlot()
    def zoom_in(self):
        factor = 1.25
        self.scale(factor,factor)
    
    @pyqtSlot()
    def zoom_out(self):
        factor = 0.8
        self.scale(factor,factor)
        
    def show_current_roi(self,x,y,box_size):
        self.scene_handler.show_current_roi(x,y,box_size)
    
    def hide_current_roi(self):
        self.scene_handler.hide_current_roi()
        
    def enable_roi_tracking(self,x,y,box_size):
        self.scene_handler.show_current_roi(x,y,box_size)
        self.scene_handler.config_moving_roi(box_size)
        self.track_roi = True

    def disable_roi_tracking(self):
        self.scene_handler.hide_current_roi()
        self.scene_handler.hide_moving_roi()
        self.track_roi = False

############################################################################### Camera Viewer

class CameraWidget(QWidget):
    start_acquiring = pyqtSignal()
    stop_acquiring  = pyqtSignal()
    
    roi_new_pos = pyqtSignal(int,int)
    roi_new_siz = pyqtSignal(int,int)
    
    def __init__(self,camera_handler,camera_name,*args,**kwargs):
        super().__init__(*args,**kwargs)
        
        self.is_saving = False
        self.is_live = False
        self.working_dir = ""
        
        self.cam_handler = camera_handler
        self.cam_thread  = QThread(self)
        self.cam_handler.moveToThread(self.cam_thread)
        
        self.img2qimg    = ImageToQImage(self.cam_handler)
        self.img2qimg.set_outlier_range(0.002)
        self.img2qimg_th = QThread(self)
        self.img2qimg.moveToThread(self.img2qimg_th)
        
        self.img2tiff    = ImageToNDTiff(self.cam_handler)
        self.img2tiff_th = QThread(self)
        self.img2tiff.moveToThread(self.img2tiff_th)
        
        self.image = CameraViewer(self.img2qimg)
        
        self.upper_bar = self.create_upper_bar(camera_name)
        
        self.lower_panel = self.create_lower_panel()                
                   
        layout = QVBoxLayout()
        layout.addWidget(self.upper_bar  , stretch=0)
        layout.addWidget(self.image      , stretch=1)
        layout.addWidget(self.lower_panel, stretch=0)
        self.setLayout(layout)
        
        self.cam_handler.roi_set.connect( self.update_roi_state )
        self.cam_handler.frame_ready.connect(self.img2qimg.got_frame)
        self.cam_handler.frame_ready.connect(self.img2tiff.got_frame)
        
        self.image.new_position.connect( self.got_new_roi_position )
        self.image.set_roi_up  .connect( self.roi_up   )
        self.image.set_roi_down.connect( self.roi_down )
        
        self.start_acquiring.connect(self.cam_handler.acquire_frames)
        
        self.roi_new_pos.connect( self.image.roi_new_pos )
        self.roi_new_siz.connect( self.image.roi_new_siz )
        
        self.img2qimg.frame_ready.connect( self.update_image )
        self.img2tiff.finish_saving.connect( self.saving_finished )
        self.img2tiff.saving_progress.connect(lambda msg: self.frames.setText(msg))
        
        self.cam_thread.start()
        self.img2qimg_th.start()
        self.img2tiff_th.start()
    
    def create_upper_bar(self,camera_name):
        widget = QWidget()
        layout = QVBoxLayout()
        
        name_label = QLabel(f'<strong>{camera_name}</strong> [{self.cam_handler.vendor} - {self.cam_handler.model}]')
        name_label.setAlignment(Qt.AlignCenter | Qt.AlignVCenter)
        
        stat_widget = QWidget()
        stat_layout = QHBoxLayout()
        
        btn_zoom_full = create_iconized_button(_g_icon_prov.expand  ,tooltip='View full image')
        btn_zoom_in   = create_iconized_button(_g_icon_prov.zoom_in ,tooltip='Zoom in')
        btn_zoom_out  = create_iconized_button(_g_icon_prov.zoom_out,tooltip='Zoom out')
        
        btn_zoom_full.clicked.connect(self.image.fitScale)
        btn_zoom_in  .clicked.connect(self.image.zoom_in)
        btn_zoom_out .clicked.connect(self.image.zoom_out)
        
        stat_layout.addWidget(btn_zoom_full)
        stat_layout.addWidget(btn_zoom_in  )
        stat_layout.addWidget(btn_zoom_out )
        
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
        
        widget = QWidget()
        layout = QHBoxLayout()
        layout.setContentsMargins(0,0,0,0)
        
        layout.addWidget( self.create_lower_left()   )
        layout.addWidget( self.create_lower_middle() )
        layout.addWidget( self.create_lower_right()  )
        
        widget.setLayout(layout)
        return widget
    
    def create_lower_left(self):
        widget = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(0,0,0,0)
        
        buttons_widget = QWidget()
        buttons_layout = QHBoxLayout()
        buttons_layout.setContentsMargins(0,0,0,0)
        
        self.snap_button = create_iconized_button(_g_icon_prov.camera      ,tooltip='Grab a frame')
        self.snap_button.clicked.connect(self.cam_handler.snap_frame)
        
        self.live_button = create_iconized_button(_g_icon_prov.video_camera,tooltip='Start acquisition')
        self.live_button.clicked.connect(self.clicked_live)
        
        buttons_layout.addStretch()
        buttons_layout.addWidget(self.snap_button)
        buttons_layout.addWidget(self.live_button)
        buttons_layout.addStretch()
        buttons_widget.setLayout(buttons_layout)
        
        input_widget = QWidget()
        input_layout = QGridLayout()
        
        self.filename = QLineEdit()
        
        self.num_frames = QSpinBox()
        self.num_frames.setRange(0,2147483647)
        self.num_frames.setSingleStep(10)
        self.num_frames.setValue(0)
        self.frames = QLabel('')
        
        self.skip_frames = QSpinBox()
        self.skip_frames.setRange(1,2147483647)
        self.skip_frames.setSingleStep(1)
        self.skip_frames.setValue(1)
        self.est_frame_time = QLabel('')
        self.skip_frames.editingFinished.connect(self.skip_frames_changed)
        
        self.save_button = create_iconized_button(_g_icon_prov.floppy_disk_arrow_in,tooltip='Save frame/frames')
        self.save_button.clicked.connect(self.clicked_save)
        
        input_layout.addWidget(QLabel('Save to NDTiff:'),0,0)
        input_layout.addWidget(self.filename,0,1)
        input_layout.addWidget(self.save_button,0,2)
        
        input_layout.addWidget(QLabel('Num. Frames:'),1,0)
        input_layout.addWidget(self.num_frames,1,1)
        input_layout.addWidget(self.frames,1,2)
        
        input_layout.addWidget(QLabel('Save each N frames:'),2,0)
        input_layout.addWidget(self.skip_frames,2,1)
        input_layout.addWidget(self.est_frame_time,2,2)
        
        input_widget.setLayout(input_layout)
        
        layout.addWidget(buttons_widget)
        layout.addWidget(input_widget)
        
        widget.setLayout(layout)
        return widget
    
    def create_lower_middle(self):
        
        widget = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(0,0,0,0)
        
        ######## ROI Buttons
        
        roi_button_widget = QWidget()
        roi_button_layout = QHBoxLayout()
        roi_button_layout.setContentsMargins(0,0,0,0)
        self.roi_button_show = create_iconized_button(_g_icon_prov.square             ,tooltip='Show ROI')
        self.roi_button_pick = create_iconized_button(_g_icon_prov.border_out         ,tooltip='Pick ROI center')
        self.roi_button_in   = create_iconized_button(_g_icon_prov.scale_frame_reduce ,tooltip='ROI in')
        self.roi_button_out  = create_iconized_button(_g_icon_prov.scale_frame_enlarge,tooltip='ROI out')
        roi_button_layout.addWidget(self.roi_button_show)
        roi_button_layout.addWidget(self.roi_button_pick)
        roi_button_layout.addWidget(self.roi_button_in  )
        roi_button_layout.addWidget(self.roi_button_out )
        roi_button_widget.setLayout(roi_button_layout)
        
        self.roi_button_show.pressed.connect (self.current_roi_show )
        self.roi_button_show.released.connect(self.current_roi_hide )
        self.roi_button_pick.clicked.connect (self.clicked_roi_pick )
        self.roi_button_in  .clicked.connect (self.clicked_roi_in   )
        self.roi_button_out .clicked.connect (self.clicked_roi_out  )
        
        ######## ROI Fields
        
        roi_config_widget = QWidget()
        roi_config_layout = QHBoxLayout()
        roi_config_layout.setContentsMargins(0,0,0,0)
        self.roi_config_label = QLabel('Next ROI X/Y:')
        self.roi_config_pos_x = create_int_line_edit(0,4000,'X',IntMultipleOfValidator(self.cam_handler.step_roi_pos))
        self.roi_config_pos_y = create_int_line_edit(0,4000,'Y',IntMultipleOfValidator(self.cam_handler.step_roi_pos))
        self.roi_config_size  = SteppingSpinBox(step=self.cam_handler.step_roi_siz,current_value=512,max_value=4000)
        roi_config_layout.addWidget(self.roi_config_label)
        roi_config_layout.addWidget(self.roi_config_pos_x)
        roi_config_layout.addWidget(self.roi_config_pos_y)
        roi_config_layout.addWidget(QLabel('Size:'))
        roi_config_layout.addWidget(self.roi_config_size )
        roi_config_widget.setLayout(roi_config_layout)
        
        self.roi_config_pos_x.editingFinished.connect(self.roi_pos_modified)
        self.roi_config_pos_y.editingFinished.connect(self.roi_pos_modified)
        self.roi_config_size .editingFinished.connect(self.roi_siz_modified)
        
        ######## ROI auto-contrast
        
        roi_contrast_widget = QWidget()
        roi_contrast_layout = QHBoxLayout()
        roi_contrast_layout.setContentsMargins(0,0,0,0)
        
        self.contrast_value = create_doublespinbox(0.0,100,0.1,0.1)
        self.contrast_value.setSuffix('%')
        self.contrast_value.editingFinished.connect(self.update_contrast)
        
        btn1 = QPushButton('None')
        btn2 = QPushButton('0.01%')
        btn3 = QPushButton('0.1%')
        btn4 = QPushButton('1%')
        btn5 = QPushButton('5%')
        
        btn1.released.connect(lambda: self.update_autocontrast(0))
        btn2.released.connect(lambda: self.update_autocontrast(0.01))
        btn3.released.connect(lambda: self.update_autocontrast(0.1))
        btn4.released.connect(lambda: self.update_autocontrast(1))
        btn5.released.connect(lambda: self.update_autocontrast(5))
        
        roi_contrast_layout.addWidget(QLabel('Auto-contrast full range ignoring: '))
        roi_contrast_layout.addStretch()
        roi_contrast_layout.addWidget(btn1)
        roi_contrast_layout.addWidget(btn2)
        roi_contrast_layout.addWidget(btn3)
        roi_contrast_layout.addWidget(btn4)
        roi_contrast_layout.addWidget(btn5)
        roi_contrast_layout.addWidget(self.contrast_value)
        roi_contrast_widget.setLayout(roi_contrast_layout)
        
        ######## ROI update Fields and Buttons
        self.update_roi_state()
        
        layout.addWidget(roi_button_widget)
        layout.addWidget(roi_config_widget)
        layout.addWidget(roi_contrast_widget)
        
        widget.setLayout(layout)
        return widget
    
    def update_autocontrast(self,new_value):
        self.contrast_value.setValue(new_value)
        self.contrast_value.editingFinished.emit()
    
    def create_lower_right(self):
        
        widget = StyledFrame()
        # widget.setFrameShape(QFrame.StyledPanel)
        # widget.setFrameShadow(QFrame.Raised)
        layout = QFormLayout()
        # layout.setContentsMargins(0,0,0,0)
        
        # Exposure time
        exp_values    = self.cam_handler.get_exp_time_range()
        exp_cur_value = self.cam_handler.get_exp_time()
        if isinstance(exp_values, tuple):
            self.in_exp_time = QSpinBox()
            self.in_exp_time.setRange( exp_values[0], exp_values[1] )
            self.in_exp_time.setSingleStep(10)
            self.in_exp_time.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
            self.in_exp_time.setValue( int(exp_cur_value) )
            self.in_exp_time.editingFinished.connect( self.exposure_time_changed )
        elif isinstance(exp_values, list):
            self.in_exp_time = create_combo_box(exp_values,exp_cur_value,closer=True)
            self.in_exp_time.currentIndexChanged.connect(lambda idx: self.cam_handler.set_exp_time( float( self.in_exp_time.itemData(idx) ) ) )
        
        layout.addRow('Exposure time (ms):',self.in_exp_time)
        
        if hasattr(self.cam_handler,'video_mode'):
            video_mode_list  = self.cam_handler.get_video_mode_range()
            video_mode_value = self.cam_handler.get_video_mode()
            if isinstance(video_mode_list, list):
                self.in_video_mode = create_combo_box(video_mode_list,video_mode_value)
                self.in_video_mode.currentIndexChanged.connect(lambda idx: self.cam_handler.set_video_mode( self.in_video_mode.itemData(idx) ) )
                layout.addRow('Video Mode (binning)',self.in_video_mode)
        
        if hasattr(self.cam_handler,'cooler'):
            entries = self.cam_handler.get_cooler_range()
            value   = self.cam_handler.get_cooler()
            self.cooler_state = create_combo_box(entries,value)
            layout.addRow('Cooler state:',self.cooler_state)
            # self.cooler_state.setEnabled(False)

        widget.setLayout(layout)
        
        return widget
    
    @pyqtSlot()
    def start_acquisition(self):
        self.is_live = True
        update_iconized_button(self.live_button,_g_icon_prov.video_camera_off,tooltip='Stop acquisition')
        self.snap_button.setEnabled(False)
        self.start_acquiring.emit()
    
    @pyqtSlot()
    def stop_acquisition(self):
        self.is_live = False
        update_iconized_button(self.live_button,_g_icon_prov.video_camera,tooltip='Start acquisition')
        self.cam_handler.stop_acquisition()
        self.img2tiff.stop_acquisition()
        self.snap_button.setEnabled(True)
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
        file_name = normpath(join( self.working_dir,file_name))
        if not self.is_live:
            self.img2tiff.save_snap(file_name)
        elif self.is_saving:
            self.img2tiff.stop_acquisition()
        else:
            if self.num_frames.value() > 0:
                self.is_saving = True
                self.img2tiff.enable_autosave()
                self.img2tiff.start_acquisition(file_name,self.num_frames.value(),self.skip_frames.value())
                self.filename.setEnabled(False)
                self.num_frames.setEnabled(False)
                update_iconized_button(self.save_button,_g_icon_prov.square,tooltip='Stop acquisition')
            else:
                self.img2tiff.save_snap(file_name)
    
    @pyqtSlot()
    def saving_finished(self):
        self.is_saving = False
        self.filename.setEnabled(True)
        self.num_frames.setEnabled(True)
        update_iconized_button(self.save_button,_g_icon_prov.floppy_disk_arrow_in,tooltip='Save frame/frames')

    @pyqtSlot()
    def skip_frames_changed(self):
        self.est_frame_time.setText(f'({self.in_exp_time.value()*self.skip_frames.value()} ms)')

    @pyqtSlot()
    def exposure_time_changed(self):
        self.est_frame_time.setText(f'({self.in_exp_time.value()*self.skip_frames.value()} ms)')
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
    
    @pyqtSlot()
    def update_roi_state(self):
        cur_level = self.cam_handler.current_roi
        max_level = self.cam_handler.roi_levels
        
        if cur_level == 0:
            self._set_roi_state_first()
        elif cur_level == (max_level-1):
            self._set_roi_state_last()
        else:
            self._set_roi_state_middle()
            
        if cur_level < (max_level-1):
            self._set_roi_next_values()
        else:
            self._set_roi_no_values()
        
    def _set_roi_state_first(self):
        self.roi_button_show.setEnabled(True)
        self.roi_button_pick.setEnabled(True)
        self.roi_button_in  .setEnabled(True)
        self.roi_button_out .setEnabled(False)
    
    def _set_roi_state_last(self):
        self.roi_button_show.setEnabled(False)
        self.roi_button_pick.setEnabled(False)
        self.roi_button_in  .setEnabled(False)
        self.roi_button_out .setEnabled(True)
    
    def _set_roi_state_middle(self):
        self.roi_button_show.setEnabled(True)
        self.roi_button_pick.setEnabled(True)
        self.roi_button_in  .setEnabled(True)
        self.roi_button_out .setEnabled(True)
        
    def _set_roi_next_values(self):
        curr_level = self.cam_handler.current_roi
        next_level = curr_level + 1
        self.roi_config_label.setText(f'Current ROI: {curr_level}. Next ROI X/Y:')
        self.roi_config_pos_x.setEnabled(True)
        self.roi_config_pos_y.setEnabled(True)
        self.roi_config_size.setEnabled(True)
        x = self.cam_handler.roi_list[next_level]['rect'].x()
        y = self.cam_handler.roi_list[next_level]['rect'].y()
        w = self.cam_handler.roi_list[next_level]['rect'].width()
        h = self.cam_handler.roi_list[next_level]['rect'].height()
        assert w==h, f'Badly defined ROI ({x,y,w,h}).'
        self.roi_config_pos_x.setText(str(x+w//2))
        self.roi_config_pos_y.setText(str(y+h//2))
        self.roi_config_size.setValue(w)
        self.image.scene_handler.halo_size = self.cam_handler.roi_list[next_level]['halo']
        
    def _set_roi_no_values(self):
        curr_level = self.cam_handler.current_roi
        self.roi_config_pos_x.setEnabled(False)
        self.roi_config_pos_y.setEnabled(False)
        self.roi_config_size.setEnabled(False)
        self.roi_config_pos_x.setText('')
        self.roi_config_pos_y.setText('')
        self.roi_config_size.setValue(0)
        self.image.scene_handler.halo_size = 0
        self.roi_config_label.setText(f'Current ROI: {curr_level}. Next ROI unavailable.')
    
    def _get_roi_entries(self):
        x = 0
        y = 0
        x_text = self.roi_config_pos_x.text()
        if len(x_text) > 0:
            x = int(x_text)
        y_text = self.roi_config_pos_y.text()
        if len(y_text) > 0:
            y = int(y_text)
        N = self.roi_config_size.value()
        return x,y,N
    
    @pyqtSlot()
    def update_contrast(self):
        value = self.contrast_value.value()
        self.img2qimg.current_range = value/100
        
    def _scale_contrast_value(self,ratio):
        value = self.contrast_value.value()
        value = round( value/ratio, 2 )
        if value > 0.5:
            value = 0
        self.contrast_value.setValue(value)
        self.update_contrast()
    
    @pyqtSlot()
    def clicked_roi_in(self):
        x,y,N = self._get_roi_entries()
        ratio = self.cam_handler.next_roi(x,y,N)
        self._scale_contrast_value(ratio)
        if self.image.track_roi:
            self.image.disable_roi_tracking()
            update_iconized_button(self.roi_button_pick,_g_icon_prov.border_out,tooltip='Pick ROI center')
    
    @pyqtSlot()
    def clicked_roi_out(self):
        ratio = self.cam_handler.previous_roi()
        self._scale_contrast_value(ratio)
    
    @pyqtSlot()
    def current_roi_show(self):
        x,y,N = self._get_roi_entries()
        self.image.show_current_roi(x,y,N)
        
    @pyqtSlot()
    def current_roi_hide(self):
        self.image.hide_current_roi()
        
    @pyqtSlot()
    def clicked_roi_pick(self):
        if self.image.track_roi:
            self.image.disable_roi_tracking()
            update_iconized_button(self.roi_button_pick,_g_icon_prov.border_out,tooltip='Pick ROI center')
            self.roi_button_show.setEnabled(True)
        else:
            x,y,N = self._get_roi_entries()
            self.image.enable_roi_tracking(x,y,N)
            update_iconized_button(self.roi_button_pick,_g_icon_prov.xmark,tooltip='Cancel')
            self.roi_button_show.setEnabled(False)
            
    @pyqtSlot(int,int)
    def got_new_roi_position(self,x,y):
        base = self.cam_handler.step_roi_pos
        x = int(base*np.round(float(x)/base))
        y = int(base*np.round(float(y)/base))
        self.roi_config_pos_x.setText(str(x))
        self.roi_config_pos_y.setText(str(y))
        self.roi_new_pos.emit(x,y)
        
    @pyqtSlot()
    def roi_pos_modified(self):
        x,y,_ = self._get_roi_entries()
        self.roi_new_pos.emit(x,y)
        
    @pyqtSlot()
    def roi_siz_modified(self):
        N = self.roi_config_size.value()
        self.roi_new_siz.emit(N,0)
        
    @pyqtSlot()
    def roi_up(self):
        self.roi_config_size.stepUp()
        self.roi_siz_modified()
    
    @pyqtSlot()
    def roi_down(self):
        self.roi_config_size.stepDown()
        self.roi_siz_modified()
    
    def free(self):
        print('camera exiting...')
        if self.img2tiff_th and self.img2tiff_th.isRunning():
            self.img2tiff_th.quit()
            self.img2tiff_th.wait()  # Ensure thread stops before deleting
        
        if self.img2qimg_th and self.img2qimg_th.isRunning():
            self.img2qimg_th.quit()
            self.img2qimg_th.wait()  # Ensure thread stops before deleting
        
        if self.cam_thread and self.cam_thread.isRunning():
            self.cam_thread.quit()
            self.cam_thread.wait()  # Ensure thread stops before deleting
        
        
    

