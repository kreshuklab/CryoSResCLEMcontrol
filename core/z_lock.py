from PyQt5.QtCore import QObject, QThread, pyqtSlot, pyqtSignal
import warnings
import numpy as np
from scipy.ndimage import gaussian_filter
from scipy.optimize import curve_fit
from scipy.optimize import OptimizeWarning
from enum import IntEnum

from core import FixedSizeNumpyQueue

def _GaussWLinear(x, a0, u0, s0, m0, o0):
    return a0 * np.exp(-(x - u0)**2 / (2 * s0**2)) + m0*x + o0

class ZLock(QObject):
    class ReportCode(IntEnum):
        MIN_FRAME_ERR = 1
        MAX_FRAME_ERR = 2
    
    class ReportType(IntEnum):
        TYPE_INFO  = 1
        TYPE_WARN  = 2
        TYPE_ERROR = 3
        
    error_reporting = pyqtSignal(int,int,str)
    
    def __init__(self,max_bead_spread=8,parent=None):
        super().__init__(parent)
        
        self._thread = QThread()
        self.moveToThread(self._thread)
        self._thread.start()
        
        self.busy = False
        self.should_process = False
        
        self.dev_manager   = None
        self.aux_cam       = None
        
        self.frame_size_min = 32
        self.frame_size_max = 80
        #self.max_bead_spread = max_bead_spread
        
        self.ratio_queue = FixedSizeNumpyQueue(5)
        
        self.voltage_z = 20
        self.voltage_reset_value = 65
        
        # Logic conf
        self.coarse_low = 0.6
        self.coarse_up  = 1.4
        
        self.fine_low    = 0.9
        self.fine_up     = 1.1
        self.should_fine = False
        
        # Kalman Conf
        self.ratio_cov    = 1.0
        self.ratio_noise  = 1.0
        self.signal_noise = 5e-4
        self.kalman_gain  = 0.1
        self.kalman_reset = 0.25
        self.kalman_ratio = 1.0
        
        
    def set_busy(self,busy:bool):
        self.busy = busy
    
    def is_busy(self) -> bool:
        return self.busy
        
    def is_active(self) -> bool:
        return self._thread.isRunning()
        
    def set_aux_cam(self,cam_widget):
        self.aux_cam = cam_widget.cam_handler
        self.aux_cam.frame_ready.connect( self.got_frame )
    
    def free(self):
        if self._thread.isRunning():
            self._thread.quit()
            self._thread.wait()
    
    def stop(self):
        self.should_process = False
    
    def start(self):
        self.ratio_queue.clear()
        self.should_process = True
    
    def _kalman_estimate(self,ratio):
        if ratio is None:
            ratio = self.kalman_ratio
        
        print(ratio,self.kalman_ratio)
        
        if np.abs( self.kalman_ratio - ratio ) > self.kalman_reset:
            print('Reset: ', np.abs( self.kalman_ratio - ratio ) )
            self.kalman_ratio = ratio
            self.ratio_cov    = 1.0
            
        cov_est = self.ratio_cov + self.signal_noise
        self.kalman_gain  = cov_est / (cov_est + self.ratio_noise)
        self.kalman_ratio = self.kalman_ratio + self.kalman_gain * (ratio - self.kalman_ratio)
        self.ratio_cov    = (1-self.kalman_gain) * cov_est
        
        return self.kalman_ratio
    
    def _estimate_std(self,proj):
        if np.abs(proj.min()) > proj.max():
            proj = -proj
        axis  = np.arange( proj.size )
        off   = proj.min()
        delta = proj.max() - off
        init_values = (0.95*delta,axis[np.argmax(proj)],0.75,0.05*delta,off)
        
        std = None
        
        popt,pcov,_,msg,ier = curve_fit(_GaussWLinear,axis,proj,init_values,full_output=True)
        
        if 'popt' not in locals() or 'pcov' not in locals():
            print("Curve fitting failed: An error occurred during fitting")
        else:
            if ier > 4:
                print("Curve fitting failed: " + msg)
            elif np.any(np.isnan(pcov)) or np.any(np.isinf(pcov)):
                print("Curve fitting failed: covariance contains NaN or infinite values")
            else:
                std = popt[2]
        
        return std

    @pyqtSlot()
    def got_frame(self):
        if self.should_process:
            frame = np.copy( self.aux_cam.frame_buffer )
            if (frame.shape[0]<self.frame_size_min) or (frame.shape[1]<self.frame_size_min):
                self.error_reporting.emit(ZLock.ReportType.TYPE_WARN,ZLock.ReportCode.MIN_FRAME_ERR,
                                          f'Image is {frame.shape[0]} by {frame.shape[1]}, should be at least {self.frame_size_min}')
                #print(f'Invalid image size for focus lock: The image is {frame.shape[0]} by {frame.shape[1]}, and it must be larger than {N}.')
                return
            
            if (frame.shape[0]>=self.frame_size_max) or (frame.shape[1]>=self.frame_size_max):
                self.error_reporting.emit(ZLock.ReportType.TYPE_WARN,ZLock.ReportCode.MAX_FRAME_ERR,
                                          f'Image is {frame.shape[0]} by {frame.shape[1]}, should be smaller than {self.frame_size_max}')
                #print(f'Invalid image size for focus lock: The image is {frame.shape[0]} by {frame.shape[1]}, and it must be larger than {N}.')
                return
            
            
            std_x = self._estimate_std( frame.mean(axis=1) )
            std_y = self._estimate_std( frame.mean(axis=0) )
            
            if std_x is None or std_y is None:
                ratio_raw = None
            else:
                ratio_raw = std_x / std_y
            ratio = self._kalman_estimate(ratio_raw)
            self.ratio_queue.push(ratio)
            print(ratio,ratio_raw)
            self.process_ratio(self.ratio_queue.median())
            
    
    def process_ratio(self,ratio):
