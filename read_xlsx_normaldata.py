# -*- coding: utf-8 -*-
"""

play around w/ reading xlsx normaldata (Polygon exported)
code should end up in models.py

-2 adjacent cols specify normal lower/upper limits, e.g.:
HipAngles(2)  HipAngles(2)
24.7          39.4

-below code basically works, reads into lower/upper numpy arrays
-change gcd code to produce lower/upper instead of avg/std
-need to refactor (where to specify normaldata in plotter)





@author: hus20664877
"""

import openpyxl
import numpy as np


ndata = "C:/Users/hus20664877/Desktop/trondheim_normal_export.xlsx"

wb = openpyxl.load_workbook(ndata)

# get sheet
ws = wb.get_sheet_by_name('Normal')

# read a cell value
print ws['A1'].value

        
rows = ws.rows  # generator

colnames_ = list(rows.next())  # cells of first row

colnames = [cell.value for cell in colnames_]  # cell values of 1st row

# cols = list(ws.columns)  # need to read all anyway

             
# produce numpy array w/ lower and upper limits
normaldata = dict()          
varname_prev, data_prev = None, None
for name, col in zip(colnames, ws.columns):
    if not name:
        continue
    if not ('(1)' in name or ('2') in name):  # variable not understood
        continue
    varname = name[:name.find('(')].strip()
    data_ = [cell.value for cell in col]
    data = np.array(data_[3:])  # strip units etc.
    if varname == varname_prev:
        normaldata[varname] = np.stack([data, data_prev])
    else:
        varname_prev, data_prev = varname, data
    

    
    
    
    
        
    
    

           
           
print colnames


               
        
        
        
    
        