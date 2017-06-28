# -*- coding: utf-8 -*-
"""
Created on Fri Nov 11 10:49:55 2016

@author: hus20664877
"""

from numutils import isfloat
import numpy as np
import openpyxl


def _check_normaldata(ndata):
    """ Sanity checks """
    for val in ndata.values():
        if not all(np.diff(val) >= 0):
            raise ValueError('Normal data not in min/max format')
        if val.shape[0] not in [1, 51]:  # must be gait cycle data or scalar
            raise ValueError('Normal data has unexpected dimensions')


def read_gcd(filename):
    """ Read normal data from a gcd file.
    Returns a dict of numpy arrays keyed by variable names. Arrays have shape
    (d, 2) where d is the dim of normal data (1 or 51). The first and second
    columns are the lower and upper bounds, respectively.
    Notes:
        -usual gcd normal data variable names do not seem to match PiG variable
         names; a translation dict is provided in models.py
        -gcd data is assumed to be in (mean, dev) 2-column format and is
         converted to (min, max) (Polygon normal data format) as
         mean-dev, mean+dev
    """
    normaldata = dict()
    with open(filename, 'r') as f:
        lines = f.readlines()
    varname = None
    for li in lines:
        lis = li.split()
        print lis
        if li[0] == '!':  # new variable
            varname = lis[0][1:]
            normaldata[varname] = list()
        elif varname and isfloat(lis[0]):  # actual data
            # assume mean, dev format
            mean, dev = np.array(lis, dtype=float)
            normaldata[varname].append([mean-dev, mean+dev])
        else:  # comment etc.
            continue
    _check_normaldata(normaldata)
    return {key: np.array(val) for key, val in normaldata.items()}


def read_xlsx(filename):
    """ Read normal data exported from Polygon (xlsx format).
    Returns a dict of numpy arrays keyed by variable names. Arrays have shape
    (d, 2) where d is the dim of normal data (1 or 51). The first and second
    columns are the lower and upper bounds, respectively.
    """
    wb = openpyxl.load_workbook(filename)
    ws = wb.get_sheet_by_name('Normal')
    colnames = (cell.value for cell in ws.rows.next())  # first row: col names
    normaldata = dict()
    # read the columns and produce dict of numpy arrays
    for colname, col in zip(colnames, ws.columns):
        if colname is None:
            continue
        # pick values from row 4 onwards (skips units etc.)
        data = np.fromiter((c.value for k, c in enumerate(col) if k >= 3),
                           float)
        data = data[~np.isnan(data)]  # drop empty rows
        normaldata[colname] = (np.stack([normaldata[colname], data], axis=1)
                               if colname in normaldata else data)
    _check_normaldata(normaldata)
    return normaldata
