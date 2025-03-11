from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot
from PyQt5.QtCore import QRect
import numpy as np
from datetime import datetime

############################################################################### CameraDevice

class _CameraDevice(QObject):
    _acquire    = pyqtSignal()
    _snap       = pyqtSignal()
    _stopped    = pyqtSignal()
    
    frame_ready = pyqtSignal()
    acquisition_started  = pyqtSignal()
    acquisition_finished = pyqtSignal()
    
    def __init__(self,unique_id,vendor,model,roi_levels,pix_size_nm,exp_time_ms,gain=None,binning=None):
        super().__init__()
        
        self.frame_buffer = np.zeros((0,0))
        self.frame_count  = int(0)
        self.timestamp    = datetime.now()
       
        self.uid         = unique_id
        self.vendor      = vendor
        self.model       = model
        self.roi_levels  = max(roi_levels,1)
        self.pix_size_nm = pix_size_nm
        
        self.is_busy = False
        self.is_acquiring   = False
        self.done_acquiring = False
        
        self.set_exp_time(exp_time_ms)
        if gain is not None:
            self.set_gain(gain)
        if binning is not None:
            self.set_binning(binning)
        self.init_roi_list()
        self.set_roi_by_index(0)
        
        self._update_configuration_function = None
        
        self._stopped.connect( self._update_configuration )
        self._acquire.connect( self.acquire_frames )
        
    ##################################################### Configuration updater
    
    @pyqtSlot()
    def _update_configuration(self):
        if self._update_configuration_function is not None:
            self._update_configuration_function()
            self._update_configuration_function = None
            self._acquire.emit()
        
    ############################################################# Exposure Time
    
    def get_exp_time_range(self): # To Be Implemented by Child
        return (0,500)
    
    def set_exp_time(self,exp_time_ms):
        self.exp_time_ms = exp_time_ms
        if self.is_acquiring:
            self._update_configuration_function = self.write_exp_time()
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
    
    ###################################################################### Gain
    
    def get_gain_range(self): # To Be Implemented by Child
        return (0,0)
    
    def set_gain(self,gain):
        print(f'set_gain not implemented ({self.uid}: {self.vendor} - {self.model})')

    ################################################################### Binning
    
    def get_binning_list(self): # To Be Implemented by Child
        return (1,)
    
    def set_binning(self,binning):
        print(f'set_binning not implemented ({self.uid}: {self.vendor} - {self.model})')
    
    ####################################################################### ROI
    
    def init_roi_list(self):
        self.roi_list = []
        self.roi_list.append(self._get_full_chip_size())
        
    def set_roi_by_index(self,roi_index):
        if roi_index < len(self.roi_list):
            if self.set_roi( self.roi_list[roi_index] ):
                self.current_roi = roi_index
            else:
                x = self.roi_list[roi_index].x()
                y = self.roi_list[roi_index].y()
                w = self.roi_list[roi_index].width()
                h = self.roi_list[roi_index].height()
                print(f'[{self.uid}: {self.vendor} - {self.model}] Error setting ROI ({x},{y},{w},{h})')
        else:
            print(f'[{self.uid}: {self.vendor} - {self.model}] Requesting invalid ROI')
    
    def set_full_roi(self): # To Be Implemented by Child
        print(f'set_full_roi not implemented ({self.uid}: {self.vendor} - {self.model})')
        return True
    
    def set_roi(self,roi_rect:QRect): # To Be Implemented by Child
        print(f'set_roi not implemented ({self.uid}: {self.vendor} - {self.model})')
        return True
    
    def _get_full_chip_size(self): # To Be Implemented by Child
        print(f'_get_full_chip_size not implemented ({self.uid}: {self.vendor} - {self.model})')
        return QRect()
    
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

############################################################################### HamamatsuCamera

from .dcam import Dcamapi, Dcam
from .dcamapi4 import DCAM_IDPROP,DCAMPROP,DCAM_IDSTR,DCAM_PIXELTYPE

class HamamatsuCamera(_CameraDevice):
    
    ############################################################# CTOR and DTOR
    
    def __init__(self,name,camera_index=0,exposure_time_ms=100):
        
        assert Dcamapi.init(), "Cannot connect to DCAM (Hamamatsu) driver."
        self.camera = Dcam(camera_index)
        assert self.camera.dev_open(), f"Failed to open camera {camera_index}."
        
        vendor = self.camera.dev_getstring(DCAM_IDSTR.VENDOR)
        model  = self.camera.dev_getstring(DCAM_IDSTR.MODEL)
        roi_levels = 2
        
        super().__init__(name,vendor,model,roi_levels,136,exposure_time_ms)
        
        self.frame_timeout_ms = 1000
        self.set_cooler_on()
        self.set_uint16()
        
    def __del__(self):
        self.camera.dev_close()
        Dcamapi.uninit()
    
    ########################################################## Extra Properties
    
    def set_uint16(self):
        self.camera.prop_setvalue(DCAM_IDPROP.IMAGE_PIXELTYPE,DCAM_PIXELTYPE.MONO16)
    
    def set_cooler_on(self):
        self.camera.prop_setvalue(DCAM_IDPROP.SENSORCOOLER,DCAMPROP.MODE.ON)
    
    def set_cooler_off(self):
        self.camera.prop_setvalue(DCAM_IDPROP.SENSORCOOLER,DCAMPROP.MODE.OFF)
    
    def set_cooler(self,turn_on:bool):
        if turn_on:
            self.set_cooler_on()
        else:
            self.set_cooler_off()
    
    def get_cooler(self):
        return True if self.camera.prop_getvalue(DCAM_IDPROP.SENSORCOOLER) == DCAMPROP.MODE.ON else False
    
    ############################################### Implement common properties
    
    def _get_full_chip_size(self):
        w = self.camera.prop_getvalue(DCAM_IDPROP.IMAGE_WIDTH)
        h = self.camera.prop_getvalue(DCAM_IDPROP.IMAGE_HEIGHT)
        return QRect(0,0,int(w),int(h))
    
    def set_full_roi(self):
        self.camera.prop_setvalue(DCAM_IDPROP.SUBARRAYMODE,DCAMPROP.MODE.OFF)
        return True
        
    def set_roi(self,roi:QRect):
        x = float(roi.x())
        y = float(roi.y())
        w = float(roi.width())
        h = float(roi.height())
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
        print('Requested Exposure time: ', self.get_exp_time())
        print('Is cooling: ', self.get_cooler())
        
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

# %%
