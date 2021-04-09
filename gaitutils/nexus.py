# -*- coding: utf-8 -*-
"""
Vicon Nexus utils & data readers.

NB: do not use the data readers from this file directly. They are intended to be
called via the read_data module.

@author: Jussi (jnu@iki.fi)
"""

from collections import defaultdict
import sys
import numpy as np
import os.path as op
import psutil
import glob
import logging
import time
import multiprocessing
import subprocess

from .numutils import _change_coords, _isfloat, _isint, _rigid_body_extrapolate_markers
from .utils import TrialEvents
from .envutils import GaitDataError
from .config import cfg

logger = logging.getLogger(__name__)


try:
    from viconnexusapi import ViconNexus

    NEXUS_IMPORTED = True
except ImportError:
    logger.debug('cannot import Vicon Nexus SDK')
    NEXUS_IMPORTED = False


def _find_nexus_path(vicon_path=None):
    """Return path to most recent Nexus version.

    vicon_path is the Vicon root directory.
    """
    if vicon_path is None:
        vicon_path = r'C:\Program Files (x86)\Vicon'  # educated guess
    if not op.isdir(vicon_path):
        return None
    nexus_glob = op.join(vicon_path, 'Nexus?.*')
    nexus_dirs = glob.glob(nexus_glob)
    if not nexus_dirs:
        return None
    nexus_vers = [op.split(dir_)[1][5:] for dir_ in nexus_dirs]
    # convert into major,minor lists: [[2,1], [2,10]] etc.
    try:
        nexus_vers = [[int(s) for s in v.split('.')] for v in nexus_vers]
    except ValueError:
        return None
    # 2-key sort using first major and then minor version number
    idx = nexus_vers.index(max(nexus_vers, key=lambda l: (l[0], l[1])))
    return nexus_dirs[idx]


def _nexus_pid():
    """Try to return the PID of the currently running Nexus process"""
    PROCNAME = "Nexus.exe"
    for proc in psutil.process_iter():
        try:
            if proc.name() == PROCNAME:
                return proc.pid
        # catch NoSuchProcess for procs that disappear inside loop
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            pass
    return None


def _nexus_version():
    """Get Nexus version via API"""
    vicon = viconnexus()
    info = vicon.GetServerInfo()
    return info[1], info[2]


def _nexus_ver_greater(major, minor):
    """Checks if running Nexus version is at least the given version"""
    vmaj, vmin = _nexus_version()
    if vmaj is None:
        return False
    else:
        return vmaj >= major and vmin >= minor


def _start_nexus():
    """Start Vicon Nexus"""
    exe = op.join(_find_nexus_path(), 'Nexus.exe')
    p = subprocess.Popen([exe])
    return p


def _kill_nexus(p=None, restart=False):
    """Kill Vicon Nexus process p"""
    if p is None:
        pid = _nexus_pid()
        p = psutil.Process(pid)
    p.terminate()
    if restart:
        time.sleep(5)
        _start_nexus()


def viconnexus():
    """Return a ViconNexus() (SDK control object) instance.

    Raises an exception if Nexus is not running.

    Returns
    -------
    ViconNexus
        The instance.
    """
    _check_nexus()
    return ViconNexus.ViconNexus()


def _close_trial():
    """Try to close currently opened Nexus trial"""
    vicon = viconnexus()
    # this op was not supported before Nexus 2.8
    if _nexus_ver_greater(2, 8):
        logger.info('force closing open trial')
        vicon.CloseTrial(5000)
    else:
        logger.info('current Nexus API version does not support closing trials')


def _open_trial(trialpath, close_first=True):
    """Open trial in Nexus"""
    vicon = viconnexus()
    if close_first:
        _close_trial()
    # Nexus wants the path without filename extension (e.g. .c3d)
    trialpath_ = op.splitext(trialpath)[0]
    vicon.OpenTrial(trialpath_, 60)


