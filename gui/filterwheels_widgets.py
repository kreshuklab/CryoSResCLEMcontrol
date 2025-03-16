from PyQt5.QtWidgets import QGridLayout,QWidget,QSizePolicy
from PyQt5.QtWidgets import QPushButton, QLabel
from PyQt5.QtCore import pyqtSignal, pyqtSlot
from .ui_utils import colorbar_style_sheet

############################################################################### FilterWheelVertical

class FilterWheelWidget(QWidget):
    set_position = pyqtSignal(int)
    
    def __init__(self,filterwheel_device,title,pos_names,pos_colors,vertical=True,parent=None):
        super().__init__(parent)
        
        self.device     = filterwheel_device
        self.pos_names  = pos_names
        self.pos_colors = pos_colors
        self.position   = filterwheel_device.get_position()
        
        if vertical:
            self._create_vertical_layout(pos_names,pos_colors)
        else:
            self._create_horizontal_layout(pos_names,pos_colors)
        
        self.update_pos(self.position)
        self.set_position.connect( self.device.set_position )
        
    def _create_vertical_layout(self,names,colors):
        layout = QGridLayout()
        layout.setContentsMargins(0,0,0,0)
        self.buttons = []
        self.colorbars = []
        
        i = 0
        for name,color in zip(names,colors):
            button = QPushButton(name)
            button.setProperty('id',i)
            button.clicked.connect(lambda: self.update_pos(self.sender().property('id')))
            self.buttons.append(button)
            
            colorbar = QLabel()
            colorbar.setFixedWidth(5)
            colorbar.setStyleSheet(colorbar_style_sheet(color))
            self.colorbars.append(colorbar)
            
            layout.addWidget(colorbar,i,0)
            layout.addWidget(button  ,i,1)
            
            i += 1
        
        layout.setColumnStretch(0,0)
        layout.setColumnStretch(1,1)
        self.setLayout(layout)
        
    def _create_horizontal_layout(self,names,colors):
        layout = QGridLayout()
        layout.setContentsMargins(0,0,0,0)
        self.buttons = []
        self.colorbars = []
        
        i = 0
        for name,color in zip(names,colors):
            button = QPushButton(name)
            button.setProperty('id',i)
            button.clicked.connect(lambda: self.update_pos(self.sender().property('id')))
            button.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Expanding)
            self.buttons.append(button)
            
            colorbar = QLabel()
            colorbar.setFixedHeight(5)
            colorbar.setStyleSheet(colorbar_style_sheet(color))
            self.colorbars.append(colorbar)
            
            layout.addWidget(button  ,0,i)
            layout.addWidget(colorbar,1,i)
            
            i += 1
        
        layout.setRowStretch(0,1)
        layout.setRowStretch(1,0)
        self.setLayout(layout)
        
    @pyqtSlot(int)
    def update_pos(self,index:int):
        self.position = index
        for i,button in enumerate(self.buttons):
            font = self.font()
            font.setBold(i==self.position)
            button.setFont(font)
        for i,colorbar in enumerate(self.colorbars):
            colorbar.setEnabled(i==self.position)
        self.set_position.emit(self.position)

# ############################################################################### FilterWheelWidget

# class FilterWheelWidget(QWidget):
#     move_to = pyqtSignal(int)
    
#     def __init__(self,manager,names=('520/35','530/30','585/40','617/50','692/50','none'),vertical=True,*args,**kwargs):
#         super().__init__(*args,**kwargs)
        
#         self.manager = manager
        
#         if vertical:
#             self.layout = QVBoxLayout()
#         else:
#             self.layout = QHBoxLayout()
        
#         for i,label in enumerate(names):
#             button = QPushButton(label)
#             button.setProperty('id',i)
#             button.clicked.connect(lambda state: self.move_to.emit( self.sender().property('id') ))
#             self.layout.addWidget(button)
        
#         self.setLayout(self.layout)
#         self.move_to.connect( self.manager.set_position )
#         self.manager.filterwheel_done.connect( self.update_position )
        
#         self.update_position()
        
#     def update_position(self):
#         position = self.manager.current_position
        
#         for i in range(self.layout.count()):
#             item = self.layout.itemAt(i)
#             widget = item.widget()
#             font = widget.font()
#             font.setBold(i==position)
#             widget.setFont(font)