#             
#             #COARSE
#             neg_coarse_ratio = 0.8  # ratio
#             # FINE
#             neg_fine_ratio   = 0.95 # ratio
#             # NOTHING
#             pos_fine_ratio   = 1.05 # ratio
#             # FINE
#             pos_coarse_ratio = 1.2  # ratio
#             # COARSE
#             delta_offset_step    = 0.5 # Volts
# =============================================================================
        # try finer/more accurate z-lock : 05.08.2024
        
        #COARSE
        neg_coarse_ratio = 0.6  # ratio
        # FINE
        neg_fine_ratio   = 0.9 # ratio
        # NOTHING
        pos_fine_ratio   = 1.1 # ratio
        # FINE
        pos_coarse_ratio = 1.4  # ratio
        # COARSE
        
        delta_offset_step_min = 0.2 # Volts
        # delta_offset_step_max = 0.5 # Volts
            
# =============================================================================        

        try:
            stage_dev = self.dev_manager.Stage
            
            move_up = True

            #if ratio < neg_coarse_ratio:
            if ratio < self.coarse_low:
                print('Coarse correction -')
                stage_dev.positioning_coarse(stage_dev.axis_z,move_up,1)
                self.kalman_ratio = 1.0
                
            elif self.should_fine and ratio < self.fine_low:
                if stage_dev.offset_tracker['z'] <= 10:
                    num_correcting_steps = int(np.floor((self.voltage_reset_value-10)/self.voltage_z))
                    stage_dev.positioning_coarse(stage_dev.axis_z,False,num_correcting_steps)
                    stage_dev.positioning_fine_absolute(stage_dev.axis_z,self.voltage_reset_value)
                else:
                    print('Fine correction -')
                    step_size=delta_offset_step_min
                    stage_dev.positioning_fine_delta(stage_dev.axis_z,step_size)
                self.kalman_ratio = 1.0
                        
            elif ratio > self.coarse_up:
                print('Coarse correction +')
                stage_dev.positioning_coarse(stage_dev.axis_z,not move_up,1)
                self.kalman_ratio = 1.0
                
            elif self.should_fine and ratio > self.fine_up:
                if stage_dev.offset_tracker['z'] >= (150-self.voltage_z-10):
                    num_correcting_steps = int(np.floor((self.voltage_reset_value-10)/self.voltage_z))
                    stage_dev.positioning_coarse(stage_dev.axis_z,True,num_correcting_steps)
                    stage_dev.positioning_fine_absolute(stage_dev.axis_z,self.voltage_reset_value)
                else:
                    print('Fine correction +')
                    step_size=delta_offset_step_min
                    stage_dev.positioning_fine_delta(stage_dev.axis_z,-step_size)
                self.kalman_ratio = 1.0
            
        except Exception as e: print(e)
                
                
        
                        
            
            
            
            
                        
            
            
            
        
        
    



