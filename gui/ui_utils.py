# from PyQt5.QtGui import QIcon
from glob import glob


class _IconProviderMeta(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super().__call__(*args, **kwargs)
        return cls._instances[cls]


class IconProvider(metaclass=_IconProviderMeta):
    def __init__(self):
        files = glob('resources/*.svg')
        for file in files:
            if not file.endswith('_dark.svg'):
                attribute_name =  file[10:-4]
                attribute_name = attribute_name.replace('-','_')
                setattr(self,attribute_name,file)
        
    def set_dark_mode(self):
        files = glob('resources/*_dark.svg')
        for file in files:
            attribute_name =  file[10:-9]
            attribute_name = attribute_name.replace('-','_')
            setattr(self,attribute_name,file)
