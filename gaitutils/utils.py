# -*- coding: utf-8 -*-
"""

Utility functions for processing gait data.

@author: Jussi (jnu@iki.fi)
"""

from __future__ import division

from builtins import str
from builtins import zip
from scipy import signal
from matplotlib import path
import matplotlib.pyplot as plt
import numpy as np
import logging

from .envutils import GaitDataError
from .numutils import (rising_zerocross, best_match, falling_zerocross,
                       _baseline)
from .config import cfg

logger = logging.getLogger(__name__)


def get_crossing_frame(mP, dim=1, p0=0):
    """ Return frame(s) where marker position (dimension dim) crosses p0
    (units are as returned by Nexus, usually mm).
    Dims are x=0, y=1, z=2. """
    y = mP[:, dim]
    nzind = np.where(y != 0)  # nonzero elements == valid data (not nice)
    y[nzind] -= p0
    zx = np.append(rising_zerocross(y), falling_zerocross(y))
    ycross = list()
    # sanity checks
    for p in zx:
        # y must be nonzero on either side of crossing (valid data)
        if p-10 > 0 and p+10 < len(y):
            if y[p-10] != 0 and y[p+10] != 0:
                # y must change sign also around p
                if np.sign(y[p-10]) != np.sign(y[p+10]):
                        ycross.append(p)
    return ycross


def avg_markerdata(mkrdata, markers, var_type='_P', roi=None):
    """ Average marker data.
    """
    data_shape = mkrdata[markers[0]+var_type].shape
    mP = np.zeros(data_shape)
    if roi is None:
        roi = [0, data_shape[0]]
    roi_frames = np.arange(roi[0], roi[1])
    n_ok = 0
    for marker in markers:
        gap_frames = mkrdata[marker+'_gaps']
        if np.intersect1d(roi_frames, gap_frames).size > 0:
            raise GaitDataError('Averaging data for %s has gaps' % marker)
        else:
            mP += mkrdata[marker+var_type]
            n_ok += 1
    else:
        return mP / n_ok


# FIXME: marker sets could be moved into models.py?
def _pig_markerset(fullbody=True, sacr=True):
    """ PiG marker set as dict (empty values) """
    _pig = ['LASI', 'RASI', 'LTHI', 'LKNE', 'LTIB', 'LANK', 'LHEE',
            'LTOE', 'RTHI', 'RKNE', 'RTIB', 'RANK', 'RHEE', 'RTOE']
    if fullbody:
        _pig += ['LFHD', 'RFHD', 'LBHD', 'RBHD', 'C7', 'T10', 'CLAV', 'STRN',
                 'RBAK', 'LSHO', 'LELB', 'LWRA', 'LWRB', 'LFIN', 'RSHO',
                 'RELB', 'RWRA', 'RWRB', 'RFIN']
    # add pelvis posterior markers; SACR or RPSI/LPSI
    _pig.extend(['SACR'] if sacr else ['RPSI', 'LPSI'])
    return {mkr: None for mkr in _pig}


def _pig_pelvis_markers():
    return ['RASI', 'RPSI', 'LASI', 'LPSI', 'SACR']


def is_plugingait_set(mkrdata):
    """ Check whether marker data set corresponds to Plug-in Gait (full body or
    lower body only). Extra markers are accepted. """
    mkrs = set(mkrdata.keys())
    # required markers
    lb_mkrs_sacr = set(_pig_markerset(fullbody=False).keys())
    lb_mkrs_psi = set(_pig_markerset(fullbody=False, sacr=False).keys())
    return lb_mkrs_psi.issubset(mkrs) or lb_mkrs_sacr.issubset(mkrs)


