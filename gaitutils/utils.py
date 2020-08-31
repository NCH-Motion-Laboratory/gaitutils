# -*- coding: utf-8 -*-
"""

Utility functions for processing gait data.

@author: Jussi (jnu@iki.fi)
"""

from __future__ import division

from builtins import range
from builtins import str
from builtins import zip
from scipy import signal
from matplotlib import path
import matplotlib.pyplot as plt
import numpy as np
import logging

from .envutils import GaitDataError
from .config import cfg
from .numutils import rising_zerocross, digitize_array, falling_zerocross, _baseline


logger = logging.getLogger(__name__)


class TrialEvents(object):
    """A struct-like container for gait event data.
    A dataclass would be better, but requires Python 3.7.
    Logically this might belong in trial.py, but low-level readers (e.g
    nexus.py) need it, so keeping it here makes imports simpler.
    """

    # these are the event types we accept
    event_types = ['rstrikes', 'lstrikes', 'rtoeoffs', 'ltoeoffs', 'general']
    # these are our internal stuff
    secret_stuff = ['_offset']

    def __init__(self, **kwargs):
        self._offset = None
        # init empty lists for all event types
        for evtype in TrialEvents.event_types:
            setattr(self, evtype, list())
        # init event lists via kwargs
        for key, val in kwargs.items():
            setattr(self, key, val)

    def __repr__(self):
        s = '<TrialEvents |'
        for k, evtype in enumerate(TrialEvents.event_types):
            if k > 0:
                s += ','
            ev_vals = getattr(self, evtype)
            s += ' %s: %s' % (evtype, ev_vals)
        s += '>'
        return s

    def __setattr__(self, attr, value):
        if attr in TrialEvents.event_types:  # regular event list
            if not isinstance(value, list):
                raise AttributeError('attribute must be a list')
            else:
                # sort to make sure that event frames are in increasing order
                super(TrialEvents, self).__setattr__(attr, sorted(value))
        elif attr in TrialEvents.secret_stuff:
            super(TrialEvents, self).__setattr__(attr, value)
        else:
            raise AttributeError('%s is not a valid attribute' % attr)

    def subtract_offset(self, offset):
        """Subtract given offset from events."""
        if self._offset:
            raise RuntimeError('offset can be subtracted only once')
        for evtype in TrialEvents.event_types:
            events = getattr(self, evtype)
            events_offset = [e - offset for e in events]
            setattr(self, evtype, events_offset)
        self._offset = offset


def _empty_fp_events():
    """Container for forceplate events"""
    return dict(
        R_strikes=[],
        R_toeoffs=[],
        L_strikes=[],
        L_toeoffs=[],
        valid=set(),
        R_strikes_plate=[],
        L_strikes_plate=[],
        our_fp_info={},
        coded='',
    )


def marker_gaps(mdata, ignore_edge_gaps=True):
    """Find gaps for a marker.

    Parameters
    ----------
    mdata : ndarray
        Marker position data. See read_data.get_marker_data()
    ignore_edge_gaps : bool, optional
        If True, leading and trailing gaps are ignored.

    Returns
    -------
    ndarray
        The indices of frames where gaps occur.
    """
    allzero = np.any(mdata, axis=1).astype(int)
    if ignore_edge_gaps:
        nleading = allzero.argmax()
        allzero_trim = np.trim_zeros(allzero)
        gap_inds = np.where(allzero_trim == 0)[0] + nleading
    else:
        gap_inds = np.where(allzero == 0)[0]
    return gap_inds


def _step_width(source):
    """Compute step width over trial cycles.

    For details of computation, see:
    https://www.vicon.com/faqs/software/how-does-nexus-plug-in-gait-and-polygon-calculate-gait-cycle-parameters-spatial-and-temporal
    Returns context keyed dict of lists.
    FIXME: marker name into params?
    FIXME: this (and similar) may also need to take Trial instance as argument
    to avoid creating new Trials
    """
    from .trial import Trial

    tr = Trial(source)
    sw = dict()
    mkr = 'TOE'  # marker name without context
    mkrdata = tr._full_marker_data
    # FIXME: why not use cycles here?
    for context, strikes in zip(['L', 'R'], [tr.events.lstrikes, tr.events.rstrikes]):
        sw[context] = list()
        nstrikes = len(strikes)
        if nstrikes < 2:
            continue
        # contralateral vars
        context_co = 'L' if context == 'R' else 'R'
        strikes_co = tr.events.lstrikes if context == 'R' else tr.events.rstrikes
        mname = context + mkr
        mname_co = context_co + mkr
        for j, strike in enumerate(strikes):
            if strike == strikes[-1]:  # last strike on this side
                break
            pos_this = mkrdata[mname][strike]
            pos_next = mkrdata[mname][strikes[j + 1]]
            strikes_next_co = [k for k in strikes_co if k > strike]
            if len(strikes_next_co) == 0:  # no subsequent contralateral strike
                break
            pos_next_co = mkrdata[mname_co][strikes_next_co[0]]
            # vector distance between 'step lines' (see url above)
            V1 = pos_next - pos_this
            V1 /= np.linalg.norm(V1)
            VC = pos_next_co - pos_this
            VCP = V1 * np.dot(VC, V1)  # proj to ipsilateral line
            VSW = VCP - VC
            # marker data is in mm, but return step width in m
            sw[context].append(np.linalg.norm(VSW) / 1000.0)
    return sw


