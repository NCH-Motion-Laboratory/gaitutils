# -*- coding: utf-8 -*-
"""

Utility functions for processing gait data.

@author: Jussi (jnu@iki.fi)
"""

from __future__ import division

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
    """Average marker data for given markers"""
    data_shape = mkrdata[markers[0]+var_type].shape
    mP = np.zeros(data_shape)
    for marker in markers:
        mP += mkrdata[marker+var_type] / len(markers)
    return mP


def principal_movement_direction(mP):
    """ Return principal movement direction (dimension of maximum variance) """
    return np.argmax(np.var(mP, axis=0))


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
        return (V.T / Vn).T


def _get_foot_points(mkrdata, context):
    """Estimate points in the xy plane containing the foot. Foot is modeled
    as a triangle"""
    FOOT_WIDTH1 = 1  # width relative to dist from HEE-TOE line to ANK
    FOOT_WIDTH2 = .5  # width in the opposite dir
    heeP = mkrdata[context+'HEE_P']
    toeP = mkrdata[context+'TOE_P']
    ankP = mkrdata[context+'ANK_P']
    # heel - toe vectors
    ht_ = toeP - heeP
    ht = _normalize(ht_)
    # estimated big toe coordinate (end of foot)
    bigtoeP = heeP + ht_ * cfg.autoproc.foot_relative_len
    # heel - ankle vectors
    ha_ = ankP - heeP
    ha = _normalize(ha_)
    # vectors orthogonal to foot plane, pointing upwards
    hz = np.cross(ha, ht)
    # unit vectors for lateral direction HEE-TOE line to ankle marker)
    hl = _normalize(np.cross(ht, hz))
    # length from HEE-TOE line to ankle marker)
    lat = (hl.T * np.sum(ha_ * hl, axis=1)).T
    # corners defining the foot polygon
    c0 = heeP
    c1 = bigtoeP - FOOT_WIDTH2 * lat
    c2 = bigtoeP + FOOT_WIDTH1 * lat
    # minima and maxima in xy plane
    # ignore nans in reduce()
    with np.errstate(divide='ignore', invalid='ignore'):
        pmin = np.minimum.reduce([c0, c1, c2])
        pmax = np.maximum.reduce([c0, c1, c2])
    return pmin, pmax