def get_subjectnames(single_only=True):
    """Get current subject name(s) from Nexus.

    Parameters
    ----------
    single_only : bool, optional
        Accept and return a single subject only. If True, an exception will be
        raised if Nexus has multiple subjects defined.

    Returns
    -------
    str | list
        The subject name, or a list of names.
    """
    vicon = viconnexus()
    get_sessionpath()  # check whether we can get data
    names_ = vicon.GetSubjectNames()
    if not names_:
        raise GaitDataError('No subject defined in Nexus')
    if single_only:
        if len(names_) > 1:
            raise GaitDataError('Nexus returns multiple subjects')
    # workaround a Nexus 2.6 bug (?) that creates extra names with weird unicode
    # strings
    names_ = [name for name in names_ if u'\ufffd1' not in name]
    return names_[0] if single_only else names_


def _check_nexus():
    """Check whether Nexus is currently running"""
    if not _nexus_pid():
        raise GaitDataError('Vicon Nexus does not seem to be running')


def get_sessionpath():
    """Get path to current Nexus session.

    Returns
    -------
    str
        The path.
    """
    try:
        vicon = viconnexus()
        sessionpath = vicon.GetTrialName()[0]
    except IOError:  # may be raised if Nexus was just terminated
        sessionpath = None
    if not sessionpath:
        raise GaitDataError(
            'Cannot get Nexus session path, no session or maybe in Live mode?'
        )
    return op.normpath(sessionpath)


def _run_pipeline(pipeline, foo, timeout):
    """Wrapper needed for multiprocessing module due to pickle limitations"""
    vicon = viconnexus()
    return vicon.RunPipeline(pipeline, foo, timeout)


def _run_pipelines(pipelines):
    """Run given Nexus pipeline(s).

    Note: this version will stall the calling Python interpreter until the
    pipeline is finished.
    """
    if type(pipelines) != list:
        pipelines = [pipelines]
    for pipeline in pipelines:
        logger.debug('running pipeline: %s' % pipeline)
        _run_pipeline(pipeline, '', cfg.autoproc.nexus_timeout)


def _run_pipelines_multiprocessing(pipelines):
    """Run given Nexus pipeline(s) via the multiprocessing module.

    The idea is to work around the Python global interpreter lock, since the
    Nexus SDK does not release it. By starting a new interpreter process for the
    pipeline, this version causes the invoking thread to sleep and release the
    GIL while the pipeline is running.
    """
    if type(pipelines) != list:
        pipelines = [pipelines]
    for pipeline in pipelines:
        logger.debug('running pipeline via multiprocessing module: %s' % pipeline)
        args = (pipeline, '', cfg.autoproc.nexus_timeout)
        p = multiprocessing.Process(target=_run_pipeline, args=args)
        p.start()
        while p.exitcode is None:
            time.sleep(0.1)


def _get_trialname():
    """Get current Nexus trialname without the session path"""
    vicon = viconnexus()
    trialname_ = vicon.GetTrialName()
    return trialname_[1]


def _is_vicon_instance(obj):
    """Check if obj is an instance of ViconNexus"""
    return obj.__class__.__name__ == 'ViconNexus'


def _get_nexus_subject_param(vicon, name, param):
    """Wrapper to get subject parameter from Nexus."""
    value = vicon.GetSubjectParam(name, param)
    # for unknown reasons, above method may return tuple or float
    # depending on whether script is run from Nexus or outside
    if type(value) == tuple:
        value = value[0] if value[1] else None
    return value


def _get_marker_names(vicon, trajs_only=True):
    """Return marker names from Nexus.

    If trajs_only, only return markers with trajectories.
    """
    subjname = get_subjectnames()
    markers = vicon.GetMarkerNames(subjname)
    # only get markers with trajectories - excludes calibration markers
    if trajs_only:
        markers = [mkr for mkr in markers if vicon.HasTrajectory(subjname, mkr)]
    return markers