def avg_markerdata(mkrdata, markers, roi=None, fail_on_gaps=True, avg_velocity=False):
    """Average marker data.

    Parameters
    ----------
    mkrdata : dict
        The markerdata dict.
    markers : list
        Markers to average.
    roi : array-like
        If given, specified a ROI. Gaps outside the ROI will be ignored.
    fail_on_gaps : bool, optional
        If True, raise an exception on ANY gaps. Otherwise, markers with gaps
        will not be included in the average.
    avg_velocity : bool, optional
        If True, return averaged marker velocity data instead of position.

    Returns
    -------
    ndarray
        The averaged data (Nx3).
    """
    data_shape = mkrdata[markers[0]].shape
    mdata_avg = np.zeros(data_shape)
    if roi is None:
        roi = [0, data_shape[0]]
    roi_frames = np.arange(roi[0], roi[1])
    n_ok = 0
    for marker in markers:
        mdata = mkrdata[marker]
        if avg_velocity:
            mdata = np.gradient(mdata)[0]
        gap_frames = marker_gaps(mdata)
        if np.intersect1d(roi_frames, gap_frames).size > 0:
            if fail_on_gaps:
                raise GaitDataError('Averaging data for %s has gaps' % marker)
            else:
                logger.warning(
                    'marker %s cannot be included in average due to gaps' % marker
                )
                continue
        else:
            mdata_avg += mdata
            n_ok += 1
    if n_ok == 0:
        raise GaitDataError('all markers have gaps, cannot average')
    else:
        return mdata_avg / n_ok


# FIXME: marker sets could be moved into models.py?
def _pig_markerset(fullbody=True, sacr=True):
    """ PiG marker set as dict (empty values) """
    _pig = [
        'LASI',
        'RASI',
        'LTHI',
        'LKNE',
        'LTIB',
        'LANK',
        'LHEE',
        'LTOE',
        'RTHI',
        'RKNE',
        'RTIB',
        'RANK',
        'RHEE',
        'RTOE',
    ]
    if fullbody:
        _pig += [
            'LFHD',
            'RFHD',
            'LBHD',
            'RBHD',
            'C7',
            'T10',
            'CLAV',
            'STRN',
            'RBAK',
            'LSHO',
            'LELB',
            'LWRA',
            'LWRB',
            'LFIN',
            'RSHO',
            'RELB',
            'RWRA',
            'RWRB',
            'RFIN',
        ]
    # add pelvis posterior markers; SACR or RPSI/LPSI
    _pig.extend(['SACR'] if sacr else ['RPSI', 'LPSI'])
    return {mkr: None for mkr in _pig}


def _pig_pelvis_markers():
    return ['RASI', 'RPSI', 'LASI', 'LPSI', 'SACR']


def is_plugingait_set(mkrdata):
    """Check whether marker data set corresponds to Plug-in Gait (full body or
    lower body only). Extra markers are accepted."""
    mkrs = set(mkrdata.keys())
    # required markers
    lb_mkrs_sacr = set(_pig_markerset(fullbody=False).keys())
    lb_mkrs_psi = set(_pig_markerset(fullbody=False, sacr=False).keys())
    return lb_mkrs_psi.issubset(mkrs) or lb_mkrs_sacr.issubset(mkrs)


def _check_markers_flipped(mkrdata):
    """Check for markers that may typically get flipped in labeling.
    Yields pairs of flipped markers"""
    MAX_ANGLE = 90  # max angle to consider vectors 'similarly oriented'
    # HEE-TOE checks
    for side in ['L', 'R']:
        # compare HEE-TOE line to pelvis orientation
        mkr_toe, mkr_hee = '%sTOE' % side, '%sHEE' % side
        ht = _normalize(mkrdata[mkr_toe] - mkrdata[mkr_hee])
        if side + 'PSI' in mkrdata:
            pa = _normalize(mkrdata[side + 'ASI'] - mkrdata[side + 'PSI'])
        elif 'SACR' in mkrdata:
            pa = _normalize(mkrdata[side + 'ASI'] - mkrdata['SACR'])
        angs = np.arccos(np.sum(ht * pa, axis=1)) / np.pi * 180
        if np.nanmedian(angs) > MAX_ANGLE:
            yield mkr_toe, mkr_hee


