# -*- coding: utf-8 -*-
"""

c3d reader functions


@author: Jussi (jnu@iki.fi)
"""

from __future__ import print_function, division
from builtins import zip
from collections import defaultdict
import logging
import numpy as np
import os
import sys

from .numutils import center_of_pressure, change_coords
from . import GaitDataError


logger = logging.getLogger(__name__)

# import btk either from btk or pyBTK
try:
    import btk
    BTK_IMPORTED = True
except ImportError:
    try:
        if sys.version_info.major == 3:
            import pyBTK.btk3 as btk
        elif sys.version_info.major == 2:
            import pyBTK.btk2 as btk
        else:
            raise Exception('unexpected major Python version')
        BTK_IMPORTED = True
    except ImportError:
        BTK_IMPORTED = False
        logger.warning('cannot find btk module; unable to read .c3d files')


def is_c3dfile(obj):
    """ Check whether obj is a valid c3d file. Currently just checks
    existence. """
    try:
        return os.path.isfile(obj)
    except TypeError:
        return False


def _get_c3d_metadata_subfields(acq, field):
    """ Return names of metadata subfields for a given field"""
    meta = acq.GetMetaData()
    meta_s = meta.GetChild(field)
    return [f.GetLabel() for f in btk.Iterate(meta_s)]


def _get_c3d_metadata_field(acq, field, subfield):
    """Get c3d metadata FIELD:SUBFIELD as Python type.
    Always returns a list - pick [0] if scalar """
    meta = acq.GetMetaData()

    def _get_child(field, child):
        try:
            return field.GetChild(child)
        except RuntimeError:
            raise ValueError('Invalid c3d metadata field: %s' % child)

    info = _get_child(_get_child(meta, field), subfield).GetInfo()
    if info.GetFormatAsString() == 'Char':
        return [s.strip() for s in info.ToString()]
    elif info.GetFormatAsString() == 'Real':
        return [x for x in info.ToDouble()]
    else:
        raise ValueError('Unhandled btk meta info type')


def _get_c3dacq(c3dfile):
    """Get a btk.btkAcquisition object"""
    reader = btk.btkAcquisitionFileReader()
    # btk interface cannot take unicode, so encode to latin-1 first
    c3dfile = c3dfile.encode('latin-1')
    reader.SetFilename(c3dfile)
    reader.Update()
    return reader.GetOutput()


def get_analysis(c3dfile, condition='unknown'):
    """Get analysis values from c3d (e.g. gait parameters). Returns a dict
    keyed by var and context. First key can optionally be a condition label."""
    logger.debug('getting analysis values from %s' % c3dfile)
    acq = _get_c3dacq(c3dfile)
    try:
        vars_ = _get_c3d_metadata_field(acq, 'ANALYSIS', 'NAMES')
        units = _get_c3d_metadata_field(acq, 'ANALYSIS', 'UNITS')
        contexts = _get_c3d_metadata_field(acq, 'ANALYSIS', 'CONTEXTS')
        vals = _get_c3d_metadata_field(acq, 'ANALYSIS', 'VALUES')
    except ValueError:
        raise GaitDataError('Cannot read time-distance parameters from %s'
                            % c3dfile)

    # build a nice output dict
    di = dict()
    di[condition] = dict()
    di_ = di[condition]

    for (var, unit, context, val) in zip(vars_, units, contexts, vals):
        if var not in di_:
            di_[var] = dict()
            di_[var]['unit'] = unit
        if context not in di_[var]:
            di_[var][context] = val

    for var in di_:
        for context in ['Left', 'Right']:
            if context not in di_[var]:
                logger.warning('%s has missing value: %s / %s' %
                               (c3dfile, var, context))
                di_[var][context] = np.NaN

    return di


def get_emg_data(c3dfile):
    """ Read EMG data from a c3d file. """
    return _get_analog_data(c3dfile, 'EMG')


def get_accelerometer_data(c3dfile):
    """ Read accelerometer data from a c3d file. """
    data = _get_analog_data(c3dfile, 'Accelerometer')
    # Remove the 'Acceleration.' prefix if inserted by Nexus, so that channel
    # names match Nexus. This is a bit ugly (not done for EMG which uses fuzzy
    # matching)
    for key in data['data']:
        if key.find('Acceleration.') == 0:
            # replace key names
            data['data'][key[13:]] = data['data'].pop(key)
    return data


