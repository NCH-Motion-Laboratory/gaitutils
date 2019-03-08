# -*- coding: utf-8 -*-
"""

Data readers & processing utils, Nexus specific

@author: Jussi (jnu@iki.fi)
"""

from __future__ import print_function, division
from collections import defaultdict
import sys
import numpy as np
import os.path as op
import psutil
import glob
import logging

from .numutils import change_coords
from . import GaitDataError, cfg


logger = logging.getLogger(__name__)


def _find_nexus_path(vicon_path):
    """Return path to most recent Nexus version"""

    if vicon_path is None:
        vicon_path = r'C:\Program Files (x86)\Vicon'  # educated guess

    if not op.isdir(vicon_path):
        return None

    nexus_glob = op.join(vicon_path, 'Nexus?.*')
    nexus_dirs = glob.glob(nexus_glob)
    if not nexus_dirs:
        return None
    nexus_vers = [op.split(dir_)[1][5:] for dir_ in nexus_dirs]
    idx = nexus_vers.index(max(nexus_vers))
    return nexus_dirs[idx]


def _add_nexus_path(vicon_path):
    """Add Nexus SDK dir to sys.path"""

    nexus_path = _find_nexus_path(vicon_path)
    if nexus_path is None:
        print('cannot locate Nexus installation directory under %s'
              % vicon_path)
        return

    sdk_path = op.join(nexus_path, 'SDK', 'Python')
    if sdk_path not in sys.path:
        sys.path.append(sdk_path)
    else:
        print('%s already in sys.path' % sdk_path)

    # import from Win32 or Win64 according to bitness of Python interpreter
    bitness = '64' if sys.maxsize > 2**32 else '32'
    win = 'Win' + bitness
    _win_sdk_path = op.join(nexus_path, 'SDK', win)

    # check that the path for the wrong architecture has not already been
    # added to path (this may happen when running inside Nexus)
    win_other = 'Win32' if win == 'Win64' else 'Win64'
    _win_sdk_other = op.join(nexus_path, 'SDK', win_other)
    if _win_sdk_other in sys.path:
        print('%s already in sys.path, removing' % _win_sdk_other)
        sys.path.remove(_win_sdk_other)

    if _win_sdk_path not in sys.path:
        print('using Nexus SDK from %s' % _win_sdk_path)
        sys.path.append(_win_sdk_path)
    else:
        print('%s already in sys.path' % _win_sdk_path)


if sys.version_info.major >= 3:
    print('running on Python 3 or newer, cannot import Nexus API (yet)')
else:
    vicon_path = op.normpath(cfg.general.vicon_path)
    _add_nexus_path(vicon_path)
    try:
        import ViconNexus
    except ImportError:
        print('cannot import Vicon Nexus SDK')

sys.stdout.flush()  # make sure import warnings get printed


def pid():
    """ Tries to return the PID of the running Nexus process. """
    PROCNAME = "Nexus.exe"
    for proc in psutil.process_iter():
        try:
            if proc.name() == PROCNAME:
                return proc.pid
        # catch NoSuchProcess for procs that disappear inside loop
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            pass
    return None


def true_ver():
    """ Tries to return the actual version of the running Nexus process
    (API does not do that). Hackish and probably unreliable """
    PROCNAME = "Nexus.exe"
    for proc in psutil.process_iter():
        try:
            if proc.name() == PROCNAME:
                exname = proc.exe()
                vind = exname.find('2.')  # assumes ver >2.
                if vind == -1:
                    return None
                try:
                    return float(exname[vind:vind+3])
                except ValueError:
                    return None
        except psutil.AccessDenied:
            pass
    return None


def viconnexus():
    """ Return a ViconNexus instance. """
    check_nexus()
    return ViconNexus.ViconNexus()


def get_subjectnames(single_only=True):
    """ Get subject name(s) from Nexus """
    vicon = viconnexus()
    get_sessionpath()  # check whether we can get data
    names_ = vicon.GetSubjectNames()
    if not names_:
        raise GaitDataError('No subject defined in Nexus')
    if single_only:
        if len(names_) > 1:
            raise GaitDataError('Nexus returns multiple subjects')
    """ Workaround a Nexus 2.6 bug (?) that creates extra names with
    weird unicode strings """
    names_ = [name for name in names_ if u'\ufffd1' not in name]
    return names_[0] if single_only else names_


def check_nexus():
    if not pid():
        raise GaitDataError('Vicon Nexus does not seem to be running')