def check_plugingait_set(mkrdata):
    """ Sanity checks for Plug-in Gait marker set """
    is_ok = dict()
    if not is_plugingait_set(mkrdata):
        raise ValueError('Not a Plug-in Gait set')
    # vector orientation checks
    MAX_ANGLE = 90  # max angle to consider vectors 'similarly oriented'
    for side in ['L', 'R']:
        is_ok[side] = True
        # compare HEE-TOE line to pelvis orientation
        ht = _normalize(mkrdata[side+'TOE'] - mkrdata[side+'HEE'])
        if side+'PSI' in mkrdata:
            pa = _normalize(mkrdata[side+'ASI'] - mkrdata[side+'PSI'])
        elif 'SACR' in mkrdata:
            pa = _normalize(mkrdata[side+'ASI'] - mkrdata['SACR'])
        angs = np.arccos(np.sum(ht * pa, axis=1)) / np.pi * 180
        if np.nanmedian(angs) > MAX_ANGLE:
            logger.warning('%sHEE and %sTOE markers probably flipped'
                           % (side, side))
            is_ok[side] = False
    return is_ok['R'] and is_ok['L']


def principal_movement_direction(mP):
    """ Return principal movement direction (dimension of maximum variance) """
    inds_ok = np.where(np.any(mP, axis=1))  # make sure that gaps are ignored
    return np.argmax(np.var(mP[inds_ok], axis=0))


def get_foot_contact_velocity(mkrdata, fp_events, medians=True, roi=None):
    """ Return foot velocities during forceplate strike/toeoff frames.
    fp_events is from detect_forceplate_events()
    If medians=True, return median values. """
    results = dict()
    for context, markers in zip(('R', 'L'), [cfg.autoproc.right_foot_markers,
                                cfg.autoproc.left_foot_markers]):
        footctrv_ = avg_markerdata(mkrdata, markers, var_type='_V', roi=roi)
        footctrv = np.linalg.norm(footctrv_, axis=1)
        strikes = fp_events[context+'_strikes']
        toeoffs = fp_events[context+'_toeoffs']
        results[context + '_strike'] = footctrv[strikes]
        results[context + '_toeoff'] = footctrv[toeoffs]
    if medians:
        results = {key: (np.array([np.median(x)]) if x.size > 0 else x)
                   for key, x in results.items()}
    return results


def _get_foot_swing_velocity(footctrv, max_peak_velocity, min_swing_velocity):
    """Compute foot swing velocity from scalar velocity data (footctrv)"""
    # find maxima of velocity: derivative crosses zero and values ok
    vd = np.gradient(footctrv)
    vdz_ind = falling_zerocross(vd)
    inds = np.where(footctrv[vdz_ind] < max_peak_velocity)[0]
    if len(inds) == 0:
        raise GaitDataError('Cannot find acceptable velocity peaks')
    # delete spurious peaks (where min swing velocity is not attained)
    vs = footctrv[vdz_ind[inds]]
    not_ok = np.where(vs < vs.max() * min_swing_velocity)
    vs = np.delete(vs, not_ok)
    return np.median(vs)


def _normalize(V):
    """Normalize rows of matrix V"""
    Vn = np.linalg.norm(V, axis=1)
    # quietly return all nans for length zero vectors
    with np.errstate(divide='ignore', invalid='ignore'):
        return V / Vn[:, np.newaxis]


