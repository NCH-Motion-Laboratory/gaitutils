# -*- coding: utf-8 -*-
"""
Normal data readers

@author: Jussi (jnu@iki.fi)
"""


from builtins import next
from builtins import zip
import numpy as np
import openpyxl
import os.path as op
import logging

from . import cfg, sessionutils, GaitDataError, numutils
from .numutils import isfloat
from ulstools.num import age_from_hetu
from .models import models_all
from .envutils import lru_cache


logger = logging.getLogger(__name__)


def read_all_normaldata(age=None):
    """ Read all normal data defined in config. If age is specified, include
    age specific normaldata. """
    model_normaldata = dict()
    # we generously accept both list and string
    if isinstance(cfg.general.normaldata_files, list):
        normaldata_files = cfg.general.normaldata_files
    else:
        normaldata_files = [cfg.general.normaldata_files]
    for fn in normaldata_files:
        ndata = read_normaldata(fn)
        model_normaldata.update(ndata)
    if age is not None:
        age_ndata_file = normaldata_age(age)
        if age_ndata_file:
            age_ndata = read_normaldata(age_ndata_file)
            model_normaldata.update(age_ndata)
    return model_normaldata


def read_session_normaldata(session):
    """Reads normal data according to patient info in current session"""
    info = sessionutils.load_info(session)
    if info is not None and 'hetu' in info:
        age = age_from_hetu(info['hetu'])
    else:
        age = None
    return read_all_normaldata(age)


@lru_cache(maxsize=10)
def read_normaldata(filename):
    """ Read normal data into dict. Dict keys are variables and values
    are Numpy arrays of shape (n, 2). n is either 1 (scalar variable)
    or 51 (data on 0..100% gait cycle, defined every 2% of cycle).
    The first and second columns are min and max values, respectively.
    (May be e.g. mean-stddev and mean+stddev)
    """
    logger.debug('reading normal data from %s' % filename)
    if not op.isfile(filename):
        raise GaitDataError('No such file %s' % filename)
    type_ = op.splitext(filename)[1].lower()
    if type_ == '.gcd':
        return _read_gcd(filename)
    elif type_ == '.xlsx':
        return _read_xlsx(filename)
    else:
        raise GaitDataError('Only .gcd or .xlsx file formats are supported')


def normaldata_age(age):
    """ Return age specific normal data file """
    for age_range, filename in cfg.general.normaldata_age.items():
        if age_range[0] <= age <= age_range[1]:
            logger.debug('found normal data file %s for age %d' % (filename, age))
            return filename


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
         mean-dev, mean+dev
        -gcd variable names are different and will be translated according
        to each models translation table """
    ndata = dict()
    with open(filename, 'r') as f:
        lines = f.readlines()
    varname = None
    for li in lines:
        lis = li.split()
        if li[0] == '!':  # new variable
            varname = lis[0][1:]
            ndata[varname] = list()
        elif varname and isfloat(lis[0]):  # actual data
            # assume mean, dev format
            mean, dev = np.array(lis, dtype=float)
            ndata[varname].append([mean - dev, mean + dev])
        else:  # comment etc.
            continue
    # translate variable names
    ndata_ = dict()
    for nvarname, nval in ndata.items():
        for model in models_all:
            if nvarname in model.gcd_normaldata_map:
                logger.debug(
                    'mapping normal data variable %s -> %s'
                    % (nvarname, model.gcd_normaldata_map[nvarname])
                )
                nvarname = model.gcd_normaldata_map[nvarname]
                break
        ndata_[nvarname] = nval
    normaldata = {key: np.array(val) for key, val in ndata_.items()}
    return _check_normaldata(normaldata)


def _read_xlsx(filename):
    """ Read normal data exported from Polygon (xlsx format). """
    wb = openpyxl.load_workbook(filename)
    ws = wb['Normal']
    colnames = (cell.value for cell in next(ws.rows))  # first row: col names
    normaldata = dict()
    # read the columns and produce dict of numpy arrays
    for colname, col in zip(colnames, ws.columns):
        if colname is None:
            continue
        # pick values from row 4 onwards (skips units etc.)
        data = np.fromiter((c.value for k, c in enumerate(col) if k >= 3), float)
        data = data[~np.isnan(data)]  # drop empty rows
        # rewrite the coordinate
        colname = colname.replace(' (1)', 'X')
        colname = colname.replace(' (2)', 'Y')
        colname = colname.replace(' (3)', 'Z')
        # scalar power variables (ones ending in 'Power')
        # are written as Z component (Nexus convention)
        if colname[-5:] == 'Power':
            colname += 'Z'
        normaldata[colname] = (
            np.stack([normaldata[colname], data], axis=1)
            if colname in normaldata
            else data
        )
    return _check_normaldata(normaldata)


def _write_xlsx(normaldata, filename):
    """Save normal data dict into Polygon xlsx format"""
    repl_di = {'X': ' (1)', 'Y': ' (2)', 'Z': ' (3)'}
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'Normal'
    for n, var in enumerate(sorted(normaldata), 1):
        logger.debug('writing %s' % var)
        data = normaldata[var]
        nrows, ncols = data.shape
        if nrows not in (51, 1) or ncols != 2:
            raise ValueError(
                'normaldata has unexpected dimensions: %d x %d' % (nrows, ncols)
            )
        # convert trailing dimension to number
        if var[-1] in 'XYZ':
            if 'Power' in var:
                var_ = var[:-1]
            else:
                var_ = var[:-1] + repl_di[var[-1]]
        else:
            var_ = var
        firstcol, secondcol = 2 * n - 1, 2 * n
        # write (data min, data max) columns for each variable
        for col, coldata in zip([firstcol, secondcol], [data[:, 0], data[:, 1]]):
            ws.cell(column=col, row=1, value=var_)  # column header
            ws.cell(column=col, row=2, value=0)  # not clear what this is
            ws.cell(
                column=col, row=3, value='unknown'
            )  # supposed to be unit, not used by us
            for k, val in enumerate(coldata):
                ws.cell(column=col, row=4 + k, value=val)
    logger.debug('saving %s' % filename)
    wb.save(filename=filename)


def normals_from_data(data):
    """Compute normaldata from data dict output by get_model_data"""
    normaldata = dict()
    for mod in models_all:
        thevars = mod.varlabels_noside
        for var in thevars:
            rvar, lvar = 'R' + var, 'L' + var
            rcurves, lcurves = data[rvar], data[lvar]
            if rcurves is None or lcurves is None:
                logger.warning('cannot get model data for %s' % var)
                continue
            # combine data for L/R
            curves = np.concatenate([rcurves, lcurves])
            # mean and median should coincide for normal distribution but
            # median is less sensitive to outliers, so use it
            curve_med = np.median(curves, axis=0)
            curve_std = numutils.mad(curves, axis=0)
            # traditionally normaldata uses 2% cycle intervals, so downsample
            curve_med_ds = curve_med[::2]
            curve_std_ds = curve_std[::2]
            lower_vardata = curve_med_ds - curve_std_ds
            upper_vardata = curve_med_ds + curve_std_ds
            normaldata[var] = np.stack([lower_vardata, upper_vardata], axis=1)
    return normaldata