def _principal_movement_direction(mdata):
    """Return principal movement direction (dimension of maximum variance)"""
    inds_ok = np.where(np.any(mdata, axis=1))  # make sure that gaps are ignored
    return np.argmax(np.var(mdata[inds_ok], axis=0))


def _get_foot_contact_vel(mkrdata, fp_events, medians=True, roi=None):
    """Return foot velocities during forceplate strike/toeoff frames.
    fp_events is from detect_forceplate_events() If medians=True, return median
    values."""
    results = dict()
    for context, markers in zip(
        ('R', 'L'), [cfg.autoproc.right_foot_markers, cfg.autoproc.left_foot_markers]
    ):
        # we can be less strict about gaps here, since missing a marker or two
        # probably won't really affect the velocity
        footctrv_ = avg_markerdata(
            mkrdata,
            markers,
            roi=roi,
            fail_on_gaps=False,
            avg_velocity=True,
        )
        footctrv = np.linalg.norm(footctrv_, axis=1)
        strikes = fp_events[context + '_strikes']
        toeoffs = fp_events[context + '_toeoffs']
        results[context + '_strike'] = footctrv[strikes]
        results[context + '_toeoff'] = footctrv[toeoffs]
    if medians:
        results = {
            key: (np.array([np.median(x)]) if x.size > 0 else x)
            for key, x in results.items()
        }
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
    """Estimate points in the xy plane enclosing the foot.

    Foot is modeled as a triangle with three points: heel, lateral leading edge
    (small toe) and medial leading edge (hallux)"""
    # marker data as N x 3 matrices
    heeP = mkrdata[context + 'HEE']
    toeP = mkrdata[context + 'TOE']
    ankP = mkrdata[context + 'ANK']
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
    ha_htV = htVn * np.sum(haV * htVn, axis=1)[:, np.newaxis]
    # lateral ANK vector (from HEE-TOE line to ANK)
    lankV = haV - ha_htV
    # edge points are coplanar with markers but not with the foot
    # lateral foot edge
    lat_edge = foot_end + lankV
    # medial foot edge
    med_edge = foot_end - lankV
    # heel edge (compensate for marker diameter)
    heel_edge = heeP + htVn * cfg.autoproc.marker_diam / 2
    logger.debug(
        'foot length: %.1f mm width: %.1f mm'
        % (
            np.nanmedian(np.linalg.norm(heel_edge - foot_end, axis=1)),
            np.nanmedian(np.linalg.norm(lat_edge - med_edge, axis=1)),
        )
    )
    return {'heel': heel_edge, 'lateral': lat_edge, 'medial': med_edge, 'toe': foot_end}


def _leading_foot(mkrdata, roi=None):
    """Determine which foot is leading (ahead in the direction of gait).
    Returns n-length list of 'R' or 'L' correspondingly (n = number of
    frames). Gaps are indicated as None. mkrdata must include foot and
    pelvis markers"""
    subj_pos = avg_markerdata(
        mkrdata, cfg.autoproc.track_markers, roi=roi, fail_on_gaps=False
    )
    # FIXME: should not use a single dim here
    gait_dim = _principal_movement_direction(subj_pos)
    gait_dir = np.median(np.diff(subj_pos, axis=0), axis=0)[gait_dim]
    lfoot = avg_markerdata(
        mkrdata, cfg.autoproc.left_foot_markers, roi=roi, fail_on_gaps=False
    )[:, gait_dim]
    rfoot = avg_markerdata(
        mkrdata, cfg.autoproc.right_foot_markers, roi=roi, fail_on_gaps=False
    )[:, gait_dim]
    cmpfun = np.greater if gait_dir > 0 else np.less
    return [
        None if R == 0.0 or L == 0.0 else ('R' if cmpfun(R, L) else 'L')
        for R, L in zip(rfoot, lfoot)
    ]


