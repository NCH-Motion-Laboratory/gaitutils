# -*- coding: utf-8 -*-
"""

Data readers & processing utils, Nexus specific

@author: Jussi (jnu@iki.fi)
"""

from __future__ import print_function, division
import sys
import numpy as np
from scipy import signal
import os.path as op
import psutil
import glob
import matplotlib.pyplot as plt
import logging

from .numutils import (rising_zerocross, best_match, falling_zerocross,
                       change_coords)
from . import utils
from .envutils import GaitDataError

from .config import cfg


logger = logging.getLogger(__name__)

# handle Nexus SDK import
nexus_path = op.normpath(cfg.general.nexus_path)
if nexus_path:
    # see if there are more recent versions than the configured one
    try:
        cfg_ver = float(op.split(nexus_path)[1][5:])
    except ValueError:
        cfg_ver = 0
    if cfg_ver > 2:
        vicondir = op.split(nexus_path)[0]
        nexus_glob = op.join(vicondir, 'Nexus2*')
        nexus_dirs = glob.glob(nexus_glob)
        if len(nexus_dirs) > 1:
            nexus_vers = [op.split(dir_)[1][5:] for dir_ in nexus_dirs]
            if any([float(ver) > cfg_ver for ver in nexus_vers]):
                print('NOTE: you may have more recent Vicon Nexus versions '
                      'installed than is specified in config. It is '
                      'recommended to edit .gaitutils.cfg in your '
                      'home directory and change cfg.general.nexus_path '
                      'to the latest version')

    if op.isdir(nexus_path):
        # we need to have SDK/Python and SDK/Win64 or SDK/Win32 on sys.path
        # if running from inside Nexus, these may be already added
        sdk_path = op.join(nexus_path, 'SDK', 'Python')
        if sdk_path not in sys.path:
            sys.path.append(sdk_path)
        else:
            print('%s already in sys.path' % sdk_path)

        # import Win32 or Win64 according to bitness of Python interpreter
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
            sys.path.append(_win_sdk_path)
        else:
            print('%s already in sys.path' % _win_sdk_path)

        print('importing Vicon Nexus SDK from %s' % _win_sdk_path)

    else:
        print('The configured Vicon Nexus directory at %s does not exist'
              % nexus_path)

try:
    import ViconNexus
except ImportError:
    # logging handlers are not installed at this point, so use print
    print('Cannot import Vicon Nexus SDK, unable to communicate with Nexus')

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
    vicon = viconnexus()
    sessionpath = vicon.GetTrialName()[0]
    if not sessionpath:
        raise GaitDataError('Cannot get Nexus session path, '
                            'no session or maybe in Live mode?')
    return op.normpath(sessionpath)


def get_trialname():
    """ Get trial name without session path """
    vicon = viconnexus()
    trialname_ = vicon.GetTrialName()
    return trialname_[1]


def find_trial_videos(fname, ext='avi', camera_id=None):
    """ Finds Nexus video files for trial file (e.g. x1d or c3d) """
    trialbase = op.splitext(fname)[0]
    vids = glob.glob(trialbase + '*' + ext)
    if camera_id is not None:
        vids = [vid for vid in vids if _camera_id(vid) == camera_id]
    return vids


def _camera_id(fname):
    """ Returns camera id for a video file """
    fn_split = op.split(fname)[-1].split('.')
    if len(fn_split) < 3:
        raise ValueError('Unexpected video file name %s' % fname)
    return fn_split[-3]


def is_vicon_instance(obj):
    """ Check if obj is an instance of ViconNexus """
    return obj.__class__.__name__ == 'ViconNexus'


# FIXME: most of get_ methods below are intended to be called via read_data
# so underscore them

