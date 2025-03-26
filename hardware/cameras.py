from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot
from PyQt5.QtCore import QRect
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
        
        # self.hotpix_list = list()
        # self.hotpix_ref  = QRect()
        
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
    
    ################################################################ Hot Pixels
    
    # def hotpix_ref_update(self,new_ref):
    #     self.hotpix_ref.setRect(new_ref)
    
    # def hotpix_list_update(self,hotpix_list):
    #     self.hotpix_list = list(hotpix_list)
    
    ####################################################################### ROI
    
    def init_roi_list(self):
        self.roi_list = []
        self.roi_list.append(self._get_full_chip_size())
        for roi_index in range(1,self.roi_levels):
            entry = self._get_default_roi_level(roi_index)
            if entry is not None:
                self.roi_list.append(entry)
                
    def next_roi(self,center_x,center_y,box_size):
        area_ratio = 1
        next_roi = self.current_roi + 1
        if next_roi < self.roi_levels:
            self.config_roi(next_roi,center_x,center_y,box_size)
            cur_area = self.roi_list[self.current_roi]['rect'].width()*self.roi_list[self.current_roi]['rect'].height()    
            new_area = self.roi_list[next_roi]['rect'].width()*self.roi_list[next_roi]['rect'].height()
            area_ratio = new_area/cur_area
            if self.do_image:
                self._update_configuration_function = self.set_roi_by_index
                self._update_configuration_argument = (next_roi,)
                self.stop_acquisition()
            else:
                self.set_roi_by_index(next_roi)
        return area_ratio
    
    def previous_roi(self,center_x,center_y,box_size):
        area_ratio = 1
        previous_roi = self.current_roi - 1
        if previous_roi >= 0:
            self.config_roi(previous_roi,center_x,center_y,box_size)
            cur_area = self.roi_list[self.current_roi]['rect'].width()*self.roi_list[self.current_roi]['rect'].height()    
            new_area = self.roi_list[previous_roi]['rect'].width()*self.roi_list[previous_roi]['rect'].height()
            area_ratio = new_area/cur_area
            if self.do_image:
                self._update_configuration_function = self.set_roi_by_index
                self._update_configuration_argument = (previous_roi,)
                self.stop_acquisition()
            else:
                self.set_roi_by_index(previous_roi)
        return area_ratio
    
    def config_roi(self,roi_index,center_x,center_y,box_size):
        if (roi_index < len(self.roi_list)) and (roi_index>0):
            x = center_x - box_size//2
            y = center_y - box_size//2
            self.roi_list[roi_index]['rect'].setRect(x,y,box_size,box_size)
    
    def set_roi_by_index(self,roi_index):
        if roi_index < len(self.roi_list):
            if roi_index == 0:
                self.set_full_roi()
                self.current_roi = roi_index
                # self.hotpix_ref_update( self.roi_list[roi_index]['rect'] )
            elif self.set_roi( self.roi_list[roi_index]['rect'] ):
                self.current_roi = roi_index
                # self.hotpix_ref_update( self.roi_list[roi_index]['rect'] )
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
            box_size = int(  self.step_roi_siz*np.round( box_size/self.step_roi_siz ) )
            x = w//2 - box_size//2
            y = h//2 - box_size//2
            x = int(  self.step_roi_pos*np.round( x/self.step_roi_pos ) )
            y = int(  self.step_roi_pos*np.round( y/self.step_roi_pos ) )
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
        print('A')
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

from tifffile import imread as _imread
from time import sleep as _sleep

class DummyCamera(_CameraDevice):
    
    ############################################################# CTOR and DTOR
    
    def __init__(self,name,camera_index=0,exposure_time_ms=100):
        self.raw_image = _imread('resources/SWTestbild_upscaled.tif')
        
        vendor = 'TestCamera'
        model  = 'Telefunken_Test_Card_T05'
        roi_levels = 2
        
        super().__init__(name,vendor,model,roi_levels,136,exposure_time_ms,step_roi_pos=4,step_roi_siz=8)
        
        self.init_roi_list()
        self.set_roi_by_index(0)
        
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
        
        def __init__(self,name,camera_index=0,exposure_time_ms=100,default_roi=0,step_roi_pos=8,step_roi_siz=8):
            
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
            
            self.init_roi_list()
            self.set_roi_by_index(0)
            
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
    HamamatsuCamera = DummyCamera
    