def _get_metadata(vicon):
    """Read trial and subject metadata from Nexus.

    See read.data.get_metadata for details."""
    _check_nexus()
    logger.debug('reading metadata from Vicon Nexus')
    subjname = get_subjectnames()
    params_available = vicon.GetSubjectParamNames(subjname)
    subj_params = defaultdict(lambda: None)
    subj_params.update(
        {
            par: _get_nexus_subject_param(vicon, subjname, par)
            for par in params_available
        }
    )
    trialname = _get_trialname()
    if not trialname:
        raise GaitDataError('No trial loaded in Nexus')
    sessionpath = get_sessionpath()
    markers = _get_marker_names(vicon)
    # get foot strike and toeoffevents. GetEvents() indices seem to often be 1
    # frame less than on Nexus display - only happens with ROI?
    lstrikes = vicon.GetEvents(subjname, "Left", "Foot Strike")[0]
    rstrikes = vicon.GetEvents(subjname, "Right", "Foot Strike")[0]
    ltoeoffs = vicon.GetEvents(subjname, "Left", "Foot Off")[0]
    rtoeoffs = vicon.GetEvents(subjname, "Right", "Foot Off")[0]
    events = TrialEvents(
        rstrikes=rstrikes, lstrikes=lstrikes, rtoeoffs=rtoeoffs, ltoeoffs=ltoeoffs
    )

    # offset will be subtracted from event frame numbers to get correct
    # 0-based index for frame data. for Nexus, it is always 1 (Nexus uses
    # 1-based frame numbering)
    offset = 1
    length = vicon.GetFrameCount()
    framerate = vicon.GetFrameRate()
    # get analog rate. this may not be mandatory if analog devices
    # are not used, but currently it needs to succeed.
    devids = vicon.GetDeviceIDs()
    if not devids:
        raise GaitDataError('Cannot determine analog rate')
    else:
        # rates may be 0 for some devices, we just pick the maximum as "the rate"
        analogrates = [vicon.GetDeviceDetails(id)[2] for id in devids]
        analograte = max(rate for rate in analogrates if _isfloat(rate))
    if analograte == 0.0:
        raise GaitDataError('Cannot determine analog rate')
    samplesperframe = analograte / framerate
    logger.debug(
        'offset @ %d, %d frames, framerate %d Hz, %d samples per '
        'frame' % (offset, length, framerate, samplesperframe)
    )
    # get n of forceplates
    fp_devids = [
        id_ for id_ in devids if vicon.GetDeviceDetails(id_)[1].lower() == 'forceplate'
    ]

    return {
        'trialname': trialname,
        'sessionpath': sessionpath,
        'offset': offset,
        'framerate': framerate,
        'analograte': analograte,
        'name': subjname,
        'subj_params': subj_params,
        'events': events,
        'length': length,
        'samplesperframe': samplesperframe,
        'n_forceplates': len(fp_devids),
        'markers': markers,
    }


def _get_emg_data(vicon):
    """Read EMG data from Nexus. Uses the configured EMG device name."""
    return _get_analog_data(vicon, cfg.emg.devname)


def _get_accelerometer_data(vicon):
    """Read accelerometer data from Nexus. Uses the configured acc device name."""
    return _get_analog_data(vicon, cfg.analog.accelerometer_devname)


def _get_analog_data(vicon, devname):
    """Read analog data from Vicon Nexus.

    Parameters
    ----------
    vicon : ViconNexus
        The SDK object.
    devname : str
        The analog device name, set in Nexus configuration. E.g. 'Myon EMG'.

    Returns
    -------
    dict
        Dict with keys 't' (time points corresponding to data samples) and
        'data' (the analog data as shape (N,) ndarray, for each output channel).
    """
    # match devname exactly (not case-sensitive though)
    ids = [
        id_
        for id_ in vicon.GetDeviceIDs()
        if vicon.GetDeviceDetails(id_)[0].lower() == devname.lower()
    ]
    if len(ids) > 1:
        raise GaitDataError('Multiple matching analog devices for %s' % devname)
    elif len(ids) == 0:
        raise GaitDataError('No matching analog devices for %s' % devname)
    dev_id = ids[0]
    dname, dtype, drate, outputids, _, _ = vicon.GetDeviceDetails(dev_id)
    # gather device outputs; there does not seem to be any reliable way to
    # identify output IDs that have actual EMG signal, so we use the heuristic
    # of units being volts. this may lead to inclusion of some channels (e.g.
    # Foot Switch on Noraxon) that are not actually EMG
    emg_outputids = [
        outputid
        for outputid in outputids
        if vicon.GetDeviceOutputDetails(dev_id, outputid)[2] == 'volt'
    ]

    data = dict()
    for outputid in emg_outputids:
        # get list of channel names and IDs
        outputname, _, _, _, chnames, chids = vicon.GetDeviceOutputDetails(
            dev_id, outputid
        )
        for chid in chids:
            chdata, _, chrate = vicon.GetDeviceChannel(dev_id, outputid, chid)
            chname = chnames[chid - 1]  # chids start from 1
            # in case of multiple output ids (e.g. Noraxon), the channel
            # names may not be unique, so try to generate unique names by
            # merging output name and channel name
            if len(emg_outputids) > 1:
                logger.warning(
                    'merging output %s and channel name %s for a unique name'
                    % (outputname, chname)
                )
                chname = '%s_%s' % (outputname, chname)
            if chname in data:
                raise RuntimeError('duplicate EMG channel; check Nexus device settings')
            data[chname] = np.array(chdata)
    # WIP: sanity checks for data (channel lengths equal, etc.)
    t = np.arange(len(chdata)) / drate  # time axis
    return {'t': t, 'data': data}