def _trial_median_velocity(source, return_curve=False):
    """Compute median velocity (walking speed) over whole trial by
    differentiation of marker data from track markers. Up/down movement of
    markers may slightly increase speed compared to time-distance values.
    If return_curve, return velocity curve normalized to 0..100% of trial"""
    from . import read_data

    try:
        frate = read_data.get_metadata(source)['framerate']
        mkrdata = read_data.get_marker_data(source, cfg.autoproc.track_markers)
        vel_3 = avg_markerdata(mkrdata, cfg.autoproc.track_markers, avg_velocity=True)
        vel_ = np.sqrt(np.sum(vel_3 ** 2, 1))  # scalar velocity
    except (GaitDataError, ValueError):
        if return_curve:
            nanvec = np.empty((100, 1))
            nanvec[:] = np.nan
            return np.nan, nanvec
        else:
            return np.nan
    vel = np.median(vel_[np.where(vel_)])  # ignore zeros
    vel_ms = vel * frate / 1000.0  # convert to m/s
    if return_curve:
        tn = np.linspace(0, 100, 101)
        vel_curve = np.interp(tn, np.linspace(0, 100, len(vel_)), vel_)
        return vel_ms, vel_curve * frate / 1000.0
    else:
        return vel_ms


def _point_in_poly(poly, pt):
    """Point-in-polygon. poly is ordered nx3 array of vertices and P is mx3
    array of points. Returns mx3 array of booleans. 3rd dim is currently
    ignored"""
    p = path.Path(poly[:, :2])
    return p.contains_point(pt)


