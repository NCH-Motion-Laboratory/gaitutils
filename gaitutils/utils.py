# -*- coding: utf-8 -*-
"""

Utility functions for processing gait data.

@author: Jussi (jnu@iki.fi)
"""

from scipy import signal
from matplotlib import path
import matplotlib.pyplot as plt
import numpy as np
import logging
from itertools import product
from dataclasses import dataclass

from .envutils import GaitDataError
from .config import cfg
from .numutils import rising_zerocross, digitize_array, falling_zerocross, _baseline


logger = logging.getLogger(__name__)


@dataclass
class GaitEvent:
    """A gait event.

    Events are usually either foot strike or toeoff, but we also support a
    "general" event. Events can have a context: either right foot, left foot or
    None (mostly useful for general events).

    Events occur at a given frame. We use 0-based frame numbering. Thus, frames
    can directly be used to index data arrays (model data, marker data etc.)
    Note that due to this choice, gaitutils internal frame numbers differ from
    event frames shown in Nexus or C3D files. When data is read, the frames are
    automatically corrected for the Nexus or C3D offset. The offset is available
    in the Nexus or C3D metadata.

    Foot strike and toeoff events may occur on a forceplate. For such events,
    the forceplate_index can be set. Our internal forceplate index is also
    0-based, i.e. the first Nexus forceplate ("FP1" in Eclipse) is denoted by 0.
    """

    _event_types = ['strike', 'toeoff', 'general']  # supported event types
    _contexts = [None, 'L', 'R']  # supported context values
    frame: int  # the frame of occurence
    event_type: str  # the type of event
    context: str = None  # the context
    forceplate_index: int = None  # forceplate index

    def __post_init__(self):
        """Validate arguments"""
        if self.context not in GaitEvent._contexts:
            raise ValueError('Invalid context')
        if self.event_type not in GaitEvent._event_types:
            raise ValueError('Invalid event type')
        if not isinstance(self.frame, int):
            raise TypeError(f'Frame needs to be an int (not {type(self.frame)})')


class GaitEvents:
    """A collection of gait events (GaitEvent instances)"""

    def __init__(self):
        self._events = list()

    def __repr__(self) -> str:
        s = '<GaitEvents |\n'
        for ev in self._events:
            s += f'{ev.context} {ev.event_type} at {ev.frame}'
            if ev.forceplate_index is not None:
                s += f' (on forceplate FP{ev.forceplate_index + 1})'
            s += '\n'
        s += '>'
        return s

    def append(self, event):
        """Append a gait event.

        Parameters
        ----------
        event : GaitEvent
            The event to add.
        """
        if not isinstance(event, GaitEvent):
            raise ValueError('append() can only accept GaitEvent instances')
        self._events.append(event)
        self._events.sort(key=lambda ev: ev.frame)  # keep events sorted

    @staticmethod
    def _filter_context(events, context):
        for ev in events:
            if ev.context == context:
                yield ev

    @staticmethod
    def _filter_type(events, ev_type):
        for ev in events:
            if ev.event_type == ev_type:
                yield ev

    @staticmethod
    def _filter_forceplate(events):
        for ev in events:
            if ev.forceplate_index is not None:
                yield ev

    def get_events(self, event_type=None, context=None, forceplate=None):
        """Get desired events.

        Parameters
        ----------
        event_type : str | None
            The desired event type. If None, include all event types.
        context : str | None
            The desired context. If None, include all.
        forceplate : bool | None
            If True, get forceplate events only. If None, get all events.

        Returns
        -------
        list
            List of GaitEvent instances.
        """
        events = self._events
        if event_type is not None:
            events = self._filter_type(events, event_type)
        if context is not None:
            events = self._filter_context(events, context)
        if forceplate is not None:
            events = self._filter_forceplate(events)
        return list(events)

    def merge_forceplate_events(self, fp_events):
        """Read forceplate-based event info and update our events.

        Nexus and C3D events do not include any info about forceplates. Thus,
        forceplate contacts have to be detected separately. This method can be
        used to update events with information from forceplate detected events.
        A tolerance of FRAME_TOL is used to determine if the events are "the
        same".

        For example, if self.events includes a foot strike at frame 100 and
        fp_events has a foot strike on forceplate 0 at frame 101, the foot
        strike at frame 100 will be updated with the forceplate index.

        Parameters
        ----------
        fp_events : GaitEvents
            The forceplate events.
        """
        FRAME_TOL = 7
        for context in 'LR':
            for event_type in ['strike', 'toeoff']:
                events_this = self.get_events(event_type=event_type, context=context)
                fp_events_this = fp_events.get_events(event_type=event_type, context=context)
                for ev, fp_ev in product(events_this, fp_events_this):
                    if abs(ev.frame - fp_ev.frame) < FRAME_TOL:
                        # here we could correct the frame according to forceplate data
                        # ev.frame = fp_ev.frame
                        ev.forceplate_index = fp_ev.forceplate_index

    def get_forceplate_info(self, n_plates):
        """Return Eclipse-style forceplate info dict and a coded string.
        
        Parameters
        ----------
        n_plates : int
            Number of forceplates.

        Returns
        -------
        tuple
            A tuple of (fp_dict, fp_coded) where fp_dict contains Eclipse-style
            forceplate contact info. Example for three forceplates:
            {'FP1': 'Right', 'FP2': 'Invalid', 'FP3': 'Left'}
            fp_coded is the same info coded into a string, used by CGM2. 'X'
            marks invalid context. For the same data as the above dict it would
            be 'RXL'.
        """
        fp_dict = dict()
        coded = ''
        for ind in range(n_plates):
            strike_events = self.get_events(event_type='strike', forceplate=True)
            plate_strikes = [ev for ev in strike_events if ev.forceplate_index == ind]
            if plate_strikes:
                strike = plate_strikes[0]
                plate_context = 'Right' if strike.context == 'R' else 'Left'
                coded += strike.context
            else:
                plate_context = 'Invalid'
                coded += 'X'
            plate_name = f'FP{ind + 1}'  # Eclipse uses 1-based index
            fp_dict[plate_name] = plate_context
        return fp_dict, coded