def _get_forceplate_ids(vicon):
    """Return Nexus forceplate device IDs"""
    return [
        id_
        for id_ in vicon.GetDeviceIDs()
        if vicon.GetDeviceDetails(id_)[1].lower() == 'forceplate'
    ]


def set_forceplate_data(vicon, fp_index, data, kind='Force'):
    """Set forceplate data in Nexus.

    This always sets the data in the device local frame. To set data in the
    global frame, you need to get the local->global transformation from Nexus,
    invert it, and apply the resulting global->local transformation to inputs.

    Parameters
    ----------
    vicon : ViconNexus
        The SDK object.
    fp_index : int
        The index of the forceplate (0...N). Note that this is not the same as
        Nexus device ID.
    data : ndarray
        Tx3 array of data, where T is number of analog frames in current data. T
        needs to equal the number of analog samples in the current Nexus trial
        (not the ROI, but whole trial).
    kind : str, optional
        Kind of data to write. Can be 'Force', 'Moment' or 'CoP', by default
        'Force'.
    """
    kinds = ['Force', 'Moment', 'CoP']
    if kind not in kinds:
        raise ValueError('kind argument needs to be one of %s' % ', '.join(kinds))
    fpids = _get_forceplate_ids(vicon)
    if not fpids:
        raise RuntimeError('no forceplates detected')
    else:
        try:
            fpid = fpids[fp_index]
        except IndexError:
            raise RuntimeError(
                'Invalid plate index %d (detected %d forceplates)'
                % (fp_index, len(fpids))
            )
    outputid = vicon.GetDeviceOutputIDFromName(fpid, kind)
    for dim, data_dim in zip('xyz', data.T):
        chname = kind[0] + dim  # e.g. 'Fx'
        chid = vicon.GetDeviceChannelIDFromName(fpid, outputid, chname)
        vicon.SetDeviceChannel(fpid, outputid, chid, data_dim)


