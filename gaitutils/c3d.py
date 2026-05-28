# -*- coding: utf-8 -*-
"""
C3D reader functions.

NB: do not use the data readers from this file directly. They are intended to be
called via the read_data module.
"""

from collections import defaultdict
import logging
from pathlib import Path
import shutil

import numpy as np
import ezc3d

from .utils import _step_width
from .envutils import GaitDataError, _named_tempfile
from .events import GaitEvents, GaitEvent
from .envutils import GaitDataError
from .numutils import center_of_pressure, _change_coords


logger = logging.getLogger(__name__)

def _robust_open_c3d(c3dfile):
    """
    Try to open a c3d file with ezc3d, and if it fails, try to work around a possible
    bug in ezc3d that causes it to fail when the file path contains extended characters.
    """

    fname = str(c3dfile)  # accept Path objects too (ezc3d won't eat those)

    try:
        c3d = ezc3d.c3d(fname)
        return c3d
    
    except RuntimeError as e:
        logger.warning('trying to work around possible extended chars bug')

        # just copy the file into another directory
        temp_path = _named_tempfile(suffix='.c3d')
        shutil.copy2(fname, temp_path)
        logger.warning(f'using {temp_path}')
        c3d = ezc3d.c3d(temp_path)
        temp_path.unlink()  # delete the temp file
        return c3d

def _is_c3d_file(source):
    """Check if source is a valid c3d file.

    XXX: Currently we just check existence. Would be good to check file header.
    """
    try:
        return Path(source).is_file()
    except TypeError:
        return False


def get_analysis(c3dfile, condition='unknown'):
    """Get ANALYSIS values from a c3d file.
    
    Usually these are the time-distance parameters, but other values may be
    stored as well.

    Parameters
    ----------
    c3dfile : str | Path
        Path to the file.
    condition : str, optional
        The condition, by default 'unknown'. The condition is only used to
        annotate the output dictionary.

    Returns
    -------
    dict
        A nested dict of the analysis values. Keys are condition, variable, and
        context/unit. For example, di['unknown']['Step Width']['Right'] would contain
        the step width for the right foot. 

    """

    # used to change units; we currently change steps/min for brevity
    UNIT_CONVERSIONS = {'steps/min': '1/min'}

    logger.debug(f'getting analysis values from {c3dfile}')

    try:
        c3d = _robust_open_c3d(c3dfile)

        names = c3d['parameters']['ANALYSIS']['NAMES']['value']
        units = c3d['parameters']['ANALYSIS']['UNITS']['value']
        contexts = c3d['parameters']['ANALYSIS']['CONTEXTS']['value']
        values = c3d['parameters']['ANALYSIS']['VALUES']['value']

        # some consistency checks
        assert len(names) == len(units)
        assert len(names) == len(contexts)
        assert len(names) == len(values)
    
    except RuntimeError:
        raise GaitDataError(f'Cannot read time-distance parameters from {c3dfile}')
    
    res = defaultdict(lambda: {})

    for name, unit, context, value in zip(names, units, contexts, values):
        if unit in UNIT_CONVERSIONS:
            unit = UNIT_CONVERSIONS[unit]
        res[name]['unit'] = unit

        if context in ['Left', 'Right']:
            res[name][context] = float(value)
        else:
            logger.warning(f'Ignoring invalid context {context} in {c3dfile} for variable {name}')

    # if c3d was missing vals for some var/context, insert nans
    for name in res:
        for context in ['Left', 'Right']:
            if context not in res[name]:
                logger.warning(f'{c3dfile} has missing value: {name} / {context}')
                res[name][context] = np.nan


    # Nexus version <2.8 did not output step width into c3d, so compute it here
    # if needed
    if 'Step Width' not in res:
        logger.warning(f'computing step widths (not found in {c3dfile})')
        sw = _step_width(c3dfile)
        res['Step Width'] = dict()
        # XXX: currently uses average of all cycles from trial
        res['Step Width']['Right'] = np.array(sw['R']).mean()
        res['Step Width']['Left'] = np.array(sw['L']).mean()
        res['Step Width']['unit'] = 'm'

    return {condition: res}