def _get_foot_points(mkrdata, context, footlen=None):
    """Estimate points in the xy plane enclosing the foot. Foot is modeled
    as a triangle"""
    # marker data as N x 3 matrices
    heeP = mkrdata[context+'HEE']
    toeP = mkrdata[context+'TOE']
    ankP = mkrdata[context+'ANK']
    # heel - toe vectors
    htV = toeP - heeP
    htVn = _normalize(htV)
    # heel - ankle vectors
    haV = ankP - heeP
    ha_len = np.linalg.norm(haV, axis=1)
    # end point of foot (just beyond 2nd toe)
    if footlen is None:
        # rough estimate based on marker distances
        logger.debug('using estimated foot length')
        footlen = np.median(ha_len) * cfg.autoproc.foot_relative_len
    foot_end = heeP + htVn * footlen
    # projection of HEE-ANK to HEE-TOE line
    ha_htV = htVn * np.sum(haV*htVn, axis=1)[:, np.newaxis]
    # lateral ANK vector (HEE-TOE line to ANK)
    lankV = haV - ha_htV
    # edge points are coplanar with markers but not with the foot
    # lateral foot edge
    lat_edge = foot_end + lankV
    # medial foot edge
    med_edge = foot_end - lankV
    # heel edge (compensate for marked position)
    heel_edge = heeP + htVn * cfg.autoproc.marker_diam/2
    logger.debug('foot length: %.1f mm width: %.1f mm' %
                 (np.nanmedian(np.linalg.norm(heel_edge-foot_end, axis=1)),
                  np.nanmedian(np.linalg.norm(lat_edge-med_edge, axis=1))))
    return {'heel': heel_edge, 'lateral': lat_edge, 'medial': med_edge,
            'toe': foot_end}


def _leading_foot(mkrdata, roi=None):
    """Determine which foot is leading (ahead in the direction of gait).
    Returns n-length list of 'R' or 'L' correspondingly (n = number of
    frames). Gaps are indicated as None. mkrdata must include foot and
    pelvis markers"""
    subj_pos = avg_markerdata(mkrdata, cfg.autoproc.track_markers, roi=roi)
    # FIXME: should not use a single dim here
    gait_dim = principal_movement_direction(subj_pos)
    gait_dir = np.median(np.diff(subj_pos, axis=0), axis=0)[gait_dim]
    lfoot = avg_markerdata(mkrdata, cfg.autoproc.left_foot_markers,
                           roi=roi)[:, gait_dim]
    rfoot = avg_markerdata(mkrdata, cfg.autoproc.right_foot_markers,
                           roi=roi)[:, gait_dim]
    cmpfun = np.greater if gait_dir > 0 else np.less
    return [None if R == 0.0 or L == 0.0 else ('R' if cmpfun(R, L) else 'L')
            for R, L in zip(rfoot, lfoot)]


def _trial_median_velocity(source):
    """Compute median velocity (walking speed) over whole trial by
    differentiation of marker data from track markers. Up/down movement of
    markers may slightly increase speed compared to time-distance values"""
    from . import read_data
    try:
        frate = read_data.get_metadata(source)['framerate']
        mkrdata = read_data.get_marker_data(source, cfg.autoproc.track_markers)
        vel_3 = avg_markerdata(mkrdata, cfg.autoproc.track_markers,
                               var_type='_V')
        vel_ = np.sqrt(np.sum(vel_3**2, 1))  # scalar velocity
    except (GaitDataError, ValueError):
        return np.nan
    vel = np.median(vel_[np.where(vel_)])  # ignore zeros
    return vel * frate / 1000.  # convert to m/s


def _point_in_poly(poly, pt):
    """Point-in-polygon. poly is ordered nx3 array of vertices and P is mx3
    array of points. Returns mx3 array of booleans. 3rd dim is currently
    ignored"""
    p = path.Path(poly[:, :2])
    return p.contains_point(pt)


