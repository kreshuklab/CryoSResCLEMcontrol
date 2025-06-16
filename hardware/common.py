from PyQt5.QtCore import QObject, QThread

class Device(QObject):
    def __init__(self,dev_name:str,dev_type:str,dev_vendor:str,dev_model:str,parent=None):
        super().__init__(parent)
        
        self.name   = dev_name
        self.type   = dev_type
        self.vendor = dev_vendor
        self.model  = dev_model
        
        self._thread = QThread()
        self.moveToThread(self._thread)
        self._thread.start()
        
        self.set_busy(False)
        
    @property
    def full_name(self) -> str:
        return f'{self.name}:{self.type}:{self.vendor}:{self.model}'
        
    @property
    def thread_id(self) -> int:
        return int(QThread().currentThreadId())
    
    def set_busy(self,busy:bool):
        self.busy = busy
    
    def is_busy(self) -> bool:
        return self.busy
        
    def is_active(self) -> bool:
        return self._thread.isRunning()
        
    def free(self):
        if self._thread.isRunning():
            self._thread.quit()
            self._thread.wait()
        print(f'Device {self.full_name}: Bye.')
            
class DeviceManager:
    def __init__(self):
        self.dev_dict:dict[str,Device] = {}
    
    def add(self,dev:Device):
        if dev.name in self.dev_dict:
            print(f"Device {dev.name} already exists.")
            return
        
        self.dev_dict[dev.name] = dev
        setattr(self,dev.name,dev)
    
    def free(self):
        for dev in self.dev_dict.values():
            dev.free()
            
    def get_active_laser(self):
        index = 0
        for dev in self.dev_dict.values():
            if dev.type == 'Laser':
                if isinstance(dev.power_status, list):
                    for i in range(len(dev.power_status)):
                        if dev.power_status[i]:
                            return index+(i/10),dev.name+f'.{i}',dev.power_value[i],dev.power_value_unit
                else:
                    if dev.power_status:
                        return index,dev.name,dev.power_value,dev.power_value_unit
                index += 1
        return 'none',0,0,'none'


