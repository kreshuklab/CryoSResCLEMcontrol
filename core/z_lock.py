from PyQt5.QtCore import QObject, QThread, pyqtSlot
import warnings
import numpy as np
from scipy.optimize import curve_fit
from scipy.optimize import OptimizeWarning

from core import FixedSizeNumpyQueue

def _GaussWOffset(x, a, x0, sigma, offset):
    return a * np.exp(-(x - x0)**2 / (2 * sigma**2)) + offset

class ZLock(QObject):
    
    def __init__(self,max_bead_spread=16,parent=None):
        super().__init__(parent)
        
        self._thread = QThread()
        self.moveToThread(self._thread)
        self._thread.start()
        
        self.busy = False
        self.should_process = False
        
        self.dev_manager   = None
        self.aux_cam       = None
        
        self.x_offset = int(0)
        self.y_offset = int(0)
        self.max_bead_spread = max_bead_spread
        
        self.ratio_queue = FixedSizeNumpyQueue(5)
        
    def set_busy(self,busy:bool):
        self.busy = busy
    
    def is_busy(self) -> bool:
        return self.busy
        
    def is_active(self) -> bool:
        return self._thread.isRunning()
        
    def set_aux_cam(self,cam_widget):
        self.aux_cam   = cam_widget.cam_handler
        self.aux_cam.frame_ready.connect( self.got_frame )

    
    def free(self):
        if self._thread.isRunning():
            self._thread.quit()
            self._thread.wait()
    
    def stop(self):
        self.should_process = False
    
    def start(self):
        self.x_offset = int(0)
        self.y_offset = int(0)
        self.ratio_queue.clear()
        
        self.should_process = True
        
    def _estimate_center_and_std(self,proj,axis):
        init_values = (proj.max()-proj.min(),np.argmax(proj),4,proj.min())
        with warnings.catch_warnings():
            warnings.simplefilter("error", OptimizeWarning)  # Treat warnings as errors
            try:
                popt,pcov = curve_fit(_GaussWOffset,axis,proj,init_values)
                if np.any(np.isnan(pcov)) or np.any(np.isinf(pcov)):
                    print("Curve fitting failed: covariance contains NaN or infinite values")
                    new_center = None
                    std = None
                else:
                    new_center = popt[1]
                    std = popt[2]
            except OptimizeWarning:
                print("Curve fitting failed: OptimizeWarning encountered")
                new_center = None
                std = None
            except Exception as e:
                print("Curve fitting failed: An error occurred:", e)
                new_center = None
                std = None

        return new_center, std
        
    @pyqtSlot()
    def got_frame(self):
        if self.should_process:
            frame = np.copy( self.aux_cam.frame_buffer )
            N = 4*self.max_bead_spread
            if (frame.shape[0]<N) or (frame.shape[1]<N):
                print(f'Invalid image size for focus lock: The image is {frame.shape[0]} by {frame.shape[1]}, and it must be larger than {N}.')
                return
        
            M = 2*self.max_bead_spread
            
            box_half    = frame.shape[0]//2
            # box_quarter = frame.shape[0]//4
            
            x0 = box_half + self.x_offset - M
            y0 = box_half + self.y_offset - M
            
            data = frame[ y0:y0+M, x0:x0+M ]
            tx = np.arange(x0,x0+M)
            ty = np.arange(y0,y0+M)
            
            self.x_center,x_std = self._estimate_center_and_std(data.mean(axis=0),tx)
            self.y_center,y_std = self._estimate_center_and_std(data.mean(axis=1),ty)
            
            if self.x_center is not None:
                self.x_center = int(self.x_center) - box_half
            else:
                self.x_center = int(0)
                
            if self.y_center is not None:
                self.y_center = int(self.y_center) - box_half
            else:
                self.y_center = int(0)    
            self.y_center = int(self.y_center) - box_half
            
            ratio = 0.0
            if (x_std is not None) and (y_std is not None):
                ratio = x_std/y_std
                self.ratio_queue.push(ratio)
                
                self.process_ratio(self.ratio_queue.median())
    
    def process_ratio(self,ratio):
        min_ratio_to_process = 0.2
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
        neg_fine_ratio   = 0.95 # ratio
        # NOTHING
        pos_fine_ratio   = 1.05 # ratio
        # FINE
        pos_coarse_ratio = 1.4  # ratio
        # COARSE
        
        delta_offset_step_min = 0.1 # Volts
        # delta_offset_step_max = 0.5 # Volts
            
# =============================================================================        

        if ratio > min_ratio_to_process:
            
            stage_dev = self.dev_manager.Stage
            
            if ratio < neg_coarse_ratio:
                print('Coarse correction -')
                stage_dev.positioning_coarse(stage_dev.axis_z,False,1)
                
            elif ratio < neg_fine_ratio:
                print('Fine correction -')
                step_size=delta_offset_step_min
                self.positioning_fine_delta(stage_dev.axis_z,-step_size)
                    
            elif ratio > pos_coarse_ratio:
                print('Coarse correction +')
                stage_dev.positioning_coarse(stage_dev.axis_z,True,1)
                
            elif ratio > pos_fine_ratio:
                print('Coarse correction +')
                step_size=delta_offset_step_min
                self.positioning_fine_delta(stage_dev.axis_z,step_size)
                
                
        
                        
            
            
            
            
                        
            
            
            
        
        
    