def detect_forceplate_events(source, mkrdata=None, fp_info=None,
                             roi=None):
    """ Detect frames where valid forceplate strikes and toeoffs occur.
    Uses forceplate data and estimated foot shape.

    If supplied, mkrdata must include foot and pelvis markers. Otherwise
    it will be read.

    If fp_info dict is supplied, no marker-based checks will be done;
    instead the Eclipse forceplate info will be used to determine the foot.
    Eclipse info is written e.g. as {FP1: 'Left'} where plate indices start
    from 1 and the value can be 'Auto', 'Left', 'Right' or 'Invalid'.
    Even if Eclipse info is used, foot strike and toeoff frames must be
    determined from forceplate data.

    If roi is given e.g. [100, 300], all marker data checks will be restricted
    to roi.
    """
    def _foot_plate_check(fpdata, mkrdata, fr0, side, footlen):
        """Helper for foot-plate check. Returns 0, 1, 2 for:
            completely outside plate, partially outside plate, inside plate"""
        allpts = _get_foot_points(mkrdata, side, footlen)
        poly = fpdata['cor_full']
        pts_ok = list()
        for label, pts in allpts.items():
            pt = pts[fr0, :]
            pt_ok = _point_in_poly(poly, pt)
            logger.debug('%s point %son plate' %
                         (label, '' if pt_ok else 'not '))
            pts_ok.append(pt_ok)
        if all(pts_ok):
            return 2
        elif any(pts_ok):
            return 1
        else:
            return 0

    # get subject info
    from . import read_data
    logger.debug('detect forceplate events from %s' % source)
    info = read_data.get_metadata(source)
    fpdata = read_data.get_forceplate_data(source)
    results = dict(R_strikes=[], R_toeoffs=[], L_strikes=[], L_toeoffs=[],
                   valid=set(), R_strikes_plate=[], L_strikes_plate=[],
                   our_fp_info={}, coded='')

    # get marker data and find "forward" direction (by max variance)
    if mkrdata is None:
        mkrs = (cfg.autoproc.right_foot_markers +
                cfg.autoproc.left_foot_markers +
                cfg.autoproc.track_markers)
        mkrdata = read_data.get_marker_data(source, mkrs)

    footlen = info['subj_params']['FootLen']
    rfootlen = info['subj_params']['RFootLen']
    lfootlen = info['subj_params']['LFootLen']
    if footlen is not None:
        logger.debug('(obsolete) single foot length parameter set to %.2f'
                     % footlen)
        rfootlen = lfootlen = footlen
    elif rfootlen is not None and lfootlen is not None:
        logger.debug('foot length parameters set to r=%.2f, l=%.2f' %
                     (rfootlen, lfootlen))
    else:
        logger.debug('foot length parameter not set')
    bodymass = info['subj_params']['Bodymass']

    logger.debug('acquiring gait events')
    events_0 = automark_events(source, mkrdata=mkrdata, mark=False,
                               roi=roi)

    # loop over plates; our internal forceplate index is 0-based
    for plate_ind, fp in enumerate(fpdata):
        logger.debug('analyzing plate %d' % plate_ind)
        # XXX: are we sure that the plate indices always match Eclipse?
        plate = 'FP' + str(plate_ind + 1)  # Eclipse starts from FP1
        if fp_info is not None and plate in fp_info:
            ecl_valid = fp_info[plate]
            detect_foot = False
            logger.debug('using Eclipse forceplate info: %s' % ecl_valid)
            if ecl_valid == 'Right':
                valid = 'R'
            elif ecl_valid == 'Left':
                valid = 'L'
            elif ecl_valid == 'Invalid':
                valid = None
            elif ecl_valid == 'Auto':
                detect_foot = True
            else:
                raise GaitDataError('unexpected Eclipse forceplate field')
        else:
            logger.debug('not using Eclipse forceplate info')
            valid = None
            detect_foot = True

        # identify candidate frames for foot strike
        # FIXME: filter should maybe depend on sampling freq
        force_checks_ok = True
        forcetot = signal.medfilt(fp['Ftot'])
        forcetot = _baseline(forcetot)
        fmax = max(forcetot)
        fmaxind = np.where(forcetot == fmax)[0][0]  # first maximum
        logger.debug('max force: %.2f N at %.2f' % (fmax, fmaxind))

        if bodymass is None:
            f_threshold = cfg.autoproc.forceplate_contact_threshold * fmax
            logger.warning('body mass unknown, thresholding force at %.2f N',
                           f_threshold)
        else:
            logger.debug('body mass %.2f kg' % bodymass)
            f_threshold = (cfg.autoproc.forceplate_contact_threshold *
                           bodymass * 9.81)
            if fmax < cfg.autoproc.forceplate_min_weight * bodymass * 9.81:
                logger.debug('insufficient max. force on plate')
                force_checks_ok = False

        # find indices where force crosses threshold
        try:
            logger.debug('force threshold: %.2f N' % f_threshold)
            friseind = rising_zerocross(forcetot-f_threshold)[0]  # first rise
            ffallind = falling_zerocross(forcetot-f_threshold)[-1]  # last fall
            logger.debug('force rise: %d fall: %d' % (friseind, ffallind))
            # 0-based frame indices (=1 less than Nexus frame index)
            strike_fr = int(np.round(friseind / info['samplesperframe']))
            toeoff_fr = int(np.round(ffallind / info['samplesperframe']))
            logger.debug('strike @ frame %d, toeoff @ %d'
                         % (strike_fr, toeoff_fr))
        except IndexError:
            logger.debug('cannot detect force rise/fall')
            force_checks_ok = False

        if not force_checks_ok:
            valid = None

        # foot marker (or point) checks
        if force_checks_ok and detect_foot:
            logger.debug('using autodetection of foot contact')
            # allows foot to settle for 50 ms after strike
            settle_fr = int(50/1000 * info['framerate'])
            fr0 = strike_fr + settle_fr
            side = _leading_foot(mkrdata, roi=roi)[fr0]
            if side is None:
                raise GaitDataError('cannot determine leading foot from marker'
                                    ' data')
            footlen = rfootlen if side == 'R' else lfootlen
            logger.debug('checking contact for leading foot: %s' % side)
            ok = _foot_plate_check(fp, mkrdata, fr0, side, footlen) == 2
            # check that contralateral foot is not on plate (needs events)
            if ok and events_0 is not None:
                contra_side = 'R' if side == 'L' else 'L'
                contra_strikes = events_0[contra_side+'_strikes']
                contra_strikes_next = contra_strikes[np.where(contra_strikes >
                                                              strike_fr)]
                if contra_strikes_next.size == 0:
                    logger.debug('no following contralateral strike')
                else:
                    fr0 = contra_strikes_next[0] + settle_fr
                    logger.debug('checking next contact for contralateral '
                                 'foot (at frame %d)' % fr0)
                    contra_next_ok = _foot_plate_check(fp, mkrdata, fr0,
                                                       contra_side,
                                                       footlen) == 0
                    ok &= contra_next_ok
                contra_strikes_prev = contra_strikes[np.where(contra_strikes <
                                                              strike_fr)]
                if contra_strikes_prev.size == 0:
                    logger.debug('no previous contralateral strike')
                else:
                    fr0 = contra_strikes_prev[-1] + settle_fr
                    logger.debug('checking previous contact for contralateral '
                                 'foot (at frame %d)' % fr0)
                    contra_prev_ok = _foot_plate_check(fp, mkrdata, fr0,
                                                       contra_side,
                                                       footlen) == 0
                    ok &= contra_prev_ok
            valid = side if ok else None

        if valid:
            logger.debug('plate %d: valid foot strike on %s at frame %d'
                         % (plate_ind, valid, strike_fr))
            results['valid'].add(valid)
            results[valid+'_strikes'].append(strike_fr)
            results[valid+'_toeoffs'].append(toeoff_fr)
            results[valid+'_strikes_plate'].append(plate_ind)
            results['our_fp_info'][plate] = 'Right' if valid == 'R' else 'Left'
            results['coded'] += valid
        else:
            logger.debug('plate %d: no valid foot strike' % plate_ind)
            results['our_fp_info'][plate] = 'Invalid'
            results['coded'] += 'X'

    logger.debug(results)
    return results


def automark_events(source, mkrdata=None, events_range=None, fp_events=None,
                    vel_thresholds=None, roi=None,
                    start_on_forceplate=False, plot=False, mark=True):

    """ Mark events based on velocity thresholding. Absolute thresholds
    can be specified as arguments. Otherwise, relative thresholds will be
    calculated based on the data. Optimal results will be obtained when
    thresholds based on force plate data are precomputed.

    If mkrdata is None, it will be read from source. Otherwise mkrdata must
    include both foot markers and the body tracking markers (see config)

    vel_thresholds gives velocity thresholds for identifying events. These
    can be obtained from forceplate data (utils.check_forceplate_contact).
    Separate thresholds for left and right side.

    fp_events is dict specifying the forceplate detected strikes and toeoffs
    (see utils.detect_forceplate_events). These will be used instead of
    (nearby) autodetected events.

    If events_range is specified, the events will be restricted to given
    coordinate range in the principal gait direction.
    E.g. events_range=[-1000, 1000]
    
    If roi is specified, events will be restricted to roi.

    If start_on_forceplate is True, the first cycle will start on forceplate
    (i.e. events earlier than the first foot strike events in fp_events will
    not be marked for the corresponding side(s)).

    If plot=True, velocity curves and events are plotted.

    If mark=False, no events will actually be marked in Nexus.

    Before automark, run reconstruct, label, gap fill and filter pipelines.
    Filtering is important to get reasonably smooth derivatives.
    """

    from .read_data import get_metadata, get_marker_data
    info = get_metadata(source)
    frate = info['framerate']
    # some operations are Nexus specific and make no sense for c3d source
    from . import nexus

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

    if vel_thresholds is None:
        vel_thresholds = {'L_strike': None, 'L_toeoff': None,
                          'R_strike': None, 'R_toeoff': None}

    if mkrdata is None:
        reqd_markers = (cfg.autoproc.right_foot_markers +
                        cfg.autoproc.left_foot_markers +
                        cfg.autoproc.track_markers)
        mkrdata = get_marker_data(source, reqd_markers)

    rfootctrv_ = avg_markerdata(mkrdata, cfg.autoproc.right_foot_markers,
                                var_type='_V', roi=roi)
    rfootctrv = np.linalg.norm(rfootctrv_, axis=1)
    lfootctrv_ = avg_markerdata(mkrdata, cfg.autoproc.left_foot_markers,
                                var_type='_V', roi=roi)
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
        maxv = _get_foot_swing_velocity(footctrv, MAX_PEAK_VELOCITY,
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
        for s1, s2 in list(zip(strikes, np.roll(strikes, -1)))[:-1]:
            to_this = np.where(np.logical_and(toeoffs > s1, toeoffs < s2))[0]
            if len(to_this) > 1:
                logger.debug('%d toeoffs during cycle, keeping the last one'
                             % len(to_this))
                toeoffs = np.delete(toeoffs, to_this[:-1])

        logger.debug('autodetected strike events: %s' % strikes)
        logger.debug('autodetected toeoff events: %s' % toeoffs)

        # select events for which the foot is close enough to center frame
        if events_range:
            mP = avg_markerdata(mkrdata, cfg.autoproc.track_markers, roi=roi)
            fwd_dim = principal_movement_direction(mP)
            strike_pos = footctrP[strikes, fwd_dim]
            dist_ok = np.logical_and(strike_pos > events_range[0],
                                     strike_pos < events_range[1])
            # exactly zero position at strike should indicate a gap -> exclude
            # TODO: smarter gap handling
            dist_ok = np.logical_and(dist_ok, strike_pos != 0)
            strikes = strikes[dist_ok]

        # correct foot strikes with force plate autodetected events
        if fp_events and fp_events[context+'_strikes']:
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

        if roi is not None:
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

        logger.debug('final strike events: %s' % strikes)
        logger.debug('final toeoff events: %s' % toeoffs)

        if mark:
            if not nexus.is_vicon_instance(source):
                raise ValueError('event marking supported only for Nexus')
            vicon = nexus.viconnexus()
            nexus.create_events(vicon, context, strikes, toeoffs)

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

    return {'R_strikes': strikes_all['R'], 'L_strikes': strikes_all['L'],
            'R_toeoffs': toeoffs_all['R'], 'L_toeoffs': toeoffs_all['L']}