def detect_forceplate_events(source, mkrdata=None, fp_info=None, roi=None):
    """Detect frames where valid forceplate strikes and toeoffs occur.

    Uses forceplate data and foot shape estimated from markers

    If supplied, mkrdata must include foot and pelvis markers. Otherwise
    it will be read from source.

    If fp_info dict is supplied, no marker-based checks will be done;
    instead the Eclipse forceplate info will be used to determine the context.
    Eclipse info is written e.g. as {FP1: 'Left'} where plate indices are 1-based
    and the value can be 'Auto', 'Left', 'Right' or 'Invalid'.
    Even if Eclipse info is used to determine context, the foot strike and
    toeoff frames must be determined from forceplate data.

    If roi is given e.g. [100, 300], all marker data checks will be restricted
    to roi.
    """

    def _check_foot_on_plate(fpdata, mkrdata, fr0, side, footlen):
        """Helper for foot-plate check. Returns 0, 1, 2 for:
        completely outside plate, partially outside plate, inside plate"""
        allpts = _get_foot_points(mkrdata, side, footlen)
        poly = fpdata['cor_full']
        pts_ok = list()
        for label, pts in allpts.items():
            pt = pts[fr0, :]
            pt_ok = _point_in_poly(poly, pt)
            logger.debug('%s point %son plate' % (label, '' if pt_ok else 'not '))
            pts_ok.append(pt_ok)
        if all(pts_ok):
            return 2
        elif any(pts_ok):
            return 1
        else:
            return 0

    def _check_eclipse_fp_info(fp_info_this):
        """Helper to check Eclipse forceplate info.
        Returns tuple of (valid, detect_foot)
        valid: detected foot according to Eclipse; 'L', 'R' or None
        (None signifies both 'do not know' and 'invalid')
        detect_foot: whether autodetection of context is desired
        or we should just use Eclipse info
        """
        # XXX: are we sure that the plate indices always match Eclipse?
        detect_foot = False
        logger.debug('using Eclipse forceplate info: %s' % fp_info_this)
        if fp_info_this == 'Right':
            # force right foot - do not detect context
            valid = 'R'
        elif fp_info_this == 'Left':
            # force left foot - do not detect context
            valid = 'L'
        elif fp_info_this == 'Invalid':
            # force invalid contact - do not detect context
            valid = None
        elif fp_info_this == 'Auto':
            # autodetect context
            detect_foot = True
            valid = None
        else:
            raise GaitDataError('unexpected Eclipse forceplate field')
        return valid, detect_foot

    def _check_plate_force(fp):
        """Analyze forceplate signal.

        Finds candidate frames for foot strike / toeoff events. This is done by finding frames where
        the force rapidly increases or settles down.
        """
        # apply median filter to remove spikes
        # XXX: kernel size should maybe depend on sampling freq?
        forcetot = signal.medfilt(fp['Ftot'], kernel_size=3)
        forcetot = _baseline(forcetot)
        fmaxind = np.argmax(forcetot)
        fmax = forcetot[fmaxind]
        logger.debug('peak force: %.2f N at sample %d' % (fmax, fmaxind))

        # determine force threshold based on body mass or maximum force
        if bodymass is None:
            f_threshold = cfg.autoproc.forceplate_contact_threshold * fmax
            logger.warning(
                'body mass unknown, thresholding force at %.2f N', f_threshold
            )
        else:
            logger.debug('body mass %.2f kg' % bodymass)
            f_threshold = cfg.autoproc.forceplate_contact_threshold * bodymass * 9.81
            if fmax < cfg.autoproc.forceplate_min_weight * bodymass * 9.81:
                logger.debug('insufficient max. force on plate')
                return list(), list()

        # find indices where rising/falling force crosses threshold
        # convert to 0-based frame indices (=1 less than Nexus frame index)
        f_rising_inds = rising_zerocross(forcetot - f_threshold)
        f_rising_inds = f_rising_inds[np.where(f_rising_inds < fmaxind)]
        f_rising_frames = list(np.round(f_rising_inds / info['samplesperframe']).astype(int))
        f_falling_inds = falling_zerocross(forcetot - f_threshold)
        f_falling_inds = f_falling_inds[np.where(f_falling_inds > fmaxind)] / info['samplesperframe']
        f_falling_frames = list(np.round(f_rising_inds / info['samplesperframe']).astype(int))
        return f_rising_frames, f_falling_frames

    # get subject info
    from . import read_data

    logger.debug('detecting forceplate events from %s' % source)
    logger.debug('reading subject data')
    info = read_data.get_metadata(source)
    fpdata = read_data.get_forceplate_data(source)
    results = _empty_fp_events()
    # read marker data if it was not supplied
    if mkrdata is None:
        mkrs = (
            cfg.autoproc.right_foot_markers
            + cfg.autoproc.left_foot_markers
            + cfg.autoproc.track_markers
        )
        mkrdata = read_data.get_marker_data(source, mkrs)
    footlen = info['subj_params']['FootLen']
    rfootlen = info['subj_params']['RFootLen']
    lfootlen = info['subj_params']['LFootLen']
    if footlen is not None:
        logger.debug('(obsolete) single foot length parameter set to %.2f' % footlen)
        rfootlen = lfootlen = footlen
    elif rfootlen is not None and lfootlen is not None:
        logger.debug(
            'foot length parameters set to r=%.2f, l=%.2f' % (rfootlen, lfootlen)
        )
    else:
        logger.debug('foot length parameter not set')
    bodymass = info['subj_params']['Bodymass']
    events_0 = automark_events(source, mkrdata=mkrdata, mark=False, roi=roi)

    # loop over plates; our internal forceplate index is 0-based
    for plate_ind, fp in enumerate(fpdata):
        logger.debug('analyzing plate %d' % plate_ind)

        # check Eclipse info for this plate
        plate = 'FP' + str(plate_ind + 1)  # Eclipse plate naming starts from FP1
        if fp_info is not None and plate in fp_info:
            fp_info_this = fp_info[plate]
            valid, detect_foot = _check_eclipse_fp_info(fp_info_this)
        else:
            logger.debug('not using Eclipse forceplate info')
            # autodetect context
            valid = None
            detect_foot = True

        # check the force signal
        strike_frames, toeoff_frames = _check_plate_force(fp)
        if strike_frames and toeoff_frames:
            force_ok = True
            strike_fr = strike_frames[-1]
            toeoff_fr = toeoff_frames[0]
        else:
            force_ok = False

        # autodetect context and whether contact is valid (all markers on plate)
        if force_ok and detect_foot:
            logger.debug('using autodetection of foot contact')
            # allows foot to settle for 50 ms after strike
            settle_time = int(50 / 1000 * info['framerate'])
            fr0 = strike_fr + settle_time
            side = _leading_foot(mkrdata, roi=roi)[fr0]
            if side is None:
                raise GaitDataError('cannot determine leading foot from marker data')
            footlen = rfootlen if side == 'R' else lfootlen
            logger.debug('checking contact for leading foot: %s' % side)
            ok = _check_foot_on_plate(fp, mkrdata, fr0, side, footlen) == 2
            # check that the contralateral foot clears the plate on subsequent and previous strike
            if ok and events_0 is not None:
                contra_side = 'R' if side == 'L' else 'L'
                contra_strikes = events_0[contra_side + '_strikes']
                contra_strikes_next = contra_strikes[
                    np.where(contra_strikes > strike_fr)
                ]
                if contra_strikes_next.size == 0:
                    logger.debug('no subsequent contralateral strike')
                else:
                    fr0 = contra_strikes_next[0] + settle_time
                    logger.debug(
                        'checking next contact for contralateral '
                        'foot (at frame %d)' % fr0
                    )
                    contra_next_ok = (
                        _check_foot_on_plate(fp, mkrdata, fr0, contra_side, footlen)
                        == 0
                    )
                    ok &= contra_next_ok
                contra_strikes_prev = contra_strikes[
                    np.where(contra_strikes < strike_fr)
                ]
                if contra_strikes_prev.size == 0:
                    logger.debug('no previous contralateral strike')
                else:
                    fr0 = contra_strikes_prev[-1] + settle_time
                    logger.debug(
                        'checking previous contact for contralateral '
                        'foot (at frame %d)' % fr0
                    )
                    contra_prev_ok = (
                        _check_foot_on_plate(fp, mkrdata, fr0, contra_side, footlen)
                        == 0
                    )
                    ok &= contra_prev_ok
            valid = side if ok else None

        if valid:
            logger.debug(
                'plate %d: valid foot strike on %s at frame %d'
                % (plate_ind, valid, strike_fr)
            )
            results['valid'].add(valid)
            results[valid + '_strikes'].append(strike_fr)
            results[valid + '_toeoffs'].append(toeoff_fr)
            results[valid + '_strikes_plate'].append(plate_ind)
            results['our_fp_info'][plate] = 'Right' if valid == 'R' else 'Left'
            results['coded'] += valid
        else:
            logger.debug('plate %d: no valid foot strike' % plate_ind)
            results['our_fp_info'][plate] = 'Invalid'
            results['coded'] += 'X'

    logger.debug(results)
    return results