def _get_1_forceplate_data(vicon, devid, coords='global'):
    """Read data of a single forceplate from Nexus.

    Parameters
    ----------
    vicon : ViconNexus
        The SDK object.
    devid : int
        The device id.
    coords : str, optional
        Whether to return data in 'global' or 'local' coordinate system.

    Returns
    -------
    dict
        Force dict with the following keys and values:

        F : ndarray
            Nx3 matrix of force.
        Ftot : ndarray
            Nx1 matrix of force magnitude.
        M : ndarray
            Nx3 matrix of moment.
        CoP : ndarray
            Nx3 matrix of center of pressure.
        wR : ndarray
            3x3 rotation matrix for local -> global frame.
        wT : ndarray
            1x3 transformation vector for local -> global frame.
        plate_corners : ndarray
            4x3 matrix of the four plate corners.

    All data is returned in the coordinate frame specified by the coords
    parameter. wR and wT are always returned as local -> world transformation.
    """
    if coords == 'global':
        getter_fun = vicon.GetDeviceChannelGlobal
    elif coords == 'local':
        getter_fun = vicon.GetDeviceChannel
    else:
        raise ValueError('Invalid coords argument, must be "global" or "local"')
    logger.debug('reading forceplate data from devid %d' % devid)
    dname, dtype, drate, outputids, nfp, _ = vicon.GetDeviceDetails(devid)
    kinds = ['Force', 'Moment', 'CoP']
    alldata = dict()
    for kind in kinds:
        outputid = vicon.GetDeviceOutputIDFromName(devid, kind)
        datalist = list()
        for dim in 'xyz':
            chname = kind[0] + dim  # e.g. 'Fx'
            chid = vicon.GetDeviceChannelIDFromName(devid, outputid, chname)
            data, chready, chrate = getter_fun(devid, outputid, chid)
            datalist.append(data)
        alldata[kind] = np.array(datalist).T
    Ftot = np.linalg.norm(alldata['Force'], axis=1)
    cop = alldata['CoP']
    # translation and rotation matrices from local to global coordinates
    wR = np.array(nfp.WorldR).reshape(3, 3)
    wT = np.array(nfp.WorldT)
    # get plate coords, convert to global frame if needed
    cor = np.stack([nfp.LowerBounds, nfp.UpperBounds])
    if coords == 'global':
        cor = _change_coords(cor, wR, wT)
    plate_corners = np.array(
        [
            cor[0, :],
            [cor[0, 0], cor[1, 1], cor[0, 2]],
            cor[1, :],
            [cor[1, 0], cor[0, 1], cor[0, 2]],
        ]
    )
    lb = np.min(cor, axis=0)
    ub = np.max(cor, axis=0)
    # check that CoP stays inside plate boundaries
    cop_ok = np.logical_and(cop[:, 0] >= lb[0], cop[:, 0] <= ub[0]).all()
    cop_ok &= np.logical_and(cop[:, 1] >= lb[1], cop[:, 1] <= ub[1]).all()
    if not cop_ok:
        logger.warning('center of pressure outside plate boundaries, clipping to plate')
        cop[:, 0] = np.clip(cop[:, 0], lb[0], ub[0])
        cop[:, 1] = np.clip(cop[:, 1], lb[1], ub[1])
    return {
        'F': alldata['Force'],
        'M': alldata['Moment'],
        'Ftot': Ftot,
        'CoP': cop,
        'wR': wR,
        'wT': wT,
        'plate_corners': plate_corners,
    }


def _get_forceplate_data(vicon):
    """Read data of all forceplates from Nexus.

    See read_data.get_forceplate_data() for details.
    """
    # get forceplate ids
    logger.debug('reading forceplate data from Vicon Nexus')
    devids = _get_forceplate_ids(vicon)
    if not devids:
        logger.debug('no forceplates detected')
        return None
    logger.debug('detected %d forceplate(s)' % len(devids))
    # filter by device names, if they are configured
    if cfg.autoproc.nexus_forceplate_devnames:
        devids = [
            id
            for id in devids
            if vicon.GetDeviceDetails(id)[0] in cfg.autoproc.nexus_forceplate_devnames
        ]
    return [_get_1_forceplate_data(vicon, devid) for devid in devids]


def _swap_markers(vicon, marker1, marker2):
    """Swap trajectories of given two markers in the current trial"""
    subj = get_subjectnames()
    m1 = vicon.GetTrajectory(subj, marker1)
    m2 = vicon.GetTrajectory(subj, marker2)
    vicon.SetTrajectory(subj, marker2, m1[0], m1[1], m1[2], m1[3])
    vicon.SetTrajectory(subj, marker1, m2[0], m2[1], m2[2], m2[3])


def _get_marker_data(vicon, markers, ignore_missing=False):
    """Get position data for specified markers.

    See read_data.get_marker_data for details.
    """
    if not isinstance(markers, list):
        markers = [markers]
    subj = get_subjectnames()
    mkrdata = dict()
    for marker in markers:
        x, y, z, _ = vicon.GetTrajectory(subj, marker)
        if len(x) == 0:
            if ignore_missing:
                logger.warning('Cannot read trajectory %s from Nexus' % marker)
                continue
            else:
                raise GaitDataError(
                    'Cannot read marker trajectory from Nexus: %s' % marker
                )
        mkrdata[marker] = np.array([x, y, z]).transpose()
    return mkrdata


