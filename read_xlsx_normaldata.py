# -*- coding: utf-8 -*-
"""

play around w/ reading xlsx normaldata
code should end up in models.py

@author: hus20664877
"""

import openpyxl


ndata = "C:/Users/hus20664877/Desktop/trondheim_normal_export.xlsx"

wb = openpyxl.load_workbook(ndata)

# get sheet
ws = wb.get_sheet_by_name('Normal')

# read a cell value
print ws['A1'].value

rows = ws.rows

colnames_ = list(rows.next())  # cells, first row

colnames = [cell.value for cell in colnames_]                

print colnames

               
        
        
        
    
        