def get_contexts(right_first=False):
    """Return the usual contexts and their names as pairs.

    Our default is to return left size first.
    """
    _contexts = [('L', 'Left'), ('R', 'Right')]
    if right_first:
        _contexts.reverse()
    return _contexts


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
    # XXX: could use cycles here, instead of iterating over foot strikes
    strike_frames = dict()
    for context in 'LR':
        strike_frames[context] = [
            ev.frame
            for ev in tr.events.get_events(event_type='strike', context=context)
        ]
    for context in 'LR':
        strikes = strike_frames[context]
        sw[context] = list()
        nstrikes = len(strikes)
        if nstrikes < 2:
            continue
        # contralateral vars
        context_co = 'L' if context == 'R' else 'R'
        strikes_co = strike_frames[context_co]
        mname = context + mkr
        mname_co = context_co + mkr
        for j, strike in enumerate(strikes):
            if strike == strikes[-1]:  # last strike on this context
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
                raise GaitDataError(f'Averaging data for {marker} has gaps')
            else:
                logger.warning(
                    f'marker {marker} cannot be included in average due to gaps'
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
    """PiG marker set as dict (empty values)"""
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
    for context in ['L', 'R']:
        # compare HEE-TOE line to pelvis orientation
        mkr_toe, mkr_hee = f'{context}TOE', f'{context}HEE'
        ht = _normalize(mkrdata[mkr_toe] - mkrdata[mkr_hee])
        if context + 'PSI' in mkrdata:
            pa = _normalize(mkrdata[context + 'ASI'] - mkrdata[context + 'PSI'])
        elif 'SACR' in mkrdata:
            pa = _normalize(mkrdata[context + 'ASI'] - mkrdata['SACR'])
        angs = np.arccos(np.sum(ht * pa, axis=1)) / np.pi * 180
        if np.nanmedian(angs) > MAX_ANGLE:
            yield mkr_toe, mkr_hee


def _principal_movement_direction(mdata):
    """Return principal movement direction (dimension of maximum variance).
    Used to find out whether gait occurs in the x- or y-dimension of lab frame.
    Returns 0 for x, 1 for y.
    """
    inds_ok = np.where(np.any(mdata, axis=1))  # make sure that gaps are ignored
    return np.argmax(np.var(mdata[inds_ok], axis=0))


def _get_foot_contact_vel(mkrdata, fp_events, medians=True, roi=None):
    """Return foot velocities during forceplate strike/toeoff frames.
    fp_events is output from detect_forceplate_events().
    If medians=True, return median values."""
    vels = dict()
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
        strikes = [
            ev.frame
            for ev in fp_events.get_events(event_type='strike', context=context)
        ]
        toeoffs = [
            ev.frame
            for ev in fp_events.get_events(event_type='toeoff', context=context)
        ]
        vels[context + '_strike'] = footctrv[strikes]
        vels[context + '_toeoff'] = footctrv[toeoffs]
    if medians:
        vels = {
            key: (np.array([np.median(x)]) if x.size > 0 else x)
            for key, x in vels.items()
        }
    return vels


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
        # a lot of zero entries (gaps) can throw off the median computation
        ha_len_nonzero = ha_len[np.where(ha_len > 0)]
        footlen = np.median(ha_len_nonzero) * cfg.autoproc.foot_relative_len
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
    pos_diff = np.diff(subj_pos, axis=0)[:, gait_dim]
    gait_dir = np.median(pos_diff[np.where(pos_diff != 0.0)])
    if gait_dir > 0:
        cmpfun = np.greater
    elif gait_dir < 0:
        cmpfun = np.less
    else:
        raise GaitDataError('cannot determine gait direction')
    lfoot = avg_markerdata(
        mkrdata, cfg.autoproc.left_foot_markers, roi=roi, fail_on_gaps=False
    )[:, gait_dim]
    rfoot = avg_markerdata(
        mkrdata, cfg.autoproc.right_foot_markers, roi=roi, fail_on_gaps=False
    )[:, gait_dim]
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
        vel_ = np.sqrt(np.sum(vel_3**2, 1))  # scalar velocity
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


def detect_forceplate_events(
    source, marker_data=None, fp_info=None, roi=None, return_nplates=False
):
    """Detect frames where valid forceplate strikes and toeoffs occur.
    Uses forceplate data and estimated foot shape.

    If supplied, marker_data must include foot and pelvis markers. Otherwise
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

    def _foot_plate_check(fpdata, marker_data, fr0, context, footlen):
        """Helper for foot-plate check.

        Returns 0, 1, 2 for: completely outside plate, partially outside plate,
        inside plate, respectively.
        """
        foot_points = _get_foot_points(marker_data, context, footlen)
        plate_corners = fpdata['plate_corners']
        logger.debug(f'{plate_corners=}')
        pts_ok = list()
        for label, pts in foot_points.items():
            foot_point = pts[fr0, :]
            logger.debug(f'{foot_point=}')
            pt_ok = _point_in_poly(plate_corners, foot_point)
            logger.debug(f"{label} point {'' if pt_ok else 'not '}on plate")
            pts_ok.append(pt_ok)
        if all(pts_ok):
            return 2
        elif any(pts_ok):
            return 1
        else:
            return 0

    def _threshold_forceplate(fp, bodymass=None):
        """Get candidate foot strike and toeoff frames by considering force only"""
        # apply median filter to remove spikes
        # XXX: kernel size should maybe depend on sampling freq?
        forcetot = signal.medfilt(fp['Ftot'], kernel_size=3)
        forcetot = _baseline(forcetot)
        fmaxind = np.argmax(forcetot)
        fmax = forcetot[fmaxind]
        logger.debug('peak force: %.2f N at sample %d' % (fmax, fmaxind))

        # find force threshold
        if bodymass is None:
            f_threshold = cfg.autoproc.forceplate_contact_threshold * fmax
            logger.warning(
                'body mass unknown, thresholding force at %.2f N', f_threshold
            )
        else:
            logger.debug(f'body mass {bodymass:.2f} kg')
            f_threshold = cfg.autoproc.forceplate_contact_threshold * bodymass * 9.81
            if fmax < cfg.autoproc.forceplate_min_weight * bodymass * 9.81:
                logger.debug('insufficient max. force on plate')
                force_checks_ok = False

        # find the indices around peak where force crosses threshold
        f_rising_inds = rising_zerocross(forcetot - f_threshold)
        f_falling_inds = falling_zerocross(forcetot - f_threshold)
        try:
            f_rising_ind = f_rising_inds[np.where(f_rising_inds < fmaxind)][-1]
            f_falling_ind = f_falling_inds[np.where(f_falling_inds > fmaxind)][0]
            logger.debug('force rise: %d fall: %d' % (f_rising_ind, f_falling_ind))
            # these are 0-based frame indices (=1 less than Nexus frame index)
            strike_fr = int(np.round(f_rising_ind / info['samplesperframe']))
            toeoff_fr = int(np.round(f_falling_ind / info['samplesperframe']))
            logger.debug(
                'foot strike at frame %d, toeoff at %d' % (strike_fr, toeoff_fr)
            )
            force_checks_ok = True
        except IndexError:
            logger.debug('cannot detect force rise/fall')
            force_checks_ok = False
            strike_fr, toeoff_fr = None, None
        return strike_fr, toeoff_fr, force_checks_ok

    def _context_from_eclipse(fp_info, plate):
        """Interpret context from Eclipse data.
        Returns tuple of (context, detect_context), where context is 'R', 'L'
        (or None for invalid/unknown) and detect_context indicates whether we
        should do our own autodetection.
        """
        context = None
        if fp_info is not None and plate in fp_info:
            eclipse_context = fp_info[plate]
            logger.debug(f'using Eclipse forceplate info: {eclipse_context}')
            if eclipse_context == 'Right':
                detect_context = False
                context = 'R'
            elif eclipse_context == 'Left':
                detect_context = False
                context = 'L'
            elif eclipse_context == 'Invalid':
                detect_context = False
            elif eclipse_context == 'Auto':
                detect_context = True
            else:
                raise GaitDataError('unexpected Eclipse forceplate field')
        else:
            logger.debug('not using Eclipse forceplate info')
            detect_context = True
        return context, detect_context

    from . import read_data

    logger.debug(f'detecting forceplate events from {source}')
    results = GaitEvents()

    # get subject info
    info = read_data.get_metadata(source)
    fpdata = read_data.get_forceplate_data(source)
    if cfg.autoproc.nexus_forceplate_devnames:
        logger.info(
            f'using configured plates: {cfg.autoproc.nexus_forceplate_devnames}'
        )
    if not fpdata:
        logger.warning('no forceplates')
        return results
    footlen = info['subj_params']['FootLen']
    rfootlen = info['subj_params']['RFootLen']
    lfootlen = info['subj_params']['LFootLen']
    if footlen is not None:
        logger.debug(f'(obsolete) single foot length parameter set to {footlen:.2f}')
        rfootlen = lfootlen = footlen
    elif rfootlen is not None and lfootlen is not None:
        logger.debug(
            f'foot length parameters set to r={rfootlen:.2f}, l={lfootlen:.2f}'
        )
    else:
        logger.debug('foot length parameter not set')
    bodymass = info['subj_params']['Bodymass']
    if marker_data is None:  # not supplied as parameter
        mkrs = (
            cfg.autoproc.right_foot_markers
            + cfg.autoproc.left_foot_markers
            + cfg.autoproc.track_markers
        )
        marker_data = read_data.get_marker_data(source, mkrs)

    datalen = marker_data[cfg.autoproc.track_markers[0]].shape[0]

    logger.debug('acquiring marker-based gait events')
    events_marker = automark_events(source, mkrdata=marker_data, roi=roi)

    # loop over the plates; our internal forceplate index is 0-based
    for plate_ind, fp in enumerate(fpdata):
        logger.debug('analyzing plate %d' % plate_ind)
        # XXX: are we sure that the plate indices always match Eclipse?
        plate = 'FP' + str(plate_ind + 1)  # Eclipse numbering starts from FP1
        context, detect_context = _context_from_eclipse(fp_info, plate)

        strike_fr, toeoff_fr, force_checks_ok = _threshold_forceplate(fp, bodymass)
        if not force_checks_ok:
            context = None

        # check foot markers (or points) to determine context and validity
        if force_checks_ok and detect_context:
            logger.debug('autodetecting context')
            # allows foot to settle for 50 ms after strike
            settle_fr = int(50 / 1000 * info['framerate'])
            fr0 = strike_fr + settle_fr
            # context is determined by leading foot at strike time
            this_context = _leading_foot(marker_data, roi=roi)[fr0]
            if this_context is None:
                raise GaitDataError('cannot determine leading foot from marker data')
            footlen = rfootlen if this_context == 'R' else lfootlen
            logger.debug(f'checking contact for leading foot: {this_context}')
            foot_contacts_ok = (
                _foot_plate_check(fp, marker_data, fr0, this_context, footlen) == 2
            )
            # to eliminate double contacts, check that contralateral foot is not on plate
            # this needs marker-based events
            if foot_contacts_ok and events_marker is not None:
                contra_context = 'R' if this_context == 'L' else 'L'
                contra_strikes = [
                    ev.frame
                    for ev in events_marker.get_events('strike', contra_context)
                ]
                contra_strikes = np.array(contra_strikes)
                contra_strikes_next = contra_strikes[
                    np.where(contra_strikes > strike_fr)
                ]
                if contra_strikes_next.size == 0:
                    logger.debug('no subsequent contralateral strike')
                else:
                    fr0 = contra_strikes_next[0] + settle_fr
                    if fr0 > datalen:  # data overrun
                        logger.debug('no subsequent contralateral strike (overrun)')
                    else:
                        logger.debug(
                            'checking the subsequent contralateral strike '
                            '(at frame %d)' % fr0
                        )
                        contra_next_ok = (
                            _foot_plate_check(
                                fp, marker_data, fr0, contra_context, footlen
                            )
                            == 0
                        )
                        foot_contacts_ok &= contra_next_ok
                contra_strikes_prev = contra_strikes[
                    np.where(contra_strikes < strike_fr)
                ]
                if contra_strikes_prev.size == 0:
                    logger.debug('no previous contralateral strike')
                else:
                    fr0 = contra_strikes_prev[-1] + settle_fr
                    logger.debug(
                        'checking previous contact for contralateral '
                        'foot (at frame %d)' % fr0
                    )
                    contra_prev_ok = (
                        _foot_plate_check(fp, marker_data, fr0, contra_context, footlen)
                        == 0
                    )
                    foot_contacts_ok &= contra_prev_ok
            context = this_context if foot_contacts_ok else None

        if context:
            logger.debug(
                'plate %d: valid foot strike on %s at frame %d'
                % (plate_ind, context, strike_fr)
            )
            strike_ev = GaitEvent(
                strike_fr, 'strike', context, forceplate_index=plate_ind
            )
            toeoff_ev = GaitEvent(
                toeoff_fr, 'toeoff', context, forceplate_index=plate_ind
            )
            results.append(strike_ev)
            results.append(toeoff_ev)
        else:
            logger.debug('plate %d: no valid foot strike' % plate_ind)
    if return_nplates:
        return results, len(fpdata)
    else:
        return results


def automark_events(
    source,
    mkrdata=None,
    events_range=None,
    vel_thresholds=None,
    roi=None,
    plot=False,
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
    vel_thresholds : dict, optional
        Absolute velocity thresholds for identifying events. These can be obtained
        from forceplate data (utils.check_forceplate_contact). If None, relative
        thresholds will be computed based on marker data.
    roi : array_like, optional
        If not None, specifies a ROI (in frames) inside which to mark events.
    plot : bool, optional
        Plot velocity curves and events using matplotlib. Mostly for debug purposes.
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

    events = GaitEvents()

    # loop: same operations for left / right foot
    for context, footctrP, footctrv in zip(
        ('R', 'L'), (rfootctrP, lfootctrP), (rfootctrv, lfootctrv)
    ):
        logger.debug(f'marking context {context}')
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
            'context: %s, default thresholds fall/rise: %.2f/%.2f'
            % (
                context,
                maxv * cfg.autoproc.strike_vel_threshold,
                maxv * cfg.autoproc.toeoff_vel_threshold,
            )
        )
        logger.debug(f'using thresholds: {threshold_fall_}/{threshold_rise_}')
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

        logger.debug(f'autodetected strike events: {strikes}')
        logger.debug(f'autodetected toeoff events: {toeoffs}')

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

        logger.debug(f'final strike events: {strikes}')
        logger.debug(f'final toeoff events: {toeoffs}')

        for fr in strikes:
            e = GaitEvent(int(fr), 'strike', context)
            events.append(e)

        for fr in toeoffs:
            e = GaitEvent(int(fr), 'toeoff', context)
            events.append(e)

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

    return events