def get_metadata(vicon):
    """ Read trial and subject metadata """
    check_nexus()
    logger.debug('reading metadata from Vicon Nexus')
    name = get_subjectnames()
    bodymass = vicon.GetSubjectParam(name, 'Bodymass')
    # for unknown reasons, above method may return tuple or float
    # depending on whether script is run from Nexus or outside
    if type(bodymass) == tuple:
        bodymass = vicon.GetSubjectParam(name, 'Bodymass')[0]
    else:  # hopefully float
        bodymass = vicon.GetSubjectParam(name, 'Bodymass')
    if bodymass <= 0:
        logger.warn('invalid or unspecified body mass: %.2f', bodymass)
        bodymass = None
    trialname = get_trialname()
    if not trialname:
        raise GaitDataError('No trial loaded in Nexus')
    sessionpath = get_sessionpath()
    markers = vicon.GetMarkerNames(name)
    # get events - GetEvents() indices seem to often be 1 frame less than on
    # Nexus display - only happens with ROI?
    lstrikes = vicon.GetEvents(name, "Left", "Foot Strike")[0]
    rstrikes = vicon.GetEvents(name, "Right", "Foot Strike")[0]
    ltoeoffs = vicon.GetEvents(name, "Left", "Foot Off")[0]
    rtoeoffs = vicon.GetEvents(name, "Right", "Foot Off")[0]
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
            'name': name, 'bodymass': bodymass, 'lstrikes': lstrikes,
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
            'cor_w': cor_w}


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
    data = []
    for devid in devids:
        data.append(_get_1_forceplate_data(vicon, devid))
    return data


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
                logger.warning('Cannot read trajectory %s from c3d file'
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
    subj = get_subjectnames()
    for var in model.read_vars:
        nums, bools = vicon.GetModelOutput(subj, var)
        if not nums:
            raise GaitDataError('Cannot read model variable %s. Make sure '
                                'that the appropriate model has been run.'
                                % var)
        # remove singleton dimensions
        modeldata[var] = np.squeeze(np.array(nums))
    return modeldata


def _list_to_str(li):
    """ Convenience for displaying lists """
    return ','.join([str(it) for it in li])


def automark_events(vicon, mkrdata=None, events_range=None, fp_events=None,
                    vel_thresholds=None, restrict_to_roi=False,
                    start_on_forceplate=False, plot=False, mark=True):

    """ Mark events based on velocity thresholding. Absolute thresholds
    can be specified as arguments. Otherwise, relative thresholds will be
    calculated based on the data. Optimal results will be obtained when
    thresholds based on force plate data are available.

    If mkrdata is None, it will be read from Nexus. Otherwise mkrdata must
    include both foot markers and the body tracking markers (see config)

    vel_thresholds gives velocity thresholds for identifying events. These
    can be obtained from forceplate data (utils.check_forceplate_contact).
    Separate thresholds for left and right side.

    fp_events is dict specifying the forceplate detected strikes and toeoffs
    (see utils.detect_forceplate_events). These will not be marked by
    velocity thresholding.

    If events_range is specified, the events will be restricted to given
    coordinate range in the principal gait direction.
    E.g. events_range=[-1000, 1000]

    If start_on_forceplate is True, the first cycle will start on forceplate
    (i.e. events earlier than the first foot strike events in fp_events will
    not be marked for the corresponding side(s)).

    If plot=True, velocity curves and events are plotted.

    If mark=False, no events will actually be marked in Nexus.

    Before automark, run reconstruct, label, gap fill and filter pipelines.
    Filtering is important to get reasonably smooth derivatives.
    """

    frate = vicon.GetFrameRate()
    if not frate:
        raise GaitDataError('Cannot get framerate from Nexus')

    # TODO: move into config
    # thresholds (relative to maximum velocity) for detecting strike/toeoff
    REL_THRESHOLD_FALL = .2
    REL_THRESHOLD_RISE = .5
    # marker data is assumed to be in mm
    # mm/frame = 1000 m/frame = 1000/frate m/s
    VEL_CONV = 1000/frate
    # reasonable limit for peak velocity (m/s before multiplier)
    MAX_PEAK_VELOCITY = 12 * VEL_CONV
    # reasonable limits for velocity on slope (increasing/decreasing)
    MAX_SLOPE_VELOCITY = 6 * VEL_CONV
    MIN_SLOPE_VELOCITY = 0  # not currently in use
    # minimum swing velocity (rel to max velocity)
    MIN_SWING_VELOCITY = .5
    # median prefilter width
    PREFILTER_MEDIAN_WIDTH = 3
    # tolerance for matching forceplate and vel. thresholded events
    FP_EVENT_TOL = 10

    subjectname = get_subjectnames()

    vel_thresholds = {'L_strike': None, 'L_toeoff': None,
                      'R_strike': None, 'R_toeoff': None}

    # get foot center positions and velocities
    if mkrdata is None:
        mkrdata = _get_marker_data(vicon, cfg.autoproc.right_foot_markers +
                                   cfg.autoproc.left_foot_markers +
                                   cfg.autoproc.track_markers)
    rfootctrv_ = utils.avg_markerdata(mkrdata, cfg.autoproc.right_foot_markers,
                                      var_type='_V')
    rfootctrv = np.linalg.norm(rfootctrv_, axis=1)
    lfootctrv_ = utils.avg_markerdata(mkrdata, cfg.autoproc.left_foot_markers,
                                      var_type='_V')
    lfootctrv = np.linalg.norm(lfootctrv_, axis=1)
    # position data: use ANK marker
    rfootctrP = mkrdata['RANK']
    lfootctrP = mkrdata['LANK']

    strikes_all = {}
    toeoffs_all = {}

    # loop: same operations for left / right foot
    for context, footctrP, footctrv in zip(('R', 'L'), (rfootctrP, lfootctrP),
                                           (rfootctrv, lfootctrv)):
        logger.debug('marking side %s' % context)
        # foot center position
        # filter scalar velocity data to suppress noise and spikes
        footctrv = signal.medfilt(footctrv, PREFILTER_MEDIAN_WIDTH)
        # get peak (swing) velocity
        maxv = utils._get_foot_swing_velocity(footctrv, MAX_PEAK_VELOCITY,
                                              MIN_SWING_VELOCITY)

        # compute thresholds
        threshold_fall_ = (vel_thresholds[context+'_strike'] or
                           maxv * REL_THRESHOLD_FALL)
        threshold_rise_ = (vel_thresholds[context+'_toeoff'] or
                           maxv * REL_THRESHOLD_RISE)
        logger.debug('side: %s, default thresholds fall/rise: %.2f/%.2f'
                     % (context, maxv * REL_THRESHOLD_FALL,
                        maxv * REL_THRESHOLD_RISE))
        logger.debug('using thresholds: %.2f/%.2f' % (threshold_fall_,
                                                      threshold_rise_))
        # find point where velocity crosses threshold
        # foot strikes (velocity decreases)
        cross = falling_zerocross(footctrv - threshold_fall_)
        # exclude edges of data vector
        fmax = len(footctrv) - 1
        cross = cross[np.where(np.logical_and(cross > 0, cross < fmax))]
        # check velocity on slope
        cind_min = np.logical_and(footctrv[cross-1] < MAX_SLOPE_VELOCITY,
                                  footctrv[cross-1] > MIN_SLOPE_VELOCITY)
        cind_max = np.logical_and(footctrv[cross+1] < MAX_SLOPE_VELOCITY,
                                  footctrv[cross+1] > MIN_SLOPE_VELOCITY)
        strikes = cross[np.logical_and(cind_min, cind_max)]

        # check for foot swing (velocity maximum) between consecutive strikes
        # if no swing, keep deleting the latter event until swing is found
        bad = []
        for sind in range(len(strikes)):
            if sind in bad:
                continue
            for sind2 in range(sind+1, len(strikes)):
                swing_max_vel = footctrv[strikes[sind]:strikes[sind2]].max()
                # logger.debug('check %d-%d' % (strikes[sind], strikes[sind2]))
                if swing_max_vel < maxv * MIN_SWING_VELOCITY:
                    logger.debug('no swing between strikes %d-%d, deleting %d'
                                 % (strikes[sind], strikes[sind2],
                                    strikes[sind2]))
                    bad.append(sind2)
                else:
                    break
        strikes = np.delete(strikes, bad)

        if len(strikes) == 0:
            raise GaitDataError('No valid foot strikes detected')

        # toe offs (velocity increases)
        cross = rising_zerocross(footctrv - threshold_rise_)
        cross = cross[np.where(np.logical_and(cross > 0,
                                              cross < len(footctrv)))]
        cind_min = np.logical_and(footctrv[cross-1] < MAX_SLOPE_VELOCITY,
                                  footctrv[cross-1] > MIN_SLOPE_VELOCITY)
        cind_max = np.logical_and(footctrv[cross+1] < MAX_SLOPE_VELOCITY,
                                  footctrv[cross+1] > MIN_SLOPE_VELOCITY)
        toeoffs = cross[np.logical_and(cind_min, cind_max)]

        if len(toeoffs) == 0:
            raise GaitDataError('Could not detect any toe-off events')

        # check for multiple toeoffs
        for s1, s2 in zip(strikes, np.roll(strikes, -1))[:-1]:
            to_this = np.where(np.logical_and(toeoffs > s1, toeoffs < s2))[0]
            if len(to_this) > 1:
                logger.debug('%d toeoffs during cycle, keeping the last one'
                             % len(to_this))
                toeoffs = np.delete(toeoffs, to_this[:-1])

        logger.debug('autodetected strike events: %s' % _list_to_str(strikes))
        logger.debug('autodetected toeoff events: %s' % _list_to_str(toeoffs))

        # select events for which the foot is close enough to center frame
        if events_range:
            mP = mkrdata[cfg.autoproc.track_markers[0]]
            fwd_dim = utils.principal_movement_direction(mP)
            strike_pos = footctrP[strikes, fwd_dim]
            dist_ok = np.logical_and(strike_pos > events_range[0],
                                     strike_pos < events_range[1])
            # exactly zero position at strike should indicate a gap -> exclude
            # TODO: smarter gap handling
            dist_ok = np.logical_and(dist_ok, strike_pos != 0)
            strikes = strikes[dist_ok]

        # correct foot strikes with force plate autodetected events
        if fp_events[context+'_strikes']:
            fp_strikes = fp_events[context+'_strikes']
            logger.debug('forceplate strikes: %s' % fp_strikes)
            # find best fp matches for all strikes
            fpc = best_match(strikes, fp_strikes)
            ok_ind = np.where(np.abs(fpc - strikes) < FP_EVENT_TOL)[0]
            if ok_ind.size == 0:
                logger.warning('could not match forceplate strike with an '
                               'autodetected strike')
            else:
                # replace with fp detected strikes
                strikes[ok_ind] = fpc[ok_ind]
                logger.debug('fp corrected strikes: %s' % strikes)
            # toeoffs
            fp_toeoffs = fp_events[context+'_toeoffs']
            logger.debug('forceplate toeoffs: %s' % fp_toeoffs)
            fpc = best_match(toeoffs, fp_toeoffs)
            ok_ind = np.where(np.abs(fpc - toeoffs) < FP_EVENT_TOL)[0]
            if ok_ind.size == 0:
                logger.warning('could not match forceplate toeoff with an '
                               'autodetected toeoff')
            else:
                toeoffs[ok_ind] = fpc[ok_ind]
                logger.debug('fp corrected toeoffs: %s' % toeoffs)
            # delete strikes before (actual) 1st forceplate contact
            if start_on_forceplate and len(fp_strikes) > 0:
                # use a tolerance here to avoid deleting possible (uncorrected)
                # strike near the fp
                not_ok = np.where(strikes < fp_strikes[0] - FP_EVENT_TOL)[0]
                if not_ok.size > 0:
                    logger.debug('deleting foot strikes before forceplate: %s'
                                 % strikes[not_ok])
                    strikes = np.delete(strikes, not_ok)

        if restrict_to_roi:
            roi = vicon.GetTrialRegionOfInterest()
            strikes = np.extract(np.logical_and(roi[0] <= strikes+1,
                                                strikes+1 <= roi[1]), strikes)

            toeoffs = np.extract(np.logical_and(roi[0] <= toeoffs+1,
                                                toeoffs+1 <= roi[1]), toeoffs)

        if len(strikes) == 0:
            raise GaitDataError('No valid foot strikes detected')

        # delete toeoffs that are not between strike events
        not_ok = np.where(np.logical_or(toeoffs <= min(strikes),
                                        toeoffs >= max(strikes)))
        toeoffs = np.delete(toeoffs, not_ok)

        logger.debug('final strike events: %s' % _list_to_str(strikes))
        logger.debug('final toeoff events: %s' % _list_to_str(toeoffs))

        # create the events in Vicon Nexus
        # Nexus frame numbers are 1-based so add 1
        logger.debug('marking events in Nexus')
        side_str = 'Right' if context == 'R' else 'Left'
        if mark:
            for fr in strikes:
                vicon.CreateAnEvent(subjectname, side_str, 'Foot Strike',
                                    int(fr+1), 0)
            for fr in toeoffs:
                vicon.CreateAnEvent(subjectname, side_str, 'Foot Off',
                                    int(fr+1), 0)
        strikes_all[context] = strikes
        toeoffs_all[context] = toeoffs

        # plot velocities w/ thresholds and marked events
        if plot:
            first_call = context == 'R'
            if first_call:
                f, (ax1, ax2) = plt.subplots(2, 1)
            ax = ax1 if first_call else ax2
            ax.plot(footctrv, 'g', label='foot center velocity ' + context)
            # algorithm, fixed thresholds
            ax.plot(strikes, footctrv[strikes], 'kD', markersize=10,
                    label='strike')
            ax.plot(toeoffs, footctrv[toeoffs], 'k^', markersize=10,
                    label='toeoff')
            ax.legend(numpoints=1, fontsize=10)
            ax.set_ylim(0, maxv+10)
            if not first_call:
                plt.xlabel('Frame')
            ax.set_ylabel('Velocity (mm/frame)')
            ax.set_title('Left' if context == 'L' else 'Right')

    if plot:
        plt.show()

    return (strikes_all['R'], strikes_all['L'], toeoffs_all['R'],
            toeoffs_all['L'])
