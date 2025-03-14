from PyQt5.QtCore import Qt,QSize
from PyQt5.QtGui import QIcon, QFontMetrics,QIntValidator,QValidator
from PyQt5.QtWidgets import QPushButton, QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox
from glob import glob
import numpy as np

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

############################################################################### SteppingSpinBox

class SteppingSpinBox(QSpinBox):
    def __init__(self,step,current_value=0,min_val=0,max_value=2147483647,parent=None):
        super().__init__(parent)
        self.base = step
        self.setSingleStep(step)
        self.setMinimum(min_val)
        self.setMaximum(max_value)
        self.setValue(current_value)

    def validate(self, in_str, pos):
        if not in_str:
            return QValidator.Intermediate, in_str, pos
        
        try:
            val = int(in_str)
            if (val % self.base) == 0:
                return QValidator.Acceptable, in_str, pos
            else:
                return QValidator.Intermediate, in_str, pos
        except ValueError:
            return QValidator.Invalid, in_str, pos
    
    def fixup(self, in_str):
        try:
            val = int(in_str)
            val = int(self.base*np.round(float(val)/self.base))
            return str(val)
        except ValueError:
            return ""
            return ""

    def stepBy(self, steps):
        value = self.value()
        new_value = value + steps * self.base  # Ensure stepping in multiples of 4
        self.setValue(new_value)

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

def create_int_line_edit(val_min,val_max,placeholder_text='',validator=None):
    line_edit     = QLineEdit()
    font_metrics  = QFontMetrics(line_edit.font())
    int_validator = QIntValidator(val_min,val_max)
    num_digits    = max(len(str(val_min)),len(str(val_max)))
    min_width     = (1+num_digits)*font_metrics.horizontalAdvance('0')
    
    line_edit.setPlaceholderText(placeholder_text)
    line_edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
    line_edit.setValidator(int_validator)
    line_edit.setMinimumWidth(min_width)
    
    if validator:
        line_edit.setValidator(validator)
    
    return line_edit

############################################################################### Create QComboBox from list

def create_combo_box(entries,current_entry):
    combo_box = QComboBox()
    for entry in entries:
        combo_box.addItem(str(entry),entry)
    current_index = entries.index(current_entry)
    combo_box.setCurrentIndex(current_index)
    return combo_box

############################################################################### Create QSpinBox

def create_spinbox(min_val,max_val,cur_val,step=1):
    spin_box = QSpinBox()
    spin_box.setFocusPolicy(Qt.ClickFocus)
    spin_box.setMinimum(min_val)
    spin_box.setMaximum(max_val)
    spin_box.setValue(cur_val)
    spin_box.setSingleStep(step)
    return spin_box

def create_doublespinbox(min_val,max_val,cur_val,step=1,decimals=2):
    spin_box = QDoubleSpinBox()
    spin_box.setFocusPolicy(Qt.ClickFocus)
    spin_box.setMinimum(min_val)
    spin_box.setMaximum(max_val)
    spin_box.setValue(cur_val)
    spin_box.setSingleStep(step)
    spin_box.setDecimals(decimals)
    return spin_box

############################################################################### Int Validator multiple of

class IntMultipleOfValidator(QValidator):
    
    def __init__(self,base=1):
        super().__init__()
        self.base = base
    
    def validate(self, in_str, pos):
        if not in_str:
            return QValidator.Intermediate, in_str, pos
        
        try:
            val = int(in_str)
            if (val % self.base) == 0:
                return QValidator.Acceptable, in_str, pos
            else:
                return QValidator.Intermediate, in_str, pos
        except ValueError:
            return QValidator.Invalid, in_str, pos

    def fixup(self, in_str):
        try:
            val = int(in_str)
            val = int(self.base*np.round(float(val)/self.base))
            return str(val)
        except ValueError:
            return ""