def automark_events(
    source,
    mkrdata=None,
    events_range=None,
    fp_events=None,
    vel_thresholds=None,
    roi=None,
    start_on_forceplate=False,
    plot=False,
    mark=True,
):
    """Automatically mark foot strike and toeoff events.

    Events are marked based on velocity thresholding. Absolute thresholds can be
    specified as arguments. Otherwise, relative thresholds will be calculated
    based on the data. Optimal results will be obtained when thresholds are
    predetermined based on forceplate data, but it is not necessary.

    Before running automark, run reconstruct, label, gap fill and filter
    pipelines. Filtering is important to get reasonably smooth derivatives.

    Parameters
    ----------
    source : str | ViconNexus
        The data source, either c3d filename or ViconNexus connection. For Nexus
        connections, the events can automatically be inserted into Nexus. For c3d
        files, the events are returned but not actually written to the c3d file.
    mkrdata : dict, optional
        The marker data dict. If not given, it will be read from the source. If
        given, it must include foot markers and subject tracking markers (see cfg).
    events_range : array_like, optional
        If specified, the events will be restricted to given coordinate range in
        the principal gait direction. E.g. [-1000, 1000]
    fp_events : dict, optional
        If not None, specifies the forceplate detected strikes and toeoffs
        (see utils.detect_forceplate_events). These will be then considered the
        ground truth and will replace nearby autodetected events.
    vel_thresholds : dict, optional
        Absolute velocity thresholds for identifying events. These can be obtained
        from forceplate data (utils.check_forceplate_contact). If None, relative
        thresholds will be computed based on marker data.
    roi : array_like, optional
        If not None, specifies a ROI (in frames) inside which to mark events.
    start_on_forceplate : bool, optional
        If True, try to start the first gait cycle on forceplate, i.e. events
        earlier than the first forceplate contact will not be marked.
    plot : bool, optional
        Plot velocity curves and events using matplotlib. Mostly for debug purposes.
    mark : bool, optional
        If False, do not actually insert the marker events into Nexus.
    """

    from .read_data import get_metadata, get_marker_data

    info = get_metadata(source)
    frate = info['framerate']
    # some operations are Nexus specific and make no sense for c3d source
    from . import nexus

    # TODO: move into config
    # marker data is assumed to be in mm
    # mm/frame = 1000 m/frame = 1000/frate m/s
    VEL_CONV = 1000 / frate
    # reasonable limit for peak velocity (m/s before multiplier)
    MAX_PEAK_VELOCITY = 12 * VEL_CONV
    # reasonable limits for velocity on slope (increasing/decreasing)
    MAX_SLOPE_VELOCITY = 6 * VEL_CONV
    MIN_SLOPE_VELOCITY = 0  # not currently in use
    # minimum swing velocity (rel to max velocity)
    MIN_SWING_VELOCITY = 0.5
    # median prefilter width
    PREFILTER_MEDIAN_WIDTH = 3
    # tolerance for matching forceplate and vel. thresholded events
    FP_EVENT_TOL = 10

    if vel_thresholds is None:
        vel_thresholds = {
            'L_strike': None,
            'L_toeoff': None,
            'R_strike': None,
            'R_toeoff': None,
        }

    if mkrdata is None:
        # FIXME: missing markers are not detected here?
        reqd_markers = (
            cfg.autoproc.right_foot_markers
            + cfg.autoproc.left_foot_markers
            + cfg.autoproc.track_markers
        )
        mkrdata = get_marker_data(source, reqd_markers)

    rfootctrv_ = avg_markerdata(
        mkrdata,
        cfg.autoproc.right_foot_markers,
        roi=roi,
        fail_on_gaps=False,
        avg_velocity=True,
    )
    rfootctrv = np.linalg.norm(rfootctrv_, axis=1)
    lfootctrv_ = avg_markerdata(
        mkrdata,
        cfg.autoproc.left_foot_markers,
        roi=roi,
        fail_on_gaps=False,
        avg_velocity=True,
    )
    lfootctrv = np.linalg.norm(lfootctrv_, axis=1)

    # position data: use ANK marker
    rfootctrP = mkrdata['RANK']
    lfootctrP = mkrdata['LANK']

    strikes_all = {}
    toeoffs_all = {}

    # loop: same operations for left / right foot
    for context, footctrP, footctrv in zip(
        ('R', 'L'), (rfootctrP, lfootctrP), (rfootctrv, lfootctrv)
    ):
        logger.debug('marking side %s' % context)
        # foot center position
        # filter scalar velocity data to suppress noise and spikes
        footctrv = signal.medfilt(footctrv, PREFILTER_MEDIAN_WIDTH)
        # get peak (swing) velocity
        maxv = _get_foot_swing_velocity(footctrv, MAX_PEAK_VELOCITY, MIN_SWING_VELOCITY)

        # compute thresholds
        if cfg.autoproc.use_fp_vel_thresholds and vel_thresholds[context + '_strike']:
            threshold_fall_ = vel_thresholds[context + '_strike']
        else:
            threshold_fall_ = maxv * cfg.autoproc.strike_vel_threshold
        if cfg.autoproc.use_fp_vel_thresholds and vel_thresholds[context + '_toeoff']:
            threshold_rise_ = vel_thresholds[context + '_toeoff']
        else:
            threshold_rise_ = maxv * cfg.autoproc.toeoff_vel_threshold
        logger.debug(
            'side: %s, default thresholds fall/rise: %.2f/%.2f'
            % (
                context,
                maxv * cfg.autoproc.strike_vel_threshold,
                maxv * cfg.autoproc.toeoff_vel_threshold,
            )
        )
        logger.debug('using thresholds: %.2f/%.2f' % (threshold_fall_, threshold_rise_))
        # find point where velocity crosses threshold
        # foot strikes (velocity decreases)
        cross = falling_zerocross(footctrv - threshold_fall_)
        # exclude edges of data vector
        fmax = len(footctrv) - 1
        cross = cross[np.where(np.logical_and(cross > 0, cross < fmax))]
        # check velocity on slope
        cind_min = np.logical_and(
            footctrv[cross - 1] < MAX_SLOPE_VELOCITY,
            footctrv[cross - 1] > MIN_SLOPE_VELOCITY,
        )
        cind_max = np.logical_and(
            footctrv[cross + 1] < MAX_SLOPE_VELOCITY,
            footctrv[cross + 1] > MIN_SLOPE_VELOCITY,
        )
        strikes = cross[np.logical_and(cind_min, cind_max)]

        # check for foot swing (velocity maximum) between consecutive strikes
        # if no swing, keep deleting the latter event until swing is found
        bad = []
        for sind in range(len(strikes)):
            if sind in bad:
                continue
            for sind2 in range(sind + 1, len(strikes)):
                swing_max_vel = footctrv[strikes[sind] : strikes[sind2]].max()
                # logger.debug('check %d-%d' % (strikes[sind], strikes[sind2]))
                if swing_max_vel < maxv * MIN_SWING_VELOCITY:
                    logger.debug(
                        'no swing between strikes %d-%d, deleting %d'
                        % (strikes[sind], strikes[sind2], strikes[sind2])
                    )
                    bad.append(sind2)
                else:
                    break
        strikes = np.delete(strikes, bad)

        if len(strikes) == 0:
            raise GaitDataError('No valid foot strikes detected')

        # toe offs (velocity increases)
        cross = rising_zerocross(footctrv - threshold_rise_)
        cross = cross[np.where(np.logical_and(cross > 0, cross < len(footctrv)))]
        cind_min = np.logical_and(
            footctrv[cross - 1] < MAX_SLOPE_VELOCITY,
            footctrv[cross - 1] > MIN_SLOPE_VELOCITY,
        )
        cind_max = np.logical_and(
            footctrv[cross + 1] < MAX_SLOPE_VELOCITY,
            footctrv[cross + 1] > MIN_SLOPE_VELOCITY,
        )
        toeoffs = cross[np.logical_and(cind_min, cind_max)]

        if len(toeoffs) == 0:
            raise GaitDataError('Could not detect any toe-off events')

        # check for multiple toeoffs
        for s1, s2 in list(zip(strikes, np.roll(strikes, -1)))[:-1]:
            to_this = np.where(np.logical_and(toeoffs > s1, toeoffs < s2))[0]
            if len(to_this) > 1:
                logger.debug(
                    '%d toeoffs during cycle, keeping the last one' % len(to_this)
                )
                toeoffs = np.delete(toeoffs, to_this[:-1])

        logger.debug('autodetected strike events: %s' % strikes)
        logger.debug('autodetected toeoff events: %s' % toeoffs)

        # select events for which the foot is close enough to center frame
        if events_range:
            mdata = avg_markerdata(mkrdata, cfg.autoproc.track_markers, roi=roi)
            fwd_dim = _principal_movement_direction(mdata)
            strike_pos = footctrP[strikes, fwd_dim]
            dist_ok = np.logical_and(
                strike_pos > events_range[0], strike_pos < events_range[1]
            )
            # exactly zero position at strike should indicate a gap -> exclude
            # TODO: smarter gap handling
            dist_ok = np.logical_and(dist_ok, strike_pos != 0)
            strikes = strikes[dist_ok]

        # correct foot strikes with force plate autodetected events
        if fp_events and fp_events[context + '_strikes']:
            fp_strikes = fp_events[context + '_strikes']
            logger.debug('forceplate strikes: %s' % fp_strikes)
            # find best fp matches for all strikes
            fpc = digitize_array(strikes, fp_strikes)
            ok_ind = np.where(np.abs(fpc - strikes) < FP_EVENT_TOL)[0]
            if ok_ind.size == 0:
                logger.warning(
                    'could not match forceplate strike with an autodetected strike'
                )
            else:
                # replace with fp detected strikes
                strikes[ok_ind] = fpc[ok_ind]
                logger.debug('fp corrected strikes: %s' % strikes)
            # toeoffs
            fp_toeoffs = fp_events[context + '_toeoffs']
            logger.debug('forceplate toeoffs: %s' % fp_toeoffs)
            fpc = digitize_array(toeoffs, fp_toeoffs)
            ok_ind = np.where(np.abs(fpc - toeoffs) < FP_EVENT_TOL)[0]
            if ok_ind.size == 0:
                logger.warning(
                    'could not match forceplate toeoff with an autodetected toeoff'
                )
            else:
                toeoffs[ok_ind] = fpc[ok_ind]
                logger.debug('fp corrected toeoffs: %s' % toeoffs)
            # delete strikes before (actual) 1st forceplate contact
            if start_on_forceplate and len(fp_strikes) > 0:
                # use a tolerance here to avoid deleting possible (uncorrected)
                # strike near the fp
                not_ok = np.where(strikes < fp_strikes[0] - FP_EVENT_TOL)[0]
                if not_ok.size > 0:
                    logger.debug(
                        'deleting foot strikes before forceplate: %s' % strikes[not_ok]
                    )
                    strikes = np.delete(strikes, not_ok)

        if roi is not None:
            strikes = np.extract(
                np.logical_and(roi[0] <= strikes + 1, strikes + 1 <= roi[1]), strikes
            )

            toeoffs = np.extract(
                np.logical_and(roi[0] <= toeoffs + 1, toeoffs + 1 <= roi[1]), toeoffs
            )

        if len(strikes) == 0:
            raise GaitDataError('No valid foot strikes detected')

        # delete toeoffs that are not between strike events
        not_ok = np.where(
            np.logical_or(toeoffs <= min(strikes), toeoffs >= max(strikes))
        )
        toeoffs = np.delete(toeoffs, not_ok)

        logger.debug('final strike events: %s' % strikes)
        logger.debug('final toeoff events: %s' % toeoffs)

        if mark:
            if not nexus._is_vicon_instance(source):
                raise ValueError('event marking supported only for Nexus')
            vicon = nexus.viconnexus()
            nexus._create_events(vicon, context, strikes, toeoffs)

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
            ax.plot(strikes, footctrv[strikes], 'kD', markersize=10, label='strike')
            ax.plot(toeoffs, footctrv[toeoffs], 'k^', markersize=10, label='toeoff')
            ax.legend(numpoints=1, fontsize=10)
            ax.set_ylim(0, maxv + 10)
            if not first_call:
                plt.xlabel('Frame')
            ax.set_ylabel('Velocity (mm/frame)')
            ax.set_title('Left' if context == 'L' else 'Right')

    if plot:
        plt.show()

    return {
        'R_strikes': strikes_all['R'],
        'L_strikes': strikes_all['L'],
        'R_toeoffs': toeoffs_all['R'],
        'L_toeoffs': toeoffs_all['L'],
    }