def get_sessionpath():
    """ Get path to current session """
    try:
        vicon = viconnexus()
        sessionpath = vicon.GetTrialName()[0]
    except IOError:  # may be raised if Nexus was just terminated
        sessionpath = None
    if not sessionpath:
        raise GaitDataError('Cannot get Nexus session path, '
                            'no session or maybe in Live mode?')
    return op.normpath(sessionpath)


def run_pipelines(vicon, plines):
    """Run given Nexus pipeline(s)"""
    if type(plines) != list:
        plines = [plines]
    for pipeline in plines:
        logger.debug('running pipeline: %s' % pipeline)
        result = vicon.Client.RunPipeline(pipeline.encode('utf-8'), '',
                                          cfg.autoproc.nexus_timeout)
        if result.Error():
            logger.warning('error while trying to run Nexus pipeline: %s'
                           % pipeline)


def get_trialname():
    """ Get trial name without session path """
    vicon = viconnexus()
    trialname_ = vicon.GetTrialName()
    return trialname_[1]


def is_vicon_instance(obj):
    """ Check if obj is an instance of ViconNexus """
    return obj.__class__.__name__ == 'ViconNexus'


def _get_nexus_subject_param(vicon, name, param):
    """Get subject parameter from Nexus."""
    value = vicon.GetSubjectParam(name, param)
    # for unknown reasons, above method may return tuple or float
    # depending on whether script is run from Nexus or outside
    if type(value) == tuple:
        value = value[0] if value[1] else None
    return value


def _get_marker_names(vicon, trajs_only=True):
    """Return marker names (only ones with trajectories, if trajs_only)"""
    subjname = get_subjectnames()
    markers = vicon.GetMarkerNames(subjname)
    # only get markers with trajectories - excludes calibration markers
    if trajs_only:
        markers = [mkr for mkr in markers if vicon.HasTrajectory(subjname,
                                                                 mkr)]
    return markers


# FIXME: most of get_ methods below are intended to be called via read_data
# so underscore them
def get_metadata(vicon):
    """ Read trial and subject metadata """
    check_nexus()
    logger.debug('reading metadata from Vicon Nexus')
    subjname = get_subjectnames()
    params_available = vicon.GetSubjectParamNames(subjname)
    subj_params = defaultdict(lambda: None)
    subj_params.update({par: _get_nexus_subject_param(vicon, subjname, par) for
                        par in params_available})
    trialname = get_trialname()
    if not trialname:
        raise GaitDataError('No trial loaded in Nexus')
    sessionpath = get_sessionpath()
    markers = _get_marker_names(vicon)
    # get events - GetEvents() indices seem to often be 1 frame less than on
    # Nexus display - only happens with ROI?
    lstrikes = vicon.GetEvents(subjname, "Left", "Foot Strike")[0]
    rstrikes = vicon.GetEvents(subjname, "Right", "Foot Strike")[0]
    ltoeoffs = vicon.GetEvents(subjname, "Left", "Foot Off")[0]
    rtoeoffs = vicon.GetEvents(subjname, "Right", "Foot Off")[0]
    # Offset will be subtracted from event frame numbers to get correct
    # 0-based index for frame data. For Nexus, it is always 1 (Nexus uses
    # 1-based frame numbering)
    offset = 1
    length = vicon.GetFrameCount()
    framerate = vicon.GetFrameRate()
    # Get analog rate. This may not be mandatory if analog devices
    # are not used, but currently it needs to succeed.
    devids = vicon.GetDeviceIDs()
    if not devids:
        raise GaitDataError('Cannot determine analog rate')
    else:
        devid = devids[0]
        _, _, analograte, _, _, _ = vicon.GetDeviceDetails(devid)
    samplesperframe = analograte / framerate
    logger.debug('offset @ %d, %d frames, framerate %d Hz, %d samples per '
                 'frame' % (offset, length, framerate, samplesperframe))
    # get n of forceplates
    fp_devids = [id_ for id_ in devids if
                 vicon.GetDeviceDetails(id_)[1].lower() == 'forceplate']

    # sort events (may be in wrong temporal order, at least in c3d files)
    for li in [lstrikes, rstrikes, ltoeoffs, rtoeoffs]:
        li.sort()

    return {'trialname': trialname, 'sessionpath': sessionpath,
            'offset': offset, 'framerate': framerate, 'analograte': analograte,
            'name': subjname, 'subj_params': subj_params, 'lstrikes': lstrikes,
            'rstrikes': rstrikes, 'ltoeoffs': ltoeoffs, 'rtoeoffs': rtoeoffs,
            'length': length, 'samplesperframe': samplesperframe,
            'n_forceplates': len(fp_devids), 'markers': markers}


