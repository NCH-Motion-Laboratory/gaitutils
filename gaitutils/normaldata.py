# -*- coding: utf-8 -*-
"""
Normal data readers

@author: jnu@iki.fi
"""


import numpy as np
import openpyxl
import os.path as op

from .numutils import isfloat


def read_normaldata(filename):
    """ Read normal data into dict. Dict keys are variables and values
    are Numpy arrays of shape (n, 2). n is either 1 (scalar variable)
    or 51 (data on 0..100% gait cycle, defined every 2% of cycle).
    The first and second columns are min and max values, respectively.
    (May be e.g. mean-stddev and mean+stddev)
    """
    if not op.isfile(filename):
        raise ValueError('No such file %s' % filename)
    type = op.splitext(filename)[1].lower()
    if type == '.gcd':
        return _read_gcd(filename)
    elif type == '.xlsx':
        return _read_xlsx(filename)
    else:
        raise ValueError('Only .gcd or .xlsx file formats are supported')


def _check_normaldata(ndata):
    """ Sanity checks """
    for val in ndata.values():
        if not all(np.diff(val) >= 0):
            raise ValueError('Normal data not in min/max format')
        if val.shape[0] not in [1, 51]:  # must be gait cycle data or scalar
            raise ValueError('Normal data has unexpected dimensions')
    return ndata


def _read_gcd(filename):
    """ Read normal data from a gcd file.
        -gcd data is assumed to be in (mean, dev) 2-column format and is
         converted to (min, max) (Polygon normal data format) as
         mean-dev, mean+dev """
    normaldata = dict()
    with open(filename, 'r') as f:
        lines = f.readlines()
    varname = None
    for li in lines:
        lis = li.split()
        if li[0] == '!':  # new variable
            varname = lis[0][1:]
            normaldata[varname] = list()
        elif varname and isfloat(lis[0]):  # actual data
            # assume mean, dev format
            mean, dev = np.array(lis, dtype=float)
            normaldata[varname].append([mean-dev, mean+dev])
        else:  # comment etc.
            continue
    normaldata = {key: np.array(val) for key, val in normaldata.items()}
    return _check_normaldata(normaldata)


def _read_xlsx(filename):
    """ Read normal data exported from Polygon (xlsx format). """
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
        # rewrite the coordinate
        colname = colname.replace(' (1)', 'X')
        colname = colname.replace(' (2)', 'Y')
        colname = colname.replace(' (3)', 'Z')
        normaldata[colname] = (np.stack([normaldata[colname], data], axis=1)
                               if colname in normaldata else data)
    return _check_normaldata(normaldata)