def _get_analog_data(c3dfile, devname):
    """ Read analog data from a c3d file. devname is matched against channel
    names. """
    acq = _get_c3dacq(c3dfile)
    data = dict()
    chnames = []
    for i in btk.Iterate(acq.GetAnalogs()):
        if i.GetDescription().find(devname) >= 0:
            chname = i.GetLabel()
            chnames.append(chname)
            data[chname] = np.squeeze(i.GetValues())
    if chnames:
        return {'t': np.arange(len(data[chname])) / acq.GetAnalogFrequency(),
                'data': data}
    else:
        raise GaitDataError('No matching analog channels found in data')


def _get_marker_data(c3dfile, markers, ignore_edge_gaps=True,
                     ignore_missing=False):
    """Get position, velocity and acceleration for specified markers."""
    if not isinstance(markers, list):  # listify if not already a list
        markers = [markers]
    acq = _get_c3dacq(c3dfile)
    mkrdata = dict()
    for marker in markers:
        try:
            mP = np.squeeze(acq.GetPoint(marker).GetValues())
        except RuntimeError:
            if ignore_missing:
                logger.warning('Cannot read trajectory %s from c3d file'
                               % marker)
                continue
            else:
                raise GaitDataError('Cannot read trajectory %s from c3d file'
                                    % marker)
        mkrdata[marker] = mP
        mkrdata[marker + '_P'] = mP
        mkrdata[marker + '_V'] = np.gradient(mP)[0]
        mkrdata[marker + '_A'] = np.gradient(mkrdata[marker+'_V'])[0]
        # find gaps
        allzero = np.any(mP, axis=1).astype(int)
        if ignore_edge_gaps:
            nleading = allzero.argmax()
            allzero_trim = np.trim_zeros(allzero)
            gap_inds = np.where(allzero_trim == 0)[0] + nleading
        else:
            gap_inds = np.where(allzero == 0)[0]
        mkrdata[marker + '_gaps'] = gap_inds
    return mkrdata


def _get_c3d_subject_param(acq, param):
    try:
        param = _get_c3d_metadata_field(acq, 'PROCESSING', param)[0]
    except ValueError:
        logger.warning('Cannot get subject parameter %s' % param)
        param = None
    return param


def get_metadata(c3dfile):
    """ Read trial and subject metadata """
    trialname = os.path.basename(os.path.splitext(c3dfile)[0])
    sessionpath = os.path.dirname(c3dfile)
    acq = _get_c3dacq(c3dfile)
    # frame offset (start of trial data in frames)
    offset = acq.GetFirstFrame()
    lastfr = acq.GetLastFrame()
    length = lastfr - offset + 1  # or acq.GetPointFrameNumber()
    framerate = acq.GetPointFrequency()
    analograte = acq.GetAnalogFrequency()
    samplesperframe = acq.GetNumberAnalogSamplePerFrame()

    # count forceplates
    fpe = btk.btkForcePlatformsExtractor()
    fpe.SetInput(acq)
    fpe.Update()
    n_forceplates = len(list(btk.Iterate(fpe.GetOutput())))

    # get markers
    try:
        markers = _get_c3d_metadata_field(acq, 'POINT', 'LABELS')
    except ValueError:
        markers = list()
    # not sure what the '*xx' markers are, but delete them for now
    markers = [m for m in markers if m[0] != '*']

    #  get events
    rstrikes, lstrikes, rtoeoffs, ltoeoffs = [], [], [], []
    for i in btk.Iterate(acq.GetEvents()):
        if i.GetLabel() == "Foot Strike":
            if i.GetContext() == "Right":
                rstrikes.append(i.GetFrame())
            elif i.GetContext() == "Left":
                lstrikes.append(i.GetFrame())
            else:
                raise GaitDataError("Unknown context on foot strike event")
        elif i.GetLabel() == "Foot Off":
            if i.GetContext() == "Right":
                rtoeoffs.append(i.GetFrame())
            elif i.GetContext() == "Left":
                ltoeoffs.append(i.GetFrame())
            else:
                raise GaitDataError("Unknown context on foot strike event")

    # get subject info
    try:
        name = _get_c3d_metadata_field(acq, 'SUBJECTS', 'NAMES')[0]
    except ValueError:
        logger.warning('Cannot get subject name')
        name = u'Unknown'

    par_names = _get_c3d_metadata_subfields(acq, 'PROCESSING')
    subj_params = defaultdict(lambda: None)
    subj_params.update({par: _get_c3d_subject_param(acq, par) for
                        par in par_names})

    # sort events (may be in wrong temporal order, at least in c3d files)
    for li in [lstrikes, rstrikes, ltoeoffs, rtoeoffs]:
        li.sort()

    return {'trialname': trialname, 'sessionpath': sessionpath,
            'offset': offset, 'framerate': framerate, 'analograte': analograte,
            'name': name, 'subj_params': subj_params, 'lstrikes': lstrikes,
            'rstrikes': rstrikes, 'ltoeoffs': ltoeoffs, 'rtoeoffs': rtoeoffs,
            'length': length, 'samplesperframe': samplesperframe,
            'n_forceplates': n_forceplates, 'markers': markers}