def _get_model_data(vicon, model):
    """Read model output variables (e.g. Plug-in Gait).

    See read_data.get_model_data for details.
    """
    modeldata = dict()
    var_dims = (3, vicon.GetFrameCount())
    subj = get_subjectnames()
    for var in model.read_vars:
        nums, bools = vicon.GetModelOutput(subj, var)
        if nums:
            data = np.squeeze(np.array(nums))
        else:
            logger.info('cannot read variable %s, returning nans' % var)
            data = np.empty(var_dims)
            data[:] = np.nan
        modeldata[var] = data
    return modeldata


def _create_events(vicon, context, strikes, toeoffs):
    """Create foot strike and toeoff events in Nexus"""
    logger.debug('marking events in Nexus')
    side_str = 'Right' if context == 'R' else 'Left'
    subjectname = get_subjectnames()
    for fr in strikes:
        vicon.CreateAnEvent(subjectname, side_str, 'Foot Strike', int(fr + 1), 0)
    for fr in toeoffs:
        vicon.CreateAnEvent(subjectname, side_str, 'Foot Off', int(fr + 1), 0)


def rigid_body_extrapolate(
    vicon,
    ref_trial,
    extrap_trials,
    ref_markers,
    extrap_markers,
    ref_frame=None,
    save_trials=True,
):
    """Extrapolate missing marker positions from one trial to others.

    Rigid body extrapolation: all markers are assumed to be part of a rigid
    cluster. The reference markers (ref_markers) must be present in all trials.
    The markers to be extrapolated (extrap_markers) must be present in the
    reference trial. The relative position of the reference marker cluster is
    computed in the extrapolation trials, and the positions of the missing
    markers are extrapolated based on that.

    Note that the reference trial and extrapolation trial can be the same. In
    that case, set ref_frame to a frame where all the markers are present. The
    other frames will then be extrapolated.

    The extrapolated marker positions are written back into Nexus and
    vicon.SaveTrial() is called to save each trial.

    Parameters
    ----------
    vicon : ViconNexus
        A ViconNexus SDK object.
    ref_trial : str
        Filename of the reference trial. Give the filename without the
        'Trial.enf' extension, e.g. 'my_session\my_trial01'. All markers must be
        present in the reference trial, at least at the frame given by
        ref_frame.
    extrap_trials : list
        The trials on which the extrapolation should be performed.
    ref_markers : list
        The reference markers to extrapolate from.
    extrap_markers : list
        The markers to extrapolate.
    ref_frame : int or None
        The reference frame to use from the reference trial. If not given, defaults to 0.
    save_trials : bool
        Whether to save the extrapolated trials.
    """
    if ref_frame is None:
        ref_frame = 0
    if not isinstance(extrap_trials, list):
        extrap_trials = [extrap_trials]
    # read data from reference trial
    _open_trial(ref_trial)
    allmarkers = ref_markers + extrap_markers
    try:
        mdata_ref = _get_marker_data(vicon, allmarkers)
    except GaitDataError:
        raise GaitDataError('cannot read markers from reference trial %s' % ref_trial)
    mdata_ref_ = np.row_stack(
        [mdata_ref[marker][ref_frame, :] for marker in allmarkers]
    )
    # read reference marker data from extrapolation trials
    for extrap_trial in extrap_trials:
        extrap_coords = defaultdict(list)
        _open_trial(extrap_trial)
        subjname = get_subjectnames()
        try:
            mdata_ref = _get_marker_data(vicon, ref_markers)
        except GaitDataError:
            raise GaitDataError(
                'cannot read markers from extrapolation trial %s' % extrap_trial
            )
        for frame in range(vicon.GetFrameCount()):
            mdata_thisframe = np.row_stack(
                [mdata_ref[marker][frame, :] for marker in ref_markers]
            )
            mdata_extrap = _rigid_body_extrapolate_markers(mdata_ref_, mdata_thisframe)
            for marker, pos in zip(extrap_markers, mdata_extrap):
                extrap_coords[marker].append(pos)
        # write extrapolated data
        for marker, vals in extrap_coords.items():
            vals_x, vals_y, vals_z = np.array(vals).T
            data_exists = [True] * vicon.GetFrameCount()
            vicon.SetTrajectory(
                subjname,
                marker,
                vals_x,
                vals_y,
                vals_z,
                data_exists,
            )
        if save_trials:
            vicon.SaveTrial(cfg.autoproc.nexus_timeout)
