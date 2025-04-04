from PyQt5.QtCore import QObject, QThread, pyqtSlot, pyqtSignal
from time import sleep

class Worker(QObject):
    done = pyqtSignal()
    
    def __init__(self,parent=None):
        super().__init__(parent)
        
        self._thread = QThread()
        self.moveToThread(self._thread)
        self._thread.start()
        
        self.busy = False
        self.should_process = False
        
        self.dev_manager   = None
        self.main_cam      = None
        self.aux_cam       = None
        self.main_saver    = None
        self.aux_saver     = None
        
    def set_busy(self,busy:bool):
        self.busy = busy
    
    def is_busy(self) -> bool:
        return self.busy
        
    def is_active(self) -> bool:
        return self._thread.isRunning()
        
    def set_main_cam(self,cam_widget):
        self.main_cam   = cam_widget.cam_handler
        self.main_saver = cam_widget.img2tiff
        
    def set_aux_cam(self,cam_widget):
        self.aux_cam   = cam_widget.cam_handler
        self.aux_saver = cam_widget.img2tiff
    
    def free(self):
        if self._thread.isRunning():
            self._thread.quit()
            self._thread.wait()
    
    @pyqtSlot()
    def stop_process(self):
        self.should_process = False
    
    @pyqtSlot(int,int,str,str,float)
    def start_coarse_z_sweep(self,n_steps,step_volt,save_main,save_aux,post_z_wait):
        self.should_process = True
        sleep(0.5)
    
        stage_dev = self.dev_manager.Stage
        direction = step_volt > 0
        voltage   = abs(step_volt)
        
        stage_dev.set_voltage(stage_dev.axis_z,voltage)
        
        if save_main:
            self.main_saver.enable_autosave()
            self.main_saver.start_acquisition(save_main,n_steps + 1)
            self.main_cam.snap_frame()
            
        if save_aux:
            self.aux_saver.enable_autosave()
            self.aux_saver.start_acquisition(save_aux,n_steps + 1)
            self.aux_cam.snap_frame()
            
        for _ in range(n_steps):
            stage_dev.positioning_coarse(stage_dev.axis_z,direction,1)
            sleep(post_z_wait)
            
            if save_main:
                self.main_cam.snap_frame()
            
            if save_aux:
                self.aux_cam.snap_frame()
            
            if not self.should_process:
                break
            
        self.should_process = False
        
        sleep(0.5)
        
        if save_main:
            self.main_saver.dataset_finish()
            
        if save_aux:
            self.aux_saver.dataset_finish()
        
        self.done.emit()
    
    @pyqtSlot(int,float,str,str,float)
    def start_fine_z_sweep(self,n_steps,delta_v,save_main,save_aux,post_z_wait):
        self.should_process = True
        sleep(0.5)
    
        stage_dev = self.dev_manager.Stage
        
        if save_main:
            self.main_saver.start_acquisition(save_main,n_steps + 1)
            self.main_cam.snap_frame()
            
        if save_aux:
            self.aux_saver.start_acquisition(save_aux,n_steps + 1)
            self.aux_cam.snap_frame()
            
        for ite in range(n_steps):
            stage_dev.positioning_fine_delta(stage_dev.axis_z,delta_v)
            sleep(post_z_wait)
            
            if save_main:
                self.main_cam.snap_frame()
                self.main_saver.dataset_push_frame()
            
            if save_aux:
                self.aux_cam.snap_frame()
                self.aux_saver.dataset_push_frame()
            
            if not self.should_process:
                break
            
        self.should_process = False
        
        sleep(0.5)
        
        if save_main:
            self.main_saver.dataset_finish()
            self.main_saver.enable_autosave()
            
        if save_aux:
            self.aux_saver.dataset_finish()
            self.aux_saver.enable_autosave()
            
        self.done.emit()
    
    #@pyqtSlot()