def get_model_data(c3dfile, model, ignore_missing=False):
    modeldata = dict()
    acq = _get_c3dacq(c3dfile)
    var_dims = (3, acq.GetPointFrameNumber())
    for var in model.read_vars:
        try:
            vals = acq.GetPoint(var).GetValues()
            modeldata[var] = np.transpose(np.squeeze(vals))
        except RuntimeError:
            if model.is_optional_var(var) or ignore_missing:
                logger.info('cannot read model variable %s, returning nans'
                            % var)
                data = np.empty(var_dims)
                data[:] = np.nan
                modeldata[var] = data
            else:
                raise GaitDataError('Cannot find model variable %s in %s' %
                                    (var, c3dfile))
        # c3d stores scalars as last dim of 3-d array
        if model.read_strategy == 'last':
            modeldata[var] = modeldata[var][2, :]
    return modeldata


def get_forceplate_data(c3dfile):
    logger.debug('reading forceplate data from %s' % c3dfile)
    read_chs = ['Fx', 'Fy', 'Fz', 'Mx', 'My', 'Mz']
    acq = _get_c3dacq(c3dfile)
    fpe = btk.btkForcePlatformsExtractor()
    fpe.SetInput(acq)
    fpe.Update()
    fpdata = list()
    nplate = 0
    for plate in btk.Iterate(fpe.GetOutput()):
        logger.debug('reading from plate %d' % nplate)
        nplate += 1
        if plate.GetType() != 2:
            # Nexus should always write forceplates as type 2
            raise GaitDataError('Only type 2 forceplates are '
                                'supported for now')
        rawdata = dict()
        data = dict()
        for ch in btk.Iterate(plate.GetChannels()):
            label = ch.GetLabel()[-3:-1]  # strip descriptor and plate number
            rawdata[label] = np.squeeze(ch.GetData().GetValues())
        if not all([ch in rawdata for ch in read_chs]):
            logger.warning('could not read force/moment data for plate %d' % nplate)
            continue
        F = np.stack([rawdata['Fx'], rawdata['Fy'], rawdata['Fz']], axis=1)
        M = np.stack([rawdata['Mx'], rawdata['My'], rawdata['Mz']], axis=1)
        # this should be the plate thickness (from moment origin to physical
        # origin) needed for center of pressure calculations
        dz = np.abs(plate.GetOrigin()[2])
        cop = center_of_pressure(F, M, dz)  # in plate local coords
        Ftot = np.linalg.norm(F, axis=1)
        # locations of +x+y, -x+y, -x-y, +x-y plate corners in world coords
        # (in that order)
        cor = plate.GetCorners()
        wT = np.mean(cor, axis=1)  # translation vector, plate -> world
        # upper and lower bounds of forceplate
        ub = np.max(cor, axis=1)
        lb = np.min(cor, axis=1)
        # plate unit vectors in world system
        px = cor[:, 0] - cor[:, 1]
        py = cor[:, 0] - cor[:, 3]
        pz = np.array([0, 0, -1])
        P = np.stack([px, py, pz], axis=1)
        wR = P / np.linalg.norm(P, axis=0)  # rotation matrix, plate -> world
        # check whether cop stays inside forceplate area and clip if necessary
        cop_w = change_coords(cop, wR, wT)
        cop_wx = np.clip(cop_w[:, 0], lb[0], ub[0])
        cop_wy = np.clip(cop_w[:, 1], lb[1], ub[1])
        if not (cop_wx == cop_w[:, 0]).all() and (cop_wy == cop_w[:, 1]).all():
            logger.warning('center of pressure outside forceplate '
                           'bounds, clipping to plate')
            cop[:, 0] = cop_wx
            cop[:, 1] = cop_wy
        # XXX moment and force transformations may still be wrong
        data['F'] = change_coords(-F, wR, 0)  # not sure why sign flip needed
        data['Ftot'] = Ftot
        data['M'] = change_coords(-M, wR, 0)  # not sure why sign flip needed
        data['CoP'] = cop_w
        data['upperbounds'] = ub
        data['lowerbounds'] = lb
        data['wR'] = wR
        data['wT'] = wT
        data['cor_full'] = cor.T
        fpdata.append(data)
    return fpdata