def _get_emg_data(c3dfile):
    c3d = _robust_open_c3d(c3dfile)
    srates = c3d['parameters']['ANALOG']['RATE']['value']
    assert srates.shape == (1,), 'There should be only one sampling rate'
    sfreq = srates[0]

    ch_idxs = [desc.startswith('Analog EMG::Voltage') for desc in c3d['parameters']['ANALOG']['DESCRIPTIONS']['value']]
    ch_idxs = np.arange(len(ch_idxs))[ch_idxs]
    ch_names = np.array(c3d['parameters']['ANALOG']['LABELS']['value'])[ch_idxs]

    data = {ch_name: c3d['data']['analogs'][0, ch_idx, :] for ch_name, ch_idx in zip(ch_names, ch_idxs)}

    if len(data) == 0:
        raise GaitDataError(f'No EMG channels found in {c3dfile}')

    t = np.arange(c3d['data']['analogs'].shape[2]) / sfreq

    return {'t': t, 'data': data}


def _get_marker_data(c3dfile, markers, ignore_missing=False):
    """Get position data for specified markers.

    See read_data.get_marker_data for details.
    """
    if not isinstance(markers, list):  # listify if not already a list
        markers = [markers]

    c3d = _robust_open_c3d(c3dfile)

    res = {}

    for marker in markers:
        if marker in c3d['parameters']['POINT']['LABELS']['value']:
            idx = c3d['parameters']['POINT']['LABELS']['value'].index(marker)
            res[marker] = c3d['data']['points'][:3, idx, :].T
        else:
            if ignore_missing:
                logger.warning(f'Cannot read trajectory {marker} from c3d file')
                continue
            else:
                raise GaitDataError(f'Cannot read trajectory {marker} from c3d file')
            
    return res


