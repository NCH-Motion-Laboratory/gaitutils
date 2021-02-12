# -*- coding: utf-8 -*-
"""
C3D reader functions.

NB: do not use the data readers from this file directly. They are intended to be
called via the read_data module.

@author: Jussi (jnu@iki.fi)
"""

from __future__ import print_function, division
from builtins import zip
from past.builtins import basestring
from collections import defaultdict
import logging
import numpy as np
import os
import os.path as op
import sys
import shutil

from .numutils import center_of_pressure, _change_coords, _is_ascii
from .utils import TrialEvents, _step_width
from .envutils import lru_cache_checkfile, _named_tempfile, GaitDataError


logger = logging.getLogger(__name__)

# try the import the bundled btk version first (currently Python 2.7 64-bit
# only); if that fails, try other options
try:
    from .thirdparty import btk

    BTK_IMPORTED = True
except ImportError:
    try:
        import btk

        BTK_IMPORTED = True
    except ImportError:
        try:
            # try pyBTK package
            if sys.version_info.major == 3:
                from pyBTK.btk3 import btk
            elif sys.version_info.major == 2:
                from pyBTK.btk2 import btk
            else:
                raise Exception('unexpected major Python version')
            BTK_IMPORTED = True
        except ImportError:
            BTK_IMPORTED = False
            logger.warning('cannot import btk module; unable to read .c3d files')


def _is_c3d_file(source):
    """Check if source is a valid c3d file.

    XXX: Currently we just check existence.
    """
    return isinstance(source, basestring) and op.isfile(source)


def _get_c3d_metadata_subfields(acq, field):
    """Return names of metadata subfields for a given field"""
    meta = acq.GetMetaData()
    meta_s = meta.GetChild(field)
    return [f.GetLabel() for f in btk.Iterate(meta_s)]


def _get_c3d_metadata_field(acq, field, subfield):
    """Get c3d metadata FIELD:SUBFIELD as Python type.

    Always returns a list.
    """
    meta = acq.GetMetaData()

    def _get_child(field, child):
        try:
            return field.GetChild(child)
        except RuntimeError:
            raise RuntimeError('Invalid c3d metadata field: %s' % child)

    info = _get_child(_get_child(meta, field), subfield).GetInfo()
    if info.GetFormatAsString() == 'Char':
        return [s.strip() for s in info.ToString()]
    elif info.GetFormatAsString() == 'Real':
        return [x for x in info.ToDouble()]
    else:
        raise RuntimeError('Unhandled btk meta info type')


@lru_cache_checkfile
def _get_c3dacq(c3dfile):
    """Get a btk c3dacq object.

    Object is returned from cache if filename and digest match.
    """
    reader = btk.btkAcquisitionFileReader()
    # Py2: btk interface cannot take unicode, so encode to latin-1 first
    if sys.version_info.major == 2:
        c3dfile = c3dfile.encode('latin-1')
    reader.SetFilename(c3dfile)
    try:
        reader.Update()
    except RuntimeError as e:
        # this is a workaround for an unresolved BTK Python 3 bug, where
        # filenames containing extended characters cannot be read
        if not _is_ascii(c3dfile) and sys.version_info.major == 3:
            logger.warning('trying to work around possible btk extended chars bug')
            # just copy the file into another directory
            temp_path = _named_tempfile(suffix='.c3d')
            shutil.copy2(c3dfile, temp_path)
            logger.warning('using %s' % temp_path)
            # we need to create a new reader here
            # (the previous update call screws it up somehow)
            reader = btk.btkAcquisitionFileReader()
            reader.SetFilename(temp_path)
            reader.Update()
            # we should be able to remove the temp file now
            os.remove(temp_path)
        else:
            # something else went wrong during read
            raise e
    return reader.GetOutput()


def get_analysis(c3dfile, condition='unknown'):
    """Get analysis values from c3d (e.g. gait parameters).

    Parameters
    ----------
    c3dfile : str
        Name of the file.
    condition : str, optional
        The condition name, by default 'unknown'.

    Returns
    -------
    dict
        A nested dict of the analysis values, keyed by variable name and
        context. The first key is the condition name.
    """
    logger.debug('getting analysis values from %s' % c3dfile)
    acq = _get_c3dacq(c3dfile)
    try:
        vars_ = _get_c3d_metadata_field(acq, 'ANALYSIS', 'NAMES')
        units = _get_c3d_metadata_field(acq, 'ANALYSIS', 'UNITS')
        contexts = _get_c3d_metadata_field(acq, 'ANALYSIS', 'CONTEXTS')
        vals = _get_c3d_metadata_field(acq, 'ANALYSIS', 'VALUES')
    except RuntimeError:
        raise GaitDataError('Cannot read time-distance parameters from %s' % c3dfile)

    # build a nice output dict
    di = defaultdict(lambda: defaultdict(dict))
    di_ = di[condition]

    for (var, unit, context, val) in zip(vars_, units, contexts, vals):
        di_[var]['unit'] = unit
        di_[var][context] = val

    # if c3d was missing vals for some var/context, insert nans
    for var in di_:
        for context in ['Left', 'Right']:
            if context not in di_[var]:
                logger.warning(
                    '%s has missing value: %s / %s' % (c3dfile, var, context)
                )
                di_[var][context] = np.nan

    # Nexus <2.8 did not output step width into c3d, so compute it here if
    # needed
    if 'Step Width' not in di_:
        logger.warning('computing step widths (not found in %s)' % c3dfile)
        sw = _step_width(c3dfile)
        di[condition]['Step Width'] = dict()
        # XXX: currently uses average of all cycles from trial
        di[condition]['Step Width']['Right'] = np.array(sw['R']).mean()
        di[condition]['Step Width']['Left'] = np.array(sw['L']).mean()
        di[condition]['Step Width']['unit'] = 'm'
    return di