def get_emg_data(vicon):
    """ Read EMG data from Nexus. This uses the configured EMG device name. """
    return _get_analog_data(vicon, cfg.emg.devname)


def get_accelerometer_data(vicon):
    """ Read EMG data from Nexus. This uses the configured EMG device name. """
    return _get_analog_data(vicon, cfg.analog.accelerometer_devname)


def _get_analog_data(vicon, devname):
    """ Read analog data from Nexus """
    ids = [id_ for id_ in vicon.GetDeviceIDs() if
           vicon.GetDeviceDetails(id_)[0].lower() == devname.lower()]
    if len(ids) > 1:
        raise GaitDataError('Multiple matching analog devices')
    elif len(ids) == 0:
        raise GaitDataError('No matching analog devices')
    dev_id = ids[0]
    dname, dtype, drate, outputids, _, _ = vicon.GetDeviceDetails(dev_id)
    # not handling multiple output ids yet
    if len(outputids) != 1:
        raise GaitDataError('Expected single output for device')
    outputid = outputids[0]
    # get list of channel names and IDs
    _, _, _, _, chnames, chids = vicon.GetDeviceOutputDetails(dev_id, outputid)
    data = dict()
    for chid in chids:
        chdata, _, chrate = vicon.GetDeviceChannel(dev_id, outputid, chid)
        chname = chnames[chid-1]  # chids start from 1
        data[chname] = np.array(chdata)
    return {'t': np.arange(len(chdata)) / drate, 'data': data}


def _get_1_forceplate_data(vicon, devid):
    """ Read data of single forceplate from Nexus.
    Data is returned in global coordinate frame """
    # get forceplate ids
    logger.debug('reading forceplate data from devid %d' % devid)
    dname, dtype, drate, outputids, nfp, _ = vicon.GetDeviceDetails(devid)
    # outputs should be force, moment, cop. select force
    outputid = outputids[0]
    chid = vicon.GetDeviceChannelIDFromName(devid, outputid, 'Fx')
    fx, chready, chrate = vicon.GetDeviceChannelGlobal(devid, outputid, chid)
    chid = vicon.GetDeviceChannelIDFromName(devid, outputid, 'Fy')
    fy, chready, chrate = vicon.GetDeviceChannelGlobal(devid, outputid, chid)
    chid = vicon.GetDeviceChannelIDFromName(devid, outputid, 'Fz')
    fz, chready, chrate = vicon.GetDeviceChannelGlobal(devid, outputid, chid)
    # moments
    outputid = outputids[1]
    chid = vicon.GetDeviceChannelIDFromName(devid, outputid, 'Mx')
    mx, chready, chrate = vicon.GetDeviceChannelGlobal(devid, outputid, chid)
    chid = vicon.GetDeviceChannelIDFromName(devid, outputid, 'My')
    my, chready, chrate = vicon.GetDeviceChannelGlobal(devid, outputid, chid)
    chid = vicon.GetDeviceChannelIDFromName(devid, outputid, 'Mz')
    mz, chready, chrate = vicon.GetDeviceChannelGlobal(devid, outputid, chid)
    # center of pressure
    outputid = outputids[2]
    chid = vicon.GetDeviceChannelIDFromName(devid, outputid, 'Cx')
    copx, chready, chrate = vicon.GetDeviceChannelGlobal(devid, outputid, chid)
    chid = vicon.GetDeviceChannelIDFromName(devid, outputid, 'Cy')
    copy, chready, chrate = vicon.GetDeviceChannelGlobal(devid, outputid, chid)
    chid = vicon.GetDeviceChannelIDFromName(devid, outputid, 'Cz')
    copz, chready, chrate = vicon.GetDeviceChannelGlobal(devid, outputid, chid)
    cop_w = np.array([copx, copy, copz]).transpose()
    F = np.array([fx, fy, fz]).transpose()
    M = np.array([mx, my, mz]).transpose()
    Ftot = np.linalg.norm(F, axis=1)
    # translation and rotation matrices -> world coords
    # suspect that Nexus wR is wrong (does not match displayed plate axes)?
    wR = np.array(nfp.WorldR).reshape(3, 3)
    wT = np.array(nfp.WorldT)
    # plate corners -> world coords
    cor = np.stack([nfp.LowerBounds, nfp.UpperBounds])
    cor_w = change_coords(cor, wR, wT)
    cor_full = np.array([cor_w[0, :],
                        [cor_w[0, 0], cor_w[1, 1], cor_w[0, 2]],
                        cor_w[1, :],
                        [cor_w[1, 0], cor_w[0, 1], cor_w[0, 2]]])

    lb = np.min(cor_w, axis=0)
    ub = np.max(cor_w, axis=0)
    # check that CoP stays inside plate boundaries
    cop_ok = np.logical_and(cop_w[:, 0] >= lb[0], cop_w[:, 0] <= ub[0]).all()
    cop_ok &= np.logical_and(cop_w[:, 1] >= lb[1], cop_w[:, 1] <= ub[1]).all()
    if not cop_ok:
        logger.warning('center of pressure outside plate boundaries, '
                       'clipping to plate')
        cop_w[:, 0] = np.clip(cop_w[:, 0], lb[0], ub[0])
        cop_w[:, 1] = np.clip(cop_w[:, 1], lb[1], ub[1])
    return {'F': F, 'M': M, 'Ftot': Ftot, 'CoP': cop_w,
            'wR': wR, 'wT': wT, 'lowerbounds': lb, 'upperbounds': ub,
            'cor_w': cor_w, 'cor_full': cor_full}