def _get_metadata(c3dfile):
    """Read trial and subject metadata from c3d file.

    See read_data.get_metadata() for details.
    """
    EVENT_LABEL_MAP = {'Foot Strike': 'strike', 'Foot Off': 'toeoff'}
    EVENT_CONTEXT_MAP = {'Right': 'R', 'Left': 'L'}

    trialname = Path(c3dfile).stem
    sessionpath = Path(c3dfile).parent

    c3d = _robust_open_c3d(c3dfile)

    offset = c3d['header']['points']['first_frame'] + 1 
    length = c3d['header']['points']['last_frame'] - offset + 2

    framerate = c3d['parameters']['POINT']['RATE']['value'][0]
    analograte = c3d['parameters']['ANALOG']['RATE']['value'][0]
    samplesperframe = analograte / framerate
    if samplesperframe != round(samplesperframe):
        samplesperframe = round(samplesperframe)
        logger.warning(f'Analog sampling rate {analograte} is not an integer multiple of framerate {framerate} in {c3dfile}, rounding samples per frame to {samplesperframe}')

    n_forceplates = c3d['parameters']['FORCE_PLATFORM']['USED']['value'][0]

    # get markers
    markers = c3d['parameters']['POINT']['LABELS']['value']
    # XXX: not sure what the '*xx' markers are, but delete them for now
    markers = [m for m in markers if m[0] != '*']

    #  get events
    events = GaitEvents()

    try:
        fr_offsets = c3d['parameters']['EVENT']['TIMES']['value'][1] * framerate - offset + 1
        contexts = c3d['parameters']['EVENT']['CONTEXTS']['value']
        ev_types = c3d['parameters']['EVENT']['LABELS']['value']
    except KeyError:
        fr_offsets = []
        contexts = []
        ev_types = []

    for fr_offset, context, ev_type in zip(fr_offsets, contexts, ev_types):
        if ev_type in EVENT_LABEL_MAP and context in EVENT_CONTEXT_MAP:
            events.append(GaitEvent(int(round(fr_offset)), EVENT_LABEL_MAP[ev_type], EVENT_CONTEXT_MAP[context]))
        else:
            logger.warning(f'Ignoring event with unrecognized type/context: {ev_type} / {context} in {c3dfile}')

    # get subject info
    try:
        subj_names = c3d['parameters']['SUBJECTS']['NAMES']['value']
        if len(subj_names) == 0:
            logger.warning(f'No subject name found in {c3dfile}, using "Unknown"')
            subj_name = 'Unknown'
        elif len(subj_names) > 1:
            logger.warning(f'Multiple subject names found in {c3dfile}')
            subj_name = 'Multiple subjects'
        else:
            subj_name = subj_names[0]
    except KeyError:
        logger.warning(f'No subject name found in {c3dfile}, using "Unknown"')
        subj_name = 'Unknown'

    subj_params = {}

    try:
        processing_items = c3d['parameters']['PROCESSING'].items()
    except KeyError:
        logger.warning(f'{c3dfile} is missing the PROCESSING section that contains subject info (bodyweight etc.)')
        processing_items = []

    for k, v in processing_items:
        try:
            subj_params[k] = v['value'][0]
        except KeyError:
            pass

    return {
        'trialname': trialname,
        'sessionpath': sessionpath,
        'offset': offset,
        'framerate': framerate,
        'analograte': analograte,
        'subject_name': subj_name,
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
    c3d = _robust_open_c3d(c3dfile)

    modeldata = {}
    var_dims = (3, c3d['header']['points']['last_frame'] - c3d['header']['points']['first_frame'] + 1)

    for var in model.read_vars:
        try:
            labels = c3d['parameters']['POINT']['LABELS']['value']
            idxs = [i for i, label in enumerate(labels) if label == var]
            modeldata[var] = c3d['data']['points'][:3, idxs[0], :]
        except IndexError:
            logger.info(f'cannot read model variable {var}, returning nans')
            data = np.empty(var_dims)
            data[:] = np.nan
            modeldata[var] = data

        # c3d stores scalars as last dim of 3-d array
        if model.read_strategy == 'last':
            modeldata[var] = modeldata[var][2, :]

    return modeldata


def _get_1_forceplate_data(c3d, plate_idx):
    """Read data of a single forceplate from a c3d file.
    c3d is a pre-loaded ezc3d object.

    plate_idx is the index of the forceplate in the
    ['parameters']['FORCE_PLATFORM'] section of the c3d file.
    """
    # These are the channel names in our setup (Vicon specific?).
    # Other c3d files may have different channel names (e.g. FX, FY, FZ, ...),
    # this code will not work for those.
    READ_CHS = ['Fx', 'Fy', 'Fz', 'Mx', 'My', 'Mz']

    if c3d['parameters']['FORCE_PLATFORM']['TYPE']['value'][plate_idx] != 2:
        # Nexus should always write forceplates as type 2
        raise GaitDataError('Only type 2 forceplates are supported for now')
    
    rawdata = {}
    for ch_idx in c3d['parameters']['FORCE_PLATFORM']['CHANNEL']['value'][:, plate_idx]:
        label = c3d['parameters']['ANALOG']['LABELS']['value'][ch_idx-1] # c3d channel indices are 1-based, but ezc3d data arrays are 0-based
        label = label[-3: -1] # e.g. 'Force.Fx1' -> 'Fx', specific to our setup
        rawdata[label] = c3d['data']['analogs'][0, ch_idx-1, :]

    if not all([ch in rawdata for ch in READ_CHS]):
        logger.warning(f'could not read force/moment data for plate {plate_idx+1}')
        return None
    
    F = np.stack([rawdata['Fx'], rawdata['Fy'], rawdata['Fz']], axis=1)
    M = np.stack([rawdata['Mx'], rawdata['My'], rawdata['Mz']], axis=1)

    # we need to calculate the center of pressure, since it's not in the C3D
    # dz is the plate thickness (from moment origin to physical origin) needed
    # for center of pressure calculations
    dz = np.abs(c3d['parameters']['FORCE_PLATFORM']['ORIGIN']['value'][2, plate_idx])
    cop = center_of_pressure(F, M, dz)  # in plate local coords
    Ftot = np.linalg.norm(F, axis=1)
    # locations of +x+y, -x+y, -x-y, +x-y plate corners in world coords
    # (in that order)
    cor = c3d['parameters']['FORCE_PLATFORM']['CORNERS']['value'][:, :, plate_idx]
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
    return {
        'F': _change_coords(-F, wR, 0),  # not sure why sign flip needed
        'Ftot': Ftot,
        'M': _change_coords(-M, wR, 0),  # not sure why sign flip needed
        'CoP': cop_w,
        'wR': wR,
        'wT': wT,
        'plate_corners': cor.T
    }


def _get_forceplate_data(c3dfile):
    """Read data of all forceplates from c3d file.

    See read_data.get_forceplate_data() for details.
    """
    logger.debug(f'reading forceplate data from {c3dfile}')

    c3d = _robust_open_c3d(c3dfile)
    fpdata = []

    for i in range(c3d['parameters']['FORCE_PLATFORM']['USED']['value'][0]):
        logger.debug(f'reading from plate {i+1}')
        data = _get_1_forceplate_data(c3d, i)
        if data is not None:
            # generate the Eclipse key
            data['eclipse_key'] = f'FP{i+1}'
            fpdata.append(data)
    return fpdata