def detect_forceplate_events(source, mkrdata=None, fp_info=None):
    """ Detect frames where valid forceplate strikes and toeoffs occur.
    Uses forceplate data and marker positions.

    If mkrdata is None, it will be read from source.
    If fp_info dict is set, no marker and COP checks will be done;
    instead the Eclipse forceplate info will be used. Eclipse info is written
    e.g. as {FP1: 'Left'} where plate indices start from 1 and the value can be
    'Left', 'Right' or 'Invalid'. Even if Eclipse info is used, foot strike
    and toeoff frames must be determined from forceplate data.

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
                   valid=set())

    # get marker data and find "forward" direction (by max variance)
    foot_markers = (cfg.autoproc.right_foot_markers +
                    cfg.autoproc.left_foot_markers)
    if mkrdata is None:
        mkrdata = read_data.get_marker_data(source, foot_markers)
    pos = sum([mkrdata[name+'_P'] for name in foot_markers])
    fwd_dir = np.argmax(np.var(pos, axis=0))
    logger.debug('gait forward direction seems to be %s' %
                 {0: 'x', 1: 'y', 2: 'z'}[fwd_dir])

    for plate_ind, fp in enumerate(fpdata, 1):  # start indexing from 1
        logger.debug('analyzing plate %d' % plate_ind)
        # check Eclipse info if it exists
        detect = True
        # XXX: are we sure that the plate indices match Eclipse?
        plate = 'FP' + str(plate_ind)
        if fp_info is not None and plate in fp_info:
            ecl_valid = fp_info[plate]
            detect = False
            logger.debug('using Eclipse forceplate info: %s' % ecl_valid)
            if ecl_valid == 'Right':
                valid = 'R'
            elif ecl_valid == 'Left':
                valid = 'L'
            elif ecl_valid == 'Invalid':
                continue
            elif ecl_valid == 'Auto':
                detect = True
            else:
                raise Exception('unexpected Eclipse forceplate field')

        # first identify candidates for footstrike by looking at fp data
        # FIXME: filter should maybe depend on sampling freq
        forcetot = signal.medfilt(fp['Ftot'])
        forcetot = _baseline(forcetot)
        fmax = max(forcetot)
        fmaxind = np.where(forcetot == fmax)[0][0]  # first maximum
        logger.debug('max force: %.2f N at %.2f' % (fmax, fmaxind))
        bodymass = info['bodymass']

        if bodymass is None:
            f_threshold = cfg.autoproc.forceplate_contact_threshold * fmax
            logger.warning('body mass unknown, thresholding force at %.2f N',
                           f_threshold)
        else:
            logger.debug('body mass %.2f kg' % bodymass)
            f_threshold = (cfg.autoproc.forceplate_contact_threshold *
                           bodymass * 9.81)
            if (detect and fmax < cfg.autoproc.forceplate_min_weight *
               bodymass * 9.81):
                logger.debug('insufficient max. force on plate')
                continue

        # find indices where force crosses threshold
        try:
            logger.debug('force threshold: %.2f N' % f_threshold)
            friseind = rising_zerocross(forcetot-f_threshold)[0]  # first rise
            ffallind = falling_zerocross(forcetot-f_threshold)[-1]  # last fall
            logger.debug('force rise: %d fall: %d' % (friseind, ffallind))
        except IndexError:
            logger.debug('cannot detect force rise/fall')
            continue

        # we work with 0-based frame indices (=1 less than Nexus frame index)
        strike_fr = int(np.round(friseind / info['samplesperframe']))
        toeoff_fr = int(np.round(ffallind / info['samplesperframe']))
        logger.debug('strike @ frame %d, toeoff @ %d' % (strike_fr, toeoff_fr))

        if detect:
            logger.debug('using autodetection')

            # check shift of center of pressure during roi in fwd dir
            cop_roi = fp['CoP'][friseind:ffallind, fwd_dir]
            if len(cop_roi) == 0:
                logger.warning('no CoP for given range')
                continue
            cop_shift = cop_roi.max() - cop_roi.min()
            total_shift = np.linalg.norm(cop_shift)
            logger.debug('CoP total shift %.2f mm' % total_shift)
            if total_shift > cfg.autoproc.cop_shift_max:
                logger.debug('center of pressure shifts too much '
                             '(double contact?)')
                continue

            # check foot positions
            valid = None
            # plate boundaries in world coords
            # FIXME: use plate corners and in-polygon algorithm
            # (no need to assume coord axes aligned with plate)
            mins, maxes = fp['lowerbounds'], fp['upperbounds']
            for side in ['R', 'L']:
                logger.debug('checking side %s' % side)
                footmins, footmaxes = _get_foot_points(mkrdata, side)
                xmin_ok = mins[0] < footmins[strike_fr, 0] < maxes[0]
                xmax_ok = mins[0] < footmaxes[strike_fr, 0] < maxes[0]
                logger.debug('at strike:')
                if not (xmin_ok and xmax_ok):
                    logger.debug('off plate in x dir')
                ymin_ok = mins[1] < footmins[strike_fr, 1] < maxes[1]
                ymax_ok = mins[1] < footmaxes[strike_fr, 1] < maxes[1]
                if not (ymin_ok and ymax_ok):
                    logger.debug('off plate in y dir')
                ok = xmin_ok and xmax_ok and ymin_ok and ymax_ok
                if ok:
                    logger.debug('contact ok')
                xmin_ok = mins[0] < footmins[toeoff_fr, 0] < maxes[0]
                xmax_ok = mins[0] < footmaxes[toeoff_fr, 0] < maxes[0]
                logger.debug('at toeoff:')
                if not (xmin_ok and xmax_ok):
                    logger.debug('off plate in x dir')
                ymin_ok = mins[1] < footmins[toeoff_fr, 1] < maxes[1]
                ymax_ok = mins[1] < footmaxes[toeoff_fr, 1] < maxes[1]
                if not (ymin_ok and ymax_ok):
                    logger.debug('off plate in y dir')
                ok &= xmin_ok and xmax_ok and ymin_ok and ymax_ok
                if ok:
                    logger.debug('contact ok')

                if ok:
                    if valid:  # already got valid contact for other foot
                        raise GaitDataError('got valid contact for both feet')
                    else:
                        valid = side
                        logger.debug('on-plate check ok for side %s' % valid)

        if valid:
            logger.debug('plate %d: valid foot strike on %s at frame %d'
                         % (plate_ind, valid, strike_fr))
            results['valid'].add(valid)
            results[valid+'_strikes'].append(strike_fr)
            results[valid+'_toeoffs'].append(toeoff_fr)
        else:
            logger.debug('plate %d: no valid foot strike' % plate_ind)

    logger.debug(results)
    return results