############################################################################### PySpinCamera

try:
    import PySpin as pyspin
    _should_use_pyspin = True
except:
    _should_use_pyspin = False
    print('PySpin libraries not found, using a dummy camera')

if _should_use_pyspin:
    
    class PySpinCamera(_CameraDevice):
        
        ############################################################# CTOR and DTOR
        
        def __init__(self,name,camera_index=0,exposure_time_ms=100,default_roi=0):
            
            self.cam_sys = pyspin.System.GetInstance()
            self.cam_list = self.cam_sys.GetCameras()
            assert camera_index < self.cam_list.GetSize(), f'PySpin (Chameleon): Trying to use camera with index {camera_index} when\nthere are only {self.cam_list.GetSize()} cameras available.'
            self.camera = self.cam_list.GetByIndex(camera_index)
            self.camera.Init()
            
            vendor = self.camera.DeviceVendorName.ToString()
            model  = self.camera.DeviceModelName.ToString()
            roi_levels = 2
            
            self._exp_real_time_ms = 20
            self._exp_buffer_size  = 0
            
            # Configuration of common parameter for cameras
            super().__init__(name,vendor,model,roi_levels,
                             pix_size_nm=136,
                             exp_time_ms=exposure_time_ms,
                             step_roi_pos=4,
                             step_roi_siz=8)
            
            # Configure camera
            # Load default
            self.camera.UserSetSelector.SetValue(pyspin.UserSetSelector_Default)
            self.camera.UserSetLoad()
            
            # Set acquisition mode
            self.camera.AcquisitionMode.SetValue(pyspin.AcquisitionMode_Continuous)
            
            # Set Gain
            self.camera.GainAuto.SetValue(pyspin.GainAuto_Off)
            gain = min(self.camera.Gain.GetMax(),24)
            self.camera.Gain.SetValue(gain)
    
            # Set Pixel format
            self.set_uint16()
            
            # Default Video Mode
            self.set_video_mode('Mode1')
            
            self.set_roi_by_index(default_roi)
            
        def __del__(self):
            self.camera.DeInit()
            del self.camera
            self.cam_list.Clear()
            self.cam_sys.ReleaseInstance()
            
        ########################################################## Extra Properties
        
        def set_uint16(self):
            self.camera.PixelFormat.SetValue(pyspin.PixelFormat_Mono16)
            
        def get_video_mode_range(self):
            return ['Mode0','Mode1']
        
        def set_video_mode(self,video_mode:str):
            if self.do_image:
                self._update_configuration_function = self.write_video_mode
                self._update_configuration_argument = (video_mode,)
                self.stop_acquisition()
            else:
                self.write_video_mode(video_mode)
        
        def write_video_mode(self,video_mode:str):
            self.video_mode  = video_mode
            nodemap          = self.camera.GetNodeMap()
            video_mode_node  = pyspin.CEnumerationPtr(nodemap.GetNode("VideoMode"))
            video_mode_entry = video_mode_node.GetEntryByName(self.video_mode).GetValue()
            video_mode_node.SetIntValue(video_mode_entry)
            
            self.init_roi_list()
            self.set_roi_by_index(0)
            
        def get_video_mode(self):
            return self.video_mode
            
        
        ############################################### Implement common properties
        
        def _get_full_chip_size(self):
            w = self.camera.WidthMax.GetValue()
            h = self.camera.HeightMax.GetValue()
            entry = {'rect':QRect(0,0,int(w),int(h)),'halo':0}
            return entry
        
        def set_full_roi(self):
            self.set_roi( self.roi_list[0]['rect'] )
            return True
        
        def config_roi(self,roi_index,center_x,center_y,box_size):
            if (roi_index < len(self.roi_list)) and (roi_index>0):
                max_w = self.camera.WidthMax.GetValue()
                max_h = self.camera.HeightMax.GetValue()
                
                x = (max_w - center_x) - box_size//2
                y = (max_h - center_y) - box_size//2
                self.roi_list[roi_index]['rect'].setRect(x,y,box_size,box_size)
            
        def set_roi(self,roi:QRect):
            self.camera.OffsetX.SetValue(0)
            self.camera.OffsetY.SetValue(0)
            w = int(roi.width())
            h = int(roi.height())
            x = int(roi.x())
            y = int(roi.y())
            self.camera.Width.SetValue(w)
            self.camera.Height.SetValue(h)
            self.camera.OffsetX.SetValue(x)
            self.camera.OffsetY.SetValue(y)
            return True
        
        def get_exp_time_range(self):
            return np.arange(20,210,20).tolist()
            
        def write_exp_time(self):
            self.camera.ExposureAuto.SetValue(pyspin.ExposureAuto_Off)
            self._exp_real_time_ms = 20
            self._exp_buffer_size  = int(np.ceil( self.exp_time_ms/self._exp_real_time_ms ))
            exp_time_us = self._exp_real_time_ms * 1e3
            exp_time_us = min(self.camera.ExposureTime.GetMax(),exp_time_us)
            self.camera.ExposureTime.SetValue(exp_time_us)
        
        def read_exp_time(self):
            exp_time_us = self.camera.ExposureTime.GetValue()
            return self._exp_buffer_size * exp_time_us / 1e3
        
        ##################################################### Acquisition functions
        
        def _do_snap_frame(self):
            w = self.camera.Width.GetValue()
            h = self.camera.Height.GetValue()
            self._internal_frame_buffer = np.zeros( (self._exp_buffer_size,int(h),int(w)), np.uint16 )
            
            self.camera.BeginAcquisition()
            
            for i in range(self._exp_buffer_size):
                # Grab image
                in_image = self.camera.GetNextImage()
                in_w     = in_image.GetWidth()
                in_h     = in_image.GetHeight()
                self._internal_frame_buffer[i,:,:] = np.array(in_image.GetData()).reshape( (in_h,in_w) )
                in_image.Release()
                
            self.frame_buffer = np.uint16(self._internal_frame_buffer.sum(axis=0).clip(0,65535))
            self.frame_count  = 0
            self.timestamp    = datetime.now()
            self.frame_ready.emit()
                
            self.camera.EndAcquisition()
            
        @pyqtSlot()
        def _do_acquire_frames(self,max_frames):
            w = self.camera.Width.GetValue()
            h = self.camera.Height.GetValue()
            self._internal_frame_buffer = np.zeros( (self._exp_buffer_size,int(h),int(w)), np.uint16 )
            
            self.camera.BeginAcquisition()
            
            self.frame_count = 0
            self.done_acquiring = False
            
            while self.do_image and not self.done_acquiring:
                
                for i in range(self._exp_buffer_size):
                    # Grab image
                    in_image = self.camera.GetNextImage()
                    in_w     = in_image.GetWidth()
                    in_h     = in_image.GetHeight()
                    self._internal_frame_buffer[i,:,:] = np.array(in_image.GetData()).reshape( (in_h,in_w) )
                    in_image.Release()
                    
                self.frame_buffer = np.uint16(self._internal_frame_buffer.sum(axis=0).clip(0,65535))
                self.timestamp    = datetime.now()
                self.frame_count += 1
                self.frame_ready.emit()
                
                self.done_acquiring = (self.frame_count>=max_frames) and (max_frames>0)
            
            self.do_image = False
            self.done_acquiring = True
            self.camera.EndAcquisition()

else:
    PySpinCamera = DummyCamera
    




# %%
