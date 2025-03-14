from PyQt5.QtCore import Qt,QSize
from PyQt5.QtGui import QIcon, QFontMetrics,QIntValidator
from PyQt5.QtWidgets import QPushButton, QLineEdit, QComboBox
from glob import glob

############################################################################### Icon Provider

class IconProvider:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(IconProvider, cls).__new__(cls)
        return cls._instance
    
    def _load_files(self):
        files_dark = glob('resources/*_dark.svg')
        icon_list = []
        for file_dark in files_dark:
            file_light = file_dark.replace('_dark','')
            attr_name  = file_light[10:-4]
            attr_name  = attr_name.replace('-','_')
            icon_list.append( (attr_name,file_light,file_dark) )
        return icon_list
    
    def load_light_mode(self):
        icon_list = self._load_files()
        self.icon_dict = {}
        for icon_entry in icon_list:
            icon = QIcon(icon_entry[1])
            icon.addFile(icon_entry[2],mode=QIcon.Disabled)
            setattr(self, icon_entry[0],icon)
    
    def load_dark_mode(self):
        icon_list = self._load_files()
        self.icon_dict = {}
        for icon_entry in icon_list:
            icon = QIcon(icon_entry[2])
            icon.addFile(icon_entry[1],mode=QIcon.Disabled)
            setattr(self, icon_entry[0],icon)

# class _IconProviderMeta(type):
#     _instances = {}

#     def __call__(cls, *args, **kwargs):
#         if cls not in cls._instances:
#             cls._instances[cls] = super().__call__(*args, **kwargs)
#         return cls._instances[cls]


# class IconProvider(metaclass=_IconProviderMeta):
#     def __init__(self):
#         files = glob('resources/*.svg')
#         for file in files:
#             if not file.endswith('_dark.svg'):
#                 attribute_name =  file[10:-4]
#                 attribute_name = attribute_name.replace('-','_')
#                 setattr(self,attribute_name,file)
        
#     def set_dark_mode(self):
#         files = glob('resources/*_dark.svg')
#         for file in files:
#             attribute_name =  file[10:-9]
#             attribute_name = attribute_name.replace('-','_')
#             setattr(self,attribute_name,file)
    
#     def get_icon(self,icon_filename):
#         return QIcon(icon_filename)

############################################################################### Create Button with Icon

def create_iconized_button(icon:QIcon,text:str='',tooltip:str='',size:QSize=QSize(24,24)):
    button = QPushButton(text)
    button.setIcon(icon)
    button.setIconSize(size)
    if tooltip:
        button.setToolTip(tooltip)
    return button

############################################################################### Update Icon of Button

def update_iconized_button(button,icon:QIcon,text:str='',tooltip:str='',size:QSize=QSize(24,24)):
    button.setIcon(icon)
    button.setIconSize(size)
    if text:
        button.setText(text)
    if tooltip:
        button.setToolTip(tooltip)
    return button

############################################################################### Create QLineEdit for integers

def create_int_line_edit(val_min,val_max,placeholder_text=''):
    line_edit     = QLineEdit()
    font_metrics  = QFontMetrics(line_edit.font())
    int_validator = QIntValidator(val_min,val_max)
    num_digits    = max(len(str(val_min)),len(str(val_max)))
    min_width     = (1+num_digits)*font_metrics.horizontalAdvance('0')
    
    line_edit.setPlaceholderText(placeholder_text)
    line_edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
    line_edit.setValidator(int_validator)
    line_edit.setMinimumWidth(min_width)
    
    return line_edit

############################################################################### Create QComboBox from list

def create_combo_box(entries,current_entry):
    combo_box = QComboBox()
    for entry in entries:
        combo_box.addItem(str(entry),entry)
    current_index = entries.index(current_entry)
    combo_box.setCurrentIndex(current_index)
    return combo_box

