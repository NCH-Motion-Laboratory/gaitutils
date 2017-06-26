# -*- coding: utf-8 -*-
"""

play around w/ reading xlsx normaldata (Polygon exported)
code should end up in models.py

-2 adjacent cols specify normal lower/upper limits, e.g.:
HipAngles(2)  HipAngles(2)
24.7          39.4

-below code basically works, reads into lower/upper numpy arrays

TODO:


    
-more sanity checks to see if it's Polygon produced xlsx file

-change gcd code to produce lower/upper instead of avg/std

-need to refactor (where to specify normaldata in plotter)
    -plotter should have set_normaldata method






@author: hus20664877
"""

import openpyxl
import numpy as np
import logging

logger = logging.getLogger(__name__)


ndata = "C:/Users/hus20664877/Desktop/trondheim_normal_export.xlsx"

wb = openpyxl.load_workbook(ndata)

# get sheet
ws = wb.get_sheet_by_name('Normal')

# read a cell value
# print ws['A1'].value

        
rows = ws.rows  # generator

colnames_ = list(rows.next())  # cells of first row

colnames = [cell.value for cell in colnames_]  # cell values of 1st row

# cols = list(ws.columns)  # need to read all anyway

             
# produce numpy array w/ lower and upper limits
normaldata = dict()          
varname_prev, data_prev = None, None
for colname, col in zip(colnames, ws.columns):
    # check for supported variable name
    if (colname is None or
       not any([x in colname for x in ['(1)', '(2)', '(3)', 'Power']])):
        continue
    # strip dim if it exists
    varname = colname[:colname.find('(')].strip() if '(' in colname else colname
    data_ = [cell.value for cell in col]
    data = np.array(data_[3:])  # strip first rows with units, etc.
    if data.shape[0] != 51:
        raise ValueError('Normal data has unexpected shape')
    if varname == varname_prev:
        normaldata[varname] = np.stack([data, data_prev])
    else:
        varname_prev, data_prev = varname, data
    

    
    
    
    
        
    
    

           