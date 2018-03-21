# -*- coding: utf-8 -*-
"""

c3d reader functions


@author: Jussi (jnu@iki.fi)
"""

from __future__ import print_function
import logging
import numpy as np
import os

from .numutils import center_of_pressure, change_coords
from .envutils import GaitDataError


logger = logging.getLogger(__name__)
try:
    import btk
except ImportError:
    print('Cannot find btk module; unable to read .c3d files')


def is_c3dfile(obj):
    """ Check whether obj is a valid c3d file. Currently just checks
    existence. """
    try:
        return os.path.isfile(obj)
    except TypeError:
        return False


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
    if isinstance(c3dfile, unicode):
        # btk interface cannot take unicode, so encode to latin-1 first
        c3dfile = c3dfile.encode('latin-1')
    reader.SetFilename(c3dfile)
    reader.Update()
    return reader.GetOutput()


def get_analysis(c3dfile, condition='unknown'):
    """Get analysis values from c3d (e.g. gait parameters). Returns a dict
    keyed by var and context. First key can optionally be a condition label."""
    acq = _get_c3dacq(c3dfile)
    vars = _get_c3d_metadata_field(acq, 'ANALYSIS', 'NAMES')
    units = _get_c3d_metadata_field(acq, 'ANALYSIS', 'UNITS')
    contexts = _get_c3d_metadata_field(acq, 'ANALYSIS', 'CONTEXTS')
    vals = _get_c3d_metadata_field(acq, 'ANALYSIS', 'VALUES')

    # build a nice output dict
    di = dict()
    di[condition] = dict()
    di_ = di[condition]

    for (var, unit, context, val) in zip(vars, units, contexts, vals):
        if var not in di_:
            di_[var] = dict()
            di_[var]['unit'] = unit
        if context not in di_[var]:
            di_[var][context] = val
    return di


def group_analysis(an_list, fun=np.mean):
    """ Average (or stddev etc) analysis dicts by applying fun to
    collected values. The condition label needs to be the same for all dicts.
    Returns single dict with the same condition. """
    if not isinstance(an_list, list):
        raise ValueError('Need a list of analysis dicts')
    if not an_list:
        return None
    an0 = an_list[0]
    if len(an_list) == 1:
        return an0
    conds = an0.keys()
    vars = an0[conds[0]].keys()
    res = dict()
    for cond in conds:
        res[cond] = dict()
        for var in vars:
            res[cond][var] = dict()
            res[cond][var]['unit'] = an0[cond][var]['unit']
            for context in ['Right', 'Left']:
                allvals = np.array([an[cond][var][context] for an in an_list if
                                    context in an[cond][var]])
                res[cond][var][context] = (fun(allvals) if allvals.size else
                                           np.nan)
    return res


def get_emg_data(c3dfile):
    """ Read EMG data from a c3d file. """
    acq = _get_c3dacq(c3dfile)
    data = dict()
    elnames = []
    for i in btk.Iterate(acq.GetAnalogs()):
        if i.GetDescription().find('EMG') >= 0 and i.GetUnit() == 'V':
            elname = i.GetLabel()
            elnames.append(elname)
            data[elname] = np.squeeze(i.GetValues())
    if elnames:
        return {'t': np.arange(len(data[elname])) / acq.GetAnalogFrequency(),
                'data': data}
    else:
        raise GaitDataError('No EMG channels found in data')


def get_marker_data(c3dfile, markers):
    if not isinstance(markers, list):  # listify if not already a list
        markers = [markers]
    acq = _get_c3dacq(c3dfile)
    mdata = dict()
    for marker in markers:
        try:
            mP = np.squeeze(acq.GetPoint(marker).GetValues())
        except RuntimeError:
            raise GaitDataError('Cannot read variable %s from c3d file'
                                % marker)
        mdata[marker + '_P'] = mP
        mdata[marker + '_V'] = np.gradient(mP)[0]
        mdata[marker + '_A'] = np.gradient(mdata[marker+'_V'])[0]
        # find gaps
        allzero = np.logical_and(mP[:, 0] == 0, mP[:, 1] == 0, mP[:, 2] == 0)
        mdata[marker + '_gaps'] = np.where(allzero)[0]
    return mdata


def get_metadata(c3dfile):
    """ Read some trial and subject metadata """

    trialname = os.path.basename(os.path.splitext(c3dfile)[0])
    sessionpath = os.path.dirname(c3dfile)
    acq = _get_c3dacq(c3dfile)
    # frame offset (start of trial data in frames)
    offset = acq.GetFirstFrame()
    lastfr = acq.GetLastFrame()
    length = lastfr - offset + 1
    framerate = acq.GetPointFrequency()
    analograte = acq.GetAnalogFrequency()
    samplesperframe = acq.GetNumberAnalogSamplePerFrame()

    # count forceplates
    fpe = btk.btkForcePlatformsExtractor()
    fpe.SetInput(acq)
    fpe.Update()
    n_forceplates = 0
    for plate in btk.Iterate(fpe.GetOutput()):
        n_forceplates += 1

    # get markers
    markers = _get_c3d_metadata_field(acq, 'POINT', 'LABELS')
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
    name = _get_c3d_metadata_field(acq, 'SUBJECTS', 'NAMES')[0]
    bodymass = _get_c3d_metadata_field(acq, 'PROCESSING', 'Bodymass')[0]

    # sort events (may be in wrong temporal order, at least in c3d files)
    for li in [lstrikes, rstrikes, ltoeoffs, rtoeoffs]:
        li.sort()

    return {'trialname': trialname, 'sessionpath': sessionpath,
            'offset': offset, 'framerate': framerate, 'analograte': analograte,
            'name': name, 'bodymass': bodymass, 'lstrikes': lstrikes,
            'rstrikes': rstrikes, 'ltoeoffs': ltoeoffs, 'rtoeoffs': rtoeoffs,
            'length': length, 'samplesperframe': samplesperframe,
            'n_forceplates': n_forceplates, 'markers': markers}


def get_model_data(c3dfile, model):
    modeldata = dict()
    acq = _get_c3dacq(c3dfile)
    for var in model.read_vars:
        try:
            vals = acq.GetPoint(var).GetValues()
            modeldata[var] = np.transpose(np.squeeze(vals))
        except RuntimeError:
            raise GaitDataError('Cannot find model variable %s in c3d file' %
                                var)
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
    nplate = 1
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
            raise GaitDataError('could not read force/moment data')
        F = np.stack([rawdata['Fx'], rawdata['Fy'], rawdata['Fz']], axis=1)
        M = np.stack([rawdata['Mx'], rawdata['My'], rawdata['Mz']], axis=1)
        # this should be the plate thickness (from moment origin to physical
        # origin) needed for center of pressure calculations
        dz = np.abs(plate.GetOrigin()[2])
        cop = center_of_pressure(F, M, dz)  # in plate local coords
        Ftot = np.sqrt(np.sum(F**2, axis=1))
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
        fpdata.append(data)
    return fpdata
