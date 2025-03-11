import numpy as np
from numba import jit
from glob import glob

############################################################################### Svg add dark theme

def create_dark_iconoir():
    files = glob('resources/*.svg')
    for file in files:
        new_file = file.replace('.svg','_dark.svg')
        if not file.endswith('_dark.svg'):
            with open(file, 'r') as file:
                file_contents = file.read()
            updated_contents = file_contents.replace('stroke="#000000"', 'stroke="#B4B4B4"')
            with open(new_file, 'w') as file:
                file.write(updated_contents)

############################################################################### Numpy based fixed-sized queue

class FixedSizeNumpyQueue():
    
    def __init__(self,n_elements=5):
        self._numel = n_elements
        self.clear()
        
    def clear(self):
        self._buffer = np.zeros(self._numel)
        self._occupancy = 0
        self._new_index = 0
        
    def push(self,value):
        self._buffer[self._new_index] = value
        self._new_index = ( self._new_index + 1 ) % self._numel
        self._occupancy += 1

    def mean(self):
        if self._occupancy < self._numel:
            return 0
        else:
            return self._buffer.mean()
        
############################################################################### Numpy based fixed-sized queue

#@jit(nopython=True,nogil=True,cache=True)
@jit(nopython=True)
def get_min_max_avg(array):
    min_val =  np.inf
    max_val = -np.inf
    avg_val = 0
    
    for val in array.flat:
        min_val = min(min_val,val)
        max_val = max(max_val,val)
        avg_val = avg_val + val
    
    return min_val,max_val,avg_val/array.size