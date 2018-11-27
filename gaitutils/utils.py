# -*- coding: utf-8 -*-
"""

Utility functions for processing gait data.

@author: Jussi (jnu@iki.fi)
"""

from __future__ import division

from builtins import str
from builtins import zip
from scipy import signal
import numpy as np
import logging

from .envutils import GaitDataError
from .numutils import rising_zerocross, falling_zerocross, _baseline
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


def avg_markerdata(mkrdata, markers, var_type='_P'):
    """ Average marker data for given markers. Markers with gaps are
    ignored."""
    data_shape = mkrdata[markers[0]+var_type].shape
    mP = np.zeros(data_shape)
    n_ok = 0
    for marker in markers:
        if mkrdata[marker+'_gaps'].size > 0:
            logger.debug('averager: skipping marker %s with gaps' % marker)
            continue
        else:
            mP += mkrdata[marker+var_type]
            n_ok += 1
    if n_ok == 0:
        raise GaitDataError('No acceptable markers')
    else:
        return mP / n_ok


def is_plugingait_set(mkrdata):
    """ Check whether marker data set corresponds to Plug-in Gait (full body or
    lower body only) """
    mkrs = set(mkrdata.keys())
    # required markers
    mkrs_pig = set(['RASI', 'LASI', 'LTHI', 'LKNE', 'LTIB', 'LANK', 'LHEE',
                    'LTOE', 'RTHI', 'RKNE', 'RTIB', 'RANK', 'RHEE', 'RTOE'])
    # in addition, accept either RPSI/LPSI or SACR
    pst_pelvis_markers = set(['RPSI', 'LPSI'])
    sacr = set(['SACR'])
    return (mkrs_pig.issubset(mkrs) and (pst_pelvis_markers.issubset(mkrs) or
            sacr.issubset(mkrs)))


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


def butter_filt(data, passband, sfreq, bord=5):
    """ Design a filter and forward-backward filter given data to
    passband, e.g. [1, 40].
    Passband is given in Hz. None for no filtering.
    Implemented as pure lowpass/highpass, if highpass/lowpass freq == 0
    """
    if passband is None:
        return data
    elif len(passband) != 2:
        raise ValueError('Passband must be a vector of length 2')
    passbandn = 2 * np.array(passband) / sfreq
    if passbandn[0] == 0:  # lowpass
        b, a = signal.butter(bord, passbandn[1], btype='lowpass')
    elif passbandn[1] == 0:  # highpass
        b, a = signal.butter(bord, passbandn[1], btype='highpass')
    else:  # bandpass
        b, a = signal.butter(bord, passbandn, btype='bandpass')
    return signal.filtfilt(b, a, data)


def get_foot_contact_velocity(mkrdata, fp_events, medians=True):
    """ Return foot velocities during forceplate strike/toeoff frames.
    fp_events is from detect_forceplate_events()
    If medians=True, return median values. """
    results = dict()
    for context, markers in zip(('R', 'L'), [cfg.autoproc.right_foot_markers,
                                cfg.autoproc.left_foot_markers]):
        footctrv_ = avg_markerdata(mkrdata, markers, var_type='_V')
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
    # estimate for end point of foot (just beyond 2nd toe):
    # heel-toe vector * heel-ankle length * constant
    if footlen is None:
        foot_end = heeP + htVn * np.median(ha_len) * cfg.autoproc.foot_relative_len
    else:
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
    logger.debug('estimated foot length: %.1f mm width %.1f mm' %
                 (np.nanmedian(np.linalg.norm(heel_edge-foot_end, axis=1)),
                  np.nanmedian(np.linalg.norm(lat_edge-med_edge, axis=1))))
    # minima and maxima in xy plane
    # ignore nans in reduce()
    with np.errstate(divide='ignore', invalid='ignore'):
        pmin = np.minimum.reduce([heel_edge, lat_edge, med_edge])
        pmax = np.maximum.reduce([heel_edge, lat_edge, med_edge])
    return pmin, pmax


def _leading_foot(mkrdata):
    """Determine which foot is leading (ahead in the direction of gait).
    Returns n-length list of 'R' or 'L' correspondingly (n = number of
    frames). Gaps are indicated as None. mkrdata must include foot and
    pelvis markers"""
    # rear of pelvis
    if 'SACR' in mkrdata:
        mkr_rear = mkrdata['SACR_P']
    else:
        mkr_rear = avg_markerdata(mkrdata, ['RPSI', 'LPSI'])
    # front of pelvis
    mkr_front = avg_markerdata(mkrdata, ['RASI', 'LASI'])
    pVn = _normalize(mkr_front - mkr_rear)  # vec pelvis -> direction of gait
    lfoot = avg_markerdata(mkrdata, cfg.autoproc.left_foot_markers)
    rfoot = avg_markerdata(mkrdata, cfg.autoproc.right_foot_markers)
    lV = lfoot - mkr_rear
    rV = rfoot - mkr_rear
    lproj = np.sum(lV*pVn, axis=1)
    rproj = np.sum(rV*pVn, axis=1)
    # ugly but the best alternative so far
    return [None if (np.isnan(l) or np.isnan(r)) else ('R' if r >= l else 'L')
            for r, l in zip(rproj, lproj)]


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


def detect_forceplate_events(source, mkrdata=None, fp_info=None):
    """ Detect frames where valid forceplate strikes and toeoffs occur.
    Uses forceplate data and marker positions.

    If supplied, mkrdata must include foot and pelvis markers. Otherwise
    it will be read.

    If fp_info dict is supplied, no marker and COP checks will be done;
    instead the Eclipse forceplate info will be used. Eclipse info is written
    e.g. as {FP1: 'Left'} where plate indices start from 1 and the value can be
    'Auto', 'Left', 'Right' or 'Invalid'. Even if Eclipse info is used, foot
    strike and toeoff frames must be determined from forceplate data.

    Conditions:
    -check max total force, must correspond to subject weight
    -center of pressure must not change too much during contact time
    -foot must be inside plate at strike & toeoff

    Returns dict with keys R_strikes, L_strikes, R_toeoffs, L_toeoffs.
    Dict values are lists of frames where valid forceplate contact occurs.
    """
    # get subject info
    from . import read_data
    logger.debug('detect forceplate events from %s' % source)
    info = read_data.get_metadata(source)
    fpdata = read_data.get_forceplate_data(source)
    results = dict(R_strikes=[], R_toeoffs=[], L_strikes=[], L_toeoffs=[],
                   valid=set(), R_strikes_plate=[], L_strikes_plate=[],
                   our_fp_info={})

    # get marker data and find "forward" direction (by max variance)
    if mkrdata is None:
        mkrs = (cfg.autoproc.right_foot_markers +
                cfg.autoproc.left_foot_markers +
                cfg.autoproc.pelvis_markers)
        mkrdata = read_data.get_marker_data(source, mkrs, ignore_missing=True)

    # FIXME: should get rid of fwd_dir since it implies coord frame orthogonal
    # to forceplates
    mP = avg_markerdata(mkrdata, cfg.autoproc.track_markers)
    fwd_dir = principal_movement_direction(mP)
    logger.debug('gait forward direction seems to be %s' %
                 {0: 'x', 1: 'y', 2: 'z'}[fwd_dir])

    bodymass = info['bodymass']
    footlen = info['footlen']
    if footlen is not None:
        logger.debug('foot length parameter set to %.2f' % footlen)
    else:
        logger.debug('foot length parameter not set')

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
                raise Exception('unexpected Eclipse forceplate field')
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
            # we work with 0-based frame indices (=1 less than Nexus frame index)
            strike_fr = int(np.round(friseind / info['samplesperframe']))
            toeoff_fr = int(np.round(ffallind / info['samplesperframe']))
            logger.debug('strike @ frame %d, toeoff @ %d' % (strike_fr, toeoff_fr))
        except IndexError:
            logger.debug('cannot detect force rise/fall')
            force_checks_ok = False

        # CoP checks
        if force_checks_ok:
            # check shift of center of pressure during roi in fwd dir
            cop_roi = fp['CoP'][friseind:ffallind, fwd_dir]
            if len(cop_roi) == 0:
                logger.warning('no CoP for given range')
                force_checks_ok = False
            else:
                cop_shift = cop_roi.max() - cop_roi.min()
                total_shift = np.linalg.norm(cop_shift)
                logger.debug('CoP total shift %.2f mm' % total_shift)
                if total_shift > cfg.autoproc.cop_shift_max:
                    logger.debug('center of pressure shifts too much '
                                 '(double contact?)')
                    force_checks_ok = False

        if not force_checks_ok:
            valid = None

        if force_checks_ok and detect_foot:
            logger.debug('using autodetection of foot contact')
            # check foot positions
            valid = None
            # plate boundaries in world coords
            # FIXME: use plate corners and in-polygon algorithm
            # (no need to assume coord axes aligned with plate)
            mins, maxes = fp['lowerbounds'], fp['upperbounds']
            # let foot settle for some tens of msec after strike
            settle_fr = int(50/1000 * info['framerate'])
            fr0 = strike_fr + settle_fr
            logger.debug('plate edges x: %.2f to %.2f  y: %.2f to %.2f' %
                         (mins[0], maxes[0], mins[1], maxes[1]))

            side = _leading_foot(mkrdata)[fr0]
            if side is None:
                raise GaitDataError('cannot determine leading foot from marker'
                                    ' data')
            logger.debug('checking contact for leading foot: %s' % side)
            footmins, footmaxes = _get_foot_points(mkrdata, side, footlen)
            logger.debug('foot edges x: %.2f to %.2f  y: %.2f to %.2f' %
                         (footmins[fr0, 0], footmaxes[fr0, 0],
                          footmins[fr0, 1], footmaxes[fr0, 1]))
            xmin_ok = mins[0] < footmins[fr0, 0] < maxes[0]
            xmax_ok = mins[0] < footmaxes[fr0, 0] < maxes[0]
            if not (xmin_ok and xmax_ok):
                logger.debug('off plate in x dir')
            ymin_ok = mins[1] < footmins[fr0, 1] < maxes[1]
            ymax_ok = mins[1] < footmaxes[fr0, 1] < maxes[1]
            if not (ymin_ok and ymax_ok):
                logger.debug('off plate in y dir')
            ok = xmin_ok and xmax_ok and ymin_ok and ymax_ok
            if ok:
                logger.debug('on-plate check ok for side %s' % side)
                valid = side

        if valid:
            logger.debug('plate %d: valid foot strike on %s at frame %d'
                         % (plate_ind, valid, strike_fr))
            results['valid'].add(valid)
            results[valid+'_strikes'].append(strike_fr)
            results[valid+'_toeoffs'].append(toeoff_fr)
            results[valid+'_strikes_plate'].append(plate_ind)
            results['our_fp_info'][plate] = 'Right' if valid == 'R' else 'Left'
        else:
            logger.debug('plate %d: no valid foot strike' % plate_ind)
            results['our_fp_info'][plate] = 'Invalid'

    logger.debug(results)
    return results