def _get_emg_data(c3dfile):
    """Read EMG data from a c3d file.

    See read_data.get_emg_data() for details.
    """
    return _get_analog_data(c3dfile, 'EMG')


def _get_accelerometer_data(c3dfile):
    """Read accelerometer data from a c3d file"""
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
    """Read analog data from a c3d file.

    devname is matched against channel names.
    """
    acq = _get_c3dacq(c3dfile)
    data = dict()
    chnames = []
    for i in btk.Iterate(acq.GetAnalogs()):
        if i.GetDescription().find(devname) >= 0:
            chname = i.GetLabel()
            chnames.append(chname)
            data[chname] = np.squeeze(i.GetValues())
    if chnames:
        return {
            't': np.arange(len(data[chname])) / acq.GetAnalogFrequency(),
            'data': data,
        }
    else:
        raise GaitDataError(
            'No analog channels matching device %s found in data' % devname
        )


def _get_marker_data(c3dfile, markers, ignore_missing=False):
    """Get position data for specified markers.

    See read_data.get_marker_data for details.
    """
    if not isinstance(markers, list):  # listify if not already a list
        markers = [markers]
    acq = _get_c3dacq(c3dfile)
    mkrdata = dict()
    for marker in markers:
        try:
            mkrdata[marker] = np.squeeze(acq.GetPoint(marker).GetValues())
        except RuntimeError:
            if ignore_missing:
                logger.warning('Cannot read trajectory %s from c3d file' % marker)
                continue
            else:
                raise GaitDataError('Cannot read trajectory %s from c3d file' % marker)
    return mkrdata


def _get_c3d_subject_param(acq, param):
    try:
        param = _get_c3d_metadata_field(acq, 'PROCESSING', param)[0]
    except RuntimeError:
        logger.warning('Cannot get subject parameter %s' % param)
        param = None
    return param


def _get_metadata(c3dfile):
    """Read trial and subject metadata from c3d file.

    See read_data.get_metadata() for details.
    """
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
    except RuntimeError:
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
    events = TrialEvents(
        rstrikes=rstrikes, lstrikes=lstrikes, rtoeoffs=rtoeoffs, ltoeoffs=ltoeoffs
    )

    # get subject info
    try:
        name = _get_c3d_metadata_field(acq, 'SUBJECTS', 'NAMES')[0]
    except RuntimeError:
        logger.warning('Cannot get subject name')
        name = u'Unknown'

    try:
        par_names = _get_c3d_metadata_subfields(acq, 'PROCESSING')
    except RuntimeError:
        raise GaitDataError('%s is missing required subject info' % c3dfile)
    subj_params = defaultdict(lambda: None)
    subj_params.update({par: _get_c3d_subject_param(acq, par) for par in par_names})

    return {
        'trialname': trialname,
        'sessionpath': sessionpath,
        'offset': offset,
        'framerate': framerate,
        'analograte': analograte,
        'name': name,
        'subj_params': subj_params,
        'events': events,
        'length': length,
        'samplesperframe': samplesperframe,
        'n_forceplates': n_forceplates,
        'markers': markers,
    }


def _get_model_data(c3dfile, model):
    """Read model output variables (e.g. Plug-in Gait).

    See read_data.get_model_data for details.
    """
    modeldata = dict()
    acq = _get_c3dacq(c3dfile)
    var_dims = (3, acq.GetPointFrameNumber())
    for var in model.read_vars:
        try:
            vals = acq.GetPoint(var).GetValues()
            modeldata[var] = np.transpose(np.squeeze(vals))
        except RuntimeError:
            logger.info('cannot read model variable %s, returning nans' % var)
            data = np.empty(var_dims)
            data[:] = np.nan
            modeldata[var] = data
        # c3d stores scalars as last dim of 3-d array
        if model.read_strategy == 'last':
            modeldata[var] = modeldata[var][2, :]
    return modeldata


def _get_forceplate_data(c3dfile):
    """Read data of all forceplates from c3d file.

    See read_data.get_forceplate_data() for details.
    """
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
            raise GaitDataError('Only type 2 forceplates are supported for now')
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
        # we need to calculate center of pressure, since it's not in the c3d
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
        # check whether CoP stays inside forceplate area and clip if necessary
        cop_w = _change_coords(cop, wR, wT)
        cop_wx = np.clip(cop_w[:, 0], lb[0], ub[0])
        cop_wy = np.clip(cop_w[:, 1], lb[1], ub[1])
        if not (cop_wx == cop_w[:, 0]).all() and (cop_wy == cop_w[:, 1]).all():
            logger.warning(
                'center of pressure outside forceplate bounds, clipping to plate'
            )
            cop[:, 0] = cop_wx
            cop[:, 1] = cop_wy
        # XXX moment and force transformations may still be wrong
        data['F'] = _change_coords(-F, wR, 0)  # not sure why sign flip needed
        data['Ftot'] = Ftot
        data['M'] = _change_coords(-M, wR, 0)  # not sure why sign flip needed
        data['CoP'] = cop_w
        data['wR'] = wR
        data['wT'] = wT
        data['plate_corners'] = cor.T
        fpdata.append(data)
    return fpdata