def get_forceplate_data(vicon):
    """ Read all forceplate data from Nexus. """
    # get forceplate ids
    logger.debug('reading forceplate data from Vicon Nexus')
    devids = [id_ for id_ in vicon.GetDeviceIDs() if
              vicon.GetDeviceDetails(id_)[1].lower() == 'forceplate']
    if len(devids) == 0:
        logger.debug('no forceplates detected')
        return None
    logger.debug('detected %d forceplate(s)' % len(devids))
    return [_get_1_forceplate_data(vicon, devid) for devid in devids]


def _swap_markers(vicon, marker1, marker2):
    """Swap two marker trajectories in currently loaded trial."""
    subj = get_subjectnames()
    m1 = vicon.GetTrajectory(subj, marker1)
    m2 = vicon.GetTrajectory(subj, marker2)
    vicon.SetTrajectory(subj, marker2, m1[0], m1[1], m1[2], m1[3])
    vicon.SetTrajectory(subj, marker1, m2[0], m2[1], m2[2], m2[3])


def _get_marker_data(vicon, markers, ignore_edge_gaps=True,
                     ignore_missing=False):
    """Get position, velocity and acceleration for specified markers."""
    if not isinstance(markers, list):
        markers = [markers]
    subj = get_subjectnames()
    mkrdata = dict()
    for marker in markers:
        x, y, z, _ = vicon.GetTrajectory(subj, marker)
        if len(x) == 0:
            if ignore_missing:
                logger.warning('Cannot read trajectory %s from Nexus'
                               % marker)
                continue
            else:
                raise GaitDataError('Cannot read marker trajectory '
                                    'from Nexus: \'%s\'' % marker)
        mP = np.array([x, y, z]).transpose()
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


def get_roi(vicon):
    """ Return array of frames corresponding to Nexus ROI """
    roi = vicon.GetTrialRegionOfInterest()
    return np.arange(roi[0], roi[1])


def get_model_data(vicon, model):
    """ Read model output variables (e.g. Plug-in Gait) """
    modeldata = dict()
    var_dims = (3, vicon.GetFrameCount())
    subj = get_subjectnames()
    for var in model.read_vars:
        nums, bools = vicon.GetModelOutput(subj, var)
        if nums:
            data = np.squeeze(np.array(nums))
        else:
            if model.is_optional_var(var):
                logger.info('cannot read optional variable %s, returning nans'
                            % var)
                data = np.empty(var_dims)
                data[:] = np.nan
            else:
                raise GaitDataError('Cannot read model variable %s. Make sure '
                                    'that the appropriate model has been run.'
                                    % var)
        modeldata[var] = data
    return modeldata


def create_events(vicon, context, strikes, toeoffs):
    """ Create foot strike and toeoff events in Nexus. """
    logger.debug('marking events in Nexus')
    side_str = 'Right' if context == 'R' else 'Left'
    subjectname = get_subjectnames()
    for fr in strikes:
        vicon.CreateAnEvent(subjectname, side_str, 'Foot Strike',
                            int(fr+1), 0)
    for fr in toeoffs:
        vicon.CreateAnEvent(subjectname, side_str, 'Foot Off',
                            int(fr+1), 0)
