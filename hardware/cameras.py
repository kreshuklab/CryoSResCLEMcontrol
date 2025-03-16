from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot
from PyQt5.QtCore import QRect, QTimer
from datetime import datetime
import numpy as np

############################################################################### CameraDevice

class _CameraDevice(QObject):
    _acquire = pyqtSignal()
    _snap    = pyqtSignal()
    _stopped = pyqtSignal()
    roi_set  = pyqtSignal()
    
    frame_ready = pyqtSignal()
    acquisition_started  = pyqtSignal()
    acquisition_finished = pyqtSignal()
    
    def __init__(self,unique_id,vendor,model,roi_levels,pix_size_nm,exp_time_ms,step_roi_pos=1,step_roi_siz=1):
        super().__init__()
        
        self.frame_buffer = np.zeros((0,0))
        self.frame_count  = int(0)
        self.timestamp    = datetime.now()
       
        self.uid         = unique_id
        self.vendor      = vendor
        self.model       = model
        self.roi_levels  = max(roi_levels,1)
        self.pix_size_nm = pix_size_nm
        
        self.step_roi_pos = step_roi_pos
        self.step_roi_siz = step_roi_siz
        
        self.is_busy = False
        self.do_image = False
        self.done_acquiring = False
        
        self.set_exp_time(exp_time_ms)
        self.init_roi_list()
        self.set_roi_by_index(0)
        
        self._update_configuration_function = None
        self._update_configuration_argument = None
        
        self._stopped.connect( self._update_configuration )
        self._acquire.connect( self.acquire_frames )
        
    ##################################################### Configuration updater
    
    @pyqtSlot()
    def _update_configuration(self):
        if self._update_configuration_function is not None:
            if self._update_configuration_argument is None:
                self._update_configuration_function()
            else:
                self._update_configuration_function(*self._update_configuration_argument)
            self._update_configuration_function = None
            self._update_configuration_argument = None
            self._acquire.emit()
        
    ############################################################# Exposure Time
    
    def get_exp_time_range(self): # To Be Implemented by Child
        return (0,500)
    
    def set_exp_time(self,exp_time_ms):
        self.exp_time_ms = exp_time_ms
        if self.do_image:
            self._update_configuration_function = self.write_exp_time
            self._update_configuration_argument = None
            self.stop_acquisition()
        else:
            self.write_exp_time()
    
    def get_exp_time(self):
        if self.is_busy:
            print(f'[{self.uid}: {self.vendor} - {self.model}] Device busy, returning configured exposure time.')
            return self.exp_time_ms
        else:
            return self.read_exp_time()

    def read_exp_time(self): # To Be Implemented by Child
        print(f'read_exp_time not implemented ({self.uid}: {self.vendor} - {self.model})')
        return self.exp_time_ms
    
    def write_exp_time(self): # To Be Implemented by Child
        print(f'write_exp_time not implemented ({self.uid}: {self.vendor} - {self.model})')
    
    ####################################################################### ROI
    
    def init_roi_list(self):
        self.roi_list = []
        self.roi_list.append(self._get_full_chip_size())
        for roi_index in range(1,self.roi_levels):
            entry = self._get_default_roi_level(roi_index)
            if entry is not None:
                self.roi_list.append(entry)
                
    def next_roi(self,center_x,center_y,box_size):
        next_roi = self.current_roi + 1
        if next_roi < self.roi_levels:
            self.config_roi(next_roi,center_x,center_y,box_size)
            if self.do_image:
                self._update_configuration_function = self.set_roi_by_index
                self._update_configuration_argument = (next_roi,)
                self.stop_acquisition()
            else:
                self.set_roi_by_index(next_roi)
    
    def previous_roi(self,center_x,center_y,box_size):
        previous_roi = self.current_roi - 1
        if previous_roi >= 0:
            self.config_roi(previous_roi,center_x,center_y,box_size)
            if self.do_image:
                self._update_configuration_function = self.set_roi_by_index
                self._update_configuration_argument = (previous_roi,)
                self.stop_acquisition()
            else:
                self.set_roi_by_index(previous_roi)
    
    def config_roi(self,roi_index,center_x,center_y,box_size):
        if (roi_index < len(self.roi_list)) and (roi_index>0):
            x = center_x - box_size//2
            y = center_y - box_size//2
            self.roi_list[roi_index]['rect'].setRect(x,y,box_size,box_size)
            print(self.roi_list)
    
    def set_roi_by_index(self,roi_index):
        print('set_roi_by_index',roi_index)
        if roi_index < len(self.roi_list):
            if roi_index == 0:
                self.set_full_roi()
                self.current_roi = roi_index
            elif self.set_roi( self.roi_list[roi_index]['rect'] ):
                self.current_roi = roi_index
            else:
                x = self.roi_list[roi_index]['rect'].x()
                y = self.roi_list[roi_index]['rect'].y()
                w = self.roi_list[roi_index]['rect'].width()
                h = self.roi_list[roi_index]['rect'].height()
                print(f'[{self.uid}: {self.vendor} - {self.model}] Error setting ROI ({x},{y},{w},{h})')
        else:
            print(f'[{self.uid}: {self.vendor} - {self.model}] Requesting invalid ROI')
        self.roi_set.emit()
    
    def set_full_roi(self): # To Be Implemented by Child
        print(f'set_full_roi not implemented ({self.uid}: {self.vendor} - {self.model})')
        return True
    
    def set_roi(self,roi_rect:QRect): # To Be Implemented by Child
        print(f'set_roi not implemented ({self.uid}: {self.vendor} - {self.model})')
        return True
    
    def _get_default_roi_level(self,roi_index):
        if (roi_index > 0) and (roi_index < (self.roi_levels+1)):
            w = self.roi_list[0]['rect'].width()
            h = self.roi_list[0]['rect'].height()
            bin_factor = 2**roi_index
            box_size = min( w//bin_factor, h//bin_factor )
            x = w//2 - box_size//2
            y = h//2 - box_size//2
            entry = {'rect':QRect(x,y,box_size,box_size),'halo':0}
            return entry
        else:
            return None
    
    def _get_full_chip_size(self): # To Be Implemented by Child
        print(f'_get_full_chip_size not implemented ({self.uid}: {self.vendor} - {self.model})')
        entry = {'rect':QRect(),'halo':0}
        return entry
    
    ################################################################ Snap Frame
    
    @pyqtSlot()
    def snap_frame(self):
        if self.is_busy:
            print(f'{self.uid}: [{self.vendor} - {self.model}] Busy - Ignoring snap request.')
            return
        
        self.is_busy = True
        self._do_snap_frame()
        self.is_busy = False
        
    def _do_snap_frame(self): # To Be Implemented by Child
        print(f'_do_snap_frame not implemented ({self.uid}: {self.vendor} - {self.model})')
    
    ########################################################## Live Acquisition
    
    @pyqtSlot()
    def acquire_frames(self):
        self.acquire_n_frames(-1)
        
    @pyqtSlot(int)
    def acquire_n_frames(self,max_frames):
        if self.is_busy:
            print(f'{self.uid}: [{self.vendor} - {self.model}] Busy - Ignoring snap request.')
            return
        
        self.is_busy  = True
        self.do_image = True
        self.acquisition_started.emit()
        self._do_acquire_frames(max_frames)
        self.is_busy = False
        self._stopped.emit()
        self.acquisition_finished.emit()

    def _do_acquire_frames(self,max_frames): # To Be Implemented by Child
        print(f'_do_acquire_frames not implemented ({self.uid}: {self.vendor} - {self.model})')

    def stop_acquisition(self):
        self.do_image = False

############################################################################### DummyDevice

class DummyCamera(_CameraDevice):
    
    ############################################################# CTOR and DTOR
    
    def __init__(self,name,camera_index=0,exposure_time_ms=100):
        
        self.raw_image = _imread('resources/SWTestbild_upscaled.tif')
        
        vendor = 'TestCamera'
        model  = 'Telefunken_Test_Card_T05'
        roi_levels = 2
        
        super().__init__(name,vendor,model,roi_levels,136,exposure_time_ms,step_roi_pos=4,step_roi_siz=8)
        self._internal_frame = np.zeros(self.raw_image.shape,np.uint16)
        self.x0 = 0
        self.y0 = 0
        self.x1 = self.raw_image.shape[1]
        self.y1 = self.raw_image.shape[0]
            
    def __del__(self):
        pass
    
    ############################################### Implement common properties
    
    def _get_full_chip_size(self):
        h,w = self.raw_image.shape
        entry = {'rect':QRect(0,0,int(w),int(h)),'halo':0}
        return entry
    
    def set_full_roi(self):
        self.x0 = 0
        self.y0 = 0
        self.x1 = self.raw_image.shape[1]
        self.y1 = self.raw_image.shape[0]
        return True
        
    def set_roi(self,roi:QRect):
        self.x0 = roi.x()
        self.y0 = roi.y()
        self.x1 = roi.x() + roi.width()
        self.y1 = roi.y() + roi.height()
        return True
        
    def write_exp_time(self):
        pass
    
    def read_exp_time(self):
        return self.exp_time_ms
    
    ##################################################### Acquisition functions
    
    def _gen_frame(self):
        self._buffer_f32  = np.float32(self.raw_image[self.y0:self.y1,self.x0:self.x1])
        self._buffer_f32 += np.random.normal(0,25*(300-self.exp_time_ms),self._buffer_f32.shape)
        self._buffer_u16  = np.uint16( self._buffer_f32.clip(0,65535) )
        return self._buffer_u16
        
    def _do_snap_frame(self):
        self.frame_buffer = self._gen_frame()
        self.frame_count  = 0
        self.timestamp    = datetime.now()
        self.frame_ready.emit()
        
    @pyqtSlot()
    def _do_acquire_frames(self,max_frames):
        
        self.frame_count = 0
        self.done_acquiring = False
        
        while self.do_image and not self.done_acquiring:
            t0 = datetime.now()
            self.frame_buffer = self._gen_frame()
            self.timestamp    = datetime.now()
            self.frame_count += 1
            self.frame_ready.emit()
            t1 = datetime.now()
            delta = t1 - t0
            delta = delta.total_seconds()*1000
            if delta < self.exp_time_ms:
                _sleep( (self.exp_time_ms-delta)/1000 )
            self.done_acquiring = (self.frame_count>=max_frames) and (max_frames>0)
        self.do_image = False
        self.done_acquiring = True

############################################################################### HamamatsuCamera

try:
    from .dcam import Dcamapi, Dcam
    from .dcamapi4 import DCAM_IDPROP,DCAMPROP,DCAM_IDSTR,DCAM_PIXELTYPE
    _should_use_dcam = True
except:
    _should_use_dcam = False
    print('DCAM libraries not found, using a dummy camera')

if _should_use_dcam:
    class HamamatsuCamera(_CameraDevice):
        
        ############################################################# CTOR and DTOR
        
        def __init__(self,name,camera_index=0,exposure_time_ms=100,default_roi=0):
            
            assert Dcamapi.init(), "Cannot connect to DCAM (Hamamatsu) driver.\n Do you have one? or is it being used by another software?"
            self.camera = Dcam(camera_index)
            assert self.camera.dev_open(), f"Failed to open camera {camera_index}."
            
            vendor = self.camera.dev_getstring(DCAM_IDSTR.VENDOR)
            model  = self.camera.dev_getstring(DCAM_IDSTR.MODEL)
            roi_levels = 2
            
            # Configuration of common parameter for cameras
            super().__init__(name,vendor,model,roi_levels,
                             pix_size_nm=136,
                             exp_time_ms=exposure_time_ms,
                             step_roi_pos=4,
                             step_roi_siz=8)
            
            self.frame_timeout_ms = 1000
            self.set_cooler_on()
            self.set_uint16()
            self.set_roi_by_index(default_roi)
            
        def __del__(self):
            self.camera.dev_close()
            Dcamapi.uninit()
        
        ########################################################## Extra Properties
        
        def set_uint16(self):
            self.camera.prop_setvalue(DCAM_IDPROP.IMAGE_PIXELTYPE,DCAM_PIXELTYPE.MONO16)
        
        def get_cooler_range(self):
            return [False,True]
        
        def set_cooler_on(self):
            self.cooler = True
            self.camera.prop_setvalue(DCAM_IDPROP.SENSORCOOLER,DCAMPROP.MODE.ON)
        
        def set_cooler_off(self):
            self.cooler = False
            self.camera.prop_setvalue(DCAM_IDPROP.SENSORCOOLER,DCAMPROP.MODE.OFF)
        
        def set_cooler(self,turn_on:bool):
            if turn_on:
                self.set_cooler_on()
            else:
                self.set_cooler_off()
        
        def get_cooler(self):
            self.cooler = True if self.camera.prop_getvalue(DCAM_IDPROP.SENSORCOOLER) == DCAMPROP.MODE.ON else False
            return self.cooler
        
        ############################################### Implement common properties
        
        def _get_full_chip_size(self):
            w = self.camera.prop_getvalue(DCAM_IDPROP.IMAGE_WIDTH)
            h = self.camera.prop_getvalue(DCAM_IDPROP.IMAGE_HEIGHT)
            entry = {'rect':QRect(0,0,int(w),int(h)),'halo':0}
            return entry
        
        def set_full_roi(self):
            self.camera.prop_setvalue(DCAM_IDPROP.SUBARRAYMODE,DCAMPROP.MODE.OFF)
            return True
            
        def set_roi(self,roi:QRect):
            w = float(roi.width())
            h = float(roi.height())
            x = float(roi.x())
            y = float(roi.y())
            self.camera.prop_setvalue(DCAM_IDPROP.SUBARRAYHPOS, x)
            self.camera.prop_setvalue(DCAM_IDPROP.SUBARRAYVPOS, y)
            self.camera.prop_setvalue(DCAM_IDPROP.SUBARRAYHSIZE,w)
            self.camera.prop_setvalue(DCAM_IDPROP.SUBARRAYVSIZE,h)
            self.camera.prop_setvalue(DCAM_IDPROP.SUBARRAYMODE,DCAMPROP.MODE.ON)
            return True
            
        def write_exp_time(self):
            exp_time_sec = float(self.exp_time_ms)/1000
            self.camera.prop_setgetvalue(DCAM_IDPROP.EXPOSURETIME,exp_time_sec)
        
        def read_exp_time(self):
            return self.camera.prop_getvalue(DCAM_IDPROP.EXPOSURETIME)*1000
        
        ##################################################### Acquisition functions
        
        def _do_snap_frame(self):
            assert self.camera.buf_alloc(1), "Failed to create buffer for camera"
            
            if self.camera.cap_snapshot():
                if self.camera.wait_capevent_frameready(self.frame_timeout_ms):
                    self.frame_buffer = self.camera.buf_getlastframedata()
                    self.frame_count  = 0
                    self.timestamp    = datetime.now()
                    self.frame_ready.emit()
            
            self.camera.buf_release()
            
        @pyqtSlot()
        def _do_acquire_frames(self,max_frames):
            
            assert self.camera.buf_alloc(3), "Failed to create buffer for camera"
            
            self.frame_count = 0
            self.done_acquiring = False
            if self.camera.cap_start():
                while self.do_image and not self.done_acquiring:
                    if self.camera.wait_capevent_frameready(self.frame_timeout_ms):
                        self.frame_buffer = self.camera.buf_getlastframedata()
                        self.timestamp    = datetime.now()
                        self.frame_count += 1
                        self.frame_ready.emit()
                    self.done_acquiring = (self.frame_count>=max_frames) and (max_frames>0)
                self.do_image = False
                self.done_acquiring = True
            self.camera.cap_stop()
            self.camera.buf_release()

else:
    from tifffile import imread as _imread
    from time import sleep as _sleep
    
    HamamatsuCamera = DummyCamera
    
# %%
