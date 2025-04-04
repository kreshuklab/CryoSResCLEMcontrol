from PyQt5.QtCore import QObject, QThread, pyqtSlot
import warnings
import numpy as np
from scipy.ndimage import gaussian_filter
from scipy.optimize import curve_fit
from scipy.optimize import OptimizeWarning
from scipy.sparse.linalg import svds

from core import FixedSizeNumpyQueue

def _GaussWLinear(x, a0, u0, s0, m0, o0):
    return a0 * np.exp(-(x - u0)**2 / (2 * s0**2)) + m0*x + o0

class ZLock(QObject):
    
    def __init__(self,max_bead_spread=10,parent=None):
        super().__init__(parent)
        
        self._thread = QThread()
        self.moveToThread(self._thread)
        self._thread.start()
        
        self.busy = False
        self.should_process = False
        
        self.dev_manager   = None
        self.aux_cam       = None
        
        self.ref_v = None
        self.ref_h = None
        
        self.x_offset = int(0)
        self.y_offset = int(0)
        self.max_bead_spread = max_bead_spread
        
        self.ratio_queue = FixedSizeNumpyQueue(5)
        
        self.voltage_z = 20
        
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
    
    def _create_ref(self,shape,kernel):
        tmp = np.zeros( shape, np.float32 )
        tmp[ tmp.shape[0]//2, tmp.shape[1]//2 ] = 1
        tmp = gaussian_filter(tmp,kernel)
        TMP = np.fft.fft2( tmp, norm='ortho' )
        return tmp,TMP

    def _compute_references(self,frame):
        if (self.ref_h is None) or ( self.ref_h.shape != frame.shape ):
            self.ref_h,self.REF_H = self._create_ref(frame.shape,(0.75,2.5))
        
        if (self.ref_v is None) or ( self.ref_v.shape != frame.shape ):
            self.ref_V,self.REF_V = self._create_ref(frame.shape,(2.5,0.75))
            
    def _compute_ratio(self,frame):
        FRAME = np.fft.fft2( frame, norm='ortho' )
        cc_h = np.fft.ifftshift( np.fft.ifft2(FRAME*self.REF_H,norm='ortho') ).real
        cc_v = np.fft.ifftshift( np.fft.ifft2(FRAME*self.REF_V,norm='ortho') ).real
        return cc_v.max()/cc_h.max()
        
    def _estimate_center_and_std(self,proj,axis):
        if np.abs(proj.min()) > proj.max():
            proj = -proj
        off   = proj.min()
        delta = proj.max() - off
        init_values = (0.95*delta,axis[np.argmax(proj)],0.75,0.05*delta,off)
        
        with warnings.catch_warnings():
            warnings.simplefilter("error", OptimizeWarning)  # Treat warnings as errors
            try:
                popt,pcov = curve_fit(_GaussWLinear,axis,proj,init_values)
                if np.any(np.isnan(pcov)) or np.any(np.isinf(pcov)):
                    print("Curve fitting failed: covariance contains NaN or infinite values")
                    new_center = None
                    std = None
                else:
                    std = popt[2]
                    new_center = popt[1]
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
            
            self._compute_references(frame)
            ratio = self._compute_ratio(frame)
            self.ratio_queue.push(ratio)
            # self.process_ratio(self.ratio_queue.median())
            
            print(self.ratio_queue.median(),ratio)
    
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

        try:
            
            move_up = True

            if ratio < neg_coarse_ratio:
                
                stage_dev = self.dev_manager.Stage
                
                if ratio < 0:
                    print('Coarse correction -')
                    stage_dev.positioning_coarse(stage_dev.axis_z,move_up,1)
                    
                # elif ratio < neg_fine_ratio:
                #     if stage_dev.offset_tracker['z'] <= 10:
                #         num_correcting_steps = int(np.floor((75-10)/self.voltage_z))
                #         stage_dev.positioning_coarse(stage_dev.axis_z,False,num_correcting_steps)
                #         stage_dev.positioning_fine_absolute(stage_dev.axis_z,75)
                #     else:
                #         print('Fine correction -')
                #         step_size=delta_offset_step_min
                #         stage_dev.positioning_fine_delta(stage_dev.axis_z,-step_size)
                        
                elif ratio > pos_coarse_ratio:
                    print('Coarse correction +')
                    stage_dev.positioning_coarse(stage_dev.axis_z,not move_up,1)
                    
                # elif ratio > pos_fine_ratio:
                #     if stage_dev.offset_tracker['z'] <= (150-self.voltage_z-10):
                #         num_correcting_steps = int(np.floor((75-10)/self.voltage_z))
                #         stage_dev.positioning_coarse(stage_dev.axis_z,True,num_correcting_steps)
                #         stage_dev.positioning_fine_absolute(stage_dev.axis_z,75)
                #     else:
                #         print('Fine correction -')
                #         step_size=delta_offset_step_min
                #         stage_dev.positioning_fine_delta(stage_dev.axis_z,-step_size)
            
        except Exception as e: print(e)
                
                
        
                        
            
            
            
            
                        
            
            
            
        
        
    



