# -*- coding: utf-8 -*-
"""

Utility functions for processing gait data.

@author: Jussi (jnu@iki.fi)
"""


from read_data import get_marker_data, get_forceplate_data, get_metadata
from gaitutils import rising_zerocross, falling_zerocross
from scipy import signal
import numpy as np
import matplotlib.pyplot as plt


def get_center_frame(source, marker):
    """ Return frame where marker crosses x axis of coordinate system
    (y = 0) """
    mrkdata = get_marker_data(source, marker)
    P = mrkdata[marker + '_P']
    y = P[:, 1]
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
    if len(ycross) > 1:
        print('get_center_frame: multiple valid crossings detected')
        ycross = ycross[0]
    return ycross


def get_movement_direction(source, marker, dir):
    """ Return average direction of movement for given marker """
    dir = dir.lower()
    dir = {'x': 0, 'y': 1, 'z': 2}[dir]
    mrkdata = get_marker_data(source, marker)
    P = mrkdata[marker+'_P']
    ydiff = np.median(np.diff(P[:, dir]))  # median of y derivative
    return 1 if ydiff > 0 else -1


def kinetics_available(source):
    """ See whether the trial has valid forceplate contact (ground reaction
    forces available) for left/right side (or neither, or both).
    Uses forceplate data, gait events and marker positions.
    For now support for one forceplate only.
    Conditions:
    -check max total force, must correspond to subject weight
    -center of pressure must not change too much during contact time
    -heel & toe markers must not be outside plate edges at strike time
    Computes foot velocities at strike & toeoff.
    Return dict as:
    return {'context': kinetics, 'strike': strike_fr, 'strike_v': strike_v,
            'toeoff': toeoff_fr, 'toeoff_v': toeoff_v}
    """
    # get subject info
    info = get_metadata(source)
    subj_weight = info['bodymass'] * 9.81

    fp0 = get_forceplate_data(source)
    forcetot = signal.medfilt(fp0['ftot'])  # remove spikes

    # autodetection parameters
    F_THRESHOLD = .1 * subj_weight  # rise threshold
    FMAX_REL_MIN = .8  # maximum force as % of bodyweight must exceed this
    MAX_COP_SHIFT = 300  # maximum CoP shift (in x or y dir) in mm
    # time specified in seconds -> analog frames
    # FRISE_WINDOW = .05 * fp0['sfrate']
    # FMAX_MAX_DELAY = .95 * fp0['sfrate']
    # right feet markers
    RIGHT_FOOT_MARKERS = ['RHEE', 'RTOE', 'RANK']
    # left foot markers
    LEFT_FOOT_MARKERS = ['LHEE', 'LTOE', 'LANK']
    # forceplate boundaries in world coords
    FP_YMIN = 0
    FP_YMAX = 508
    FP_XMIN = 0
    FP_XMAX = 465
    # tolerance for toeoff in y dir
    Y_TOEOFF_TOL = 20
    # ankle marker tolerance in x dir
    X_ANKLE_TOL = 20

    emptydi = {'context': '', 'strike': None, 'strike_v': None,
               'toeoff': None, 'toeoff_v': None}

    fmax = max(forcetot)
    fmaxind = np.where(forcetot == fmax)[0][0]  # first maximum
    print('kinetics_available: max force:', fmax, 'at:', fmaxind,
          'weight:', subj_weight)
    if max(forcetot) < FMAX_REL_MIN * subj_weight:
        print('kinetics_available: insufficient max. force on plate')
        return emptydi
    # find indices where force crosses threshold
    try:
        friseind = rising_zerocross(forcetot-F_THRESHOLD)[0]  # first rise
        ffallind = falling_zerocross(forcetot-F_THRESHOLD)[-1]  # last fall
    except IndexError:
        print('kinetics_available: cannot detect force rise/fall')
        return emptydi
    # check shift of center of pressure during ROI; should not shift too much
    cop_roi = np.arange(friseind, ffallind)
    copx, copy = np.array(fp0['cop'][:, 0]), np.array(fp0['cop'][:, 1])
    copx_shift = np.max(copx[cop_roi]) - np.min(copx[cop_roi])
    copy_shift = np.max(copy[cop_roi]) - np.min(copy[cop_roi])
    if copx_shift > MAX_COP_SHIFT or copy_shift > MAX_COP_SHIFT:
        print('kinetics_available: center of pressure shifts too much',
              '(double contact?)')
        return emptydi

    # check: markers inside forceplate region during strike/toeoff
    strike_fr = int(np.round(friseind / fp0['samplesperframe']))
    toeoff_fr = int(np.round(ffallind / fp0['samplesperframe']))
    mrkdata = get_marker_data(source, RIGHT_FOOT_MARKERS + LEFT_FOOT_MARKERS)
    kinetics = None
    ok = True
    for marker in RIGHT_FOOT_MARKERS:
        marker += '_P'
        # ankle marker gets extra tolerance in x dir
        if marker == 'RANK_P':
            FP_XMIN_ = FP_XMIN - X_ANKLE_TOL
            FP_XMAX_ = FP_XMAX + X_ANKLE_TOL
        else:
            FP_XMIN_ = FP_XMIN
            FP_XMAX_ = FP_XMAX
        ok &= np.logical_and(mrkdata[marker][:, 0] > FP_XMIN,
                             mrkdata[marker][:, 0] < FP_XMAX)[strike_fr]
        ok &= np.logical_and(mrkdata[marker][:, 0] > FP_XMIN,
                             mrkdata[marker][:, 0] < FP_XMAX)[toeoff_fr]
        ok &= np.logical_and(mrkdata[marker][:, 1] > FP_YMIN,
                             mrkdata[marker][:, 1] < FP_YMAX)[strike_fr]
        ok &= np.logical_and(mrkdata[marker][:, 1] > FP_YMIN - Y_TOEOFF_TOL,
                             mrkdata[marker][:, 1] <
                             FP_YMAX + Y_TOEOFF_TOL)[toeoff_fr]
        if not ok:
            break
    if ok:
        kinetics = 'R'
    ok = True
    for marker in LEFT_FOOT_MARKERS:
        marker += '_P'
        if marker == 'LANK_P':
            FP_XMIN_ = FP_XMIN - X_ANKLE_TOL
            FP_XMAX_ = FP_XMAX + X_ANKLE_TOL
        else:
            FP_XMIN_ = FP_XMIN
            FP_XMAX_ = FP_XMAX
        ok &= np.logical_and(mrkdata[marker][:, 0] > FP_XMIN_,
                             mrkdata[marker][:, 0] < FP_XMAX_)[strike_fr]
        ok &= np.logical_and(mrkdata[marker][:, 0] > FP_XMIN_,
                             mrkdata[marker][:, 0] < FP_XMAX_)[toeoff_fr]
        ok &= np.logical_and(mrkdata[marker][:, 1] > FP_YMIN,
                             mrkdata[marker][:, 1] < FP_YMAX)[strike_fr]
        ok &= np.logical_and(mrkdata[marker][:, 1] > FP_YMIN - Y_TOEOFF_TOL,
                             mrkdata[marker][:, 1] <
                             FP_YMAX + Y_TOEOFF_TOL)[toeoff_fr]
        if not ok:
            break
    if ok:
        kinetics = 'L'

    if not kinetics:
        print('kinetics_available: markers off plate during strike/toeoff')
        return emptydi

    # kinetics ok, compute velocities at strike
    markers = RIGHT_FOOT_MARKERS if kinetics == 'R' else LEFT_FOOT_MARKERS
    footctrV = np.zeros(mrkdata[markers[0]+'_V'].shape)
    for marker in markers:
        footctrV += mrkdata[marker+'_V'] / len(markers)
    footctrv = np.sqrt(np.sum(footctrV[:, 1:3]**2, 1))
    strike_v = footctrv[int(strike_fr)]
    toeoff_v = footctrv[int(toeoff_fr)]
    print('kinetics_available: strike on %s at %d, toeoff at %d'
          % (kinetics, strike_fr, toeoff_fr))
    return {'context': kinetics, 'strike': strike_fr, 'strike_v': strike_v,
            'toeoff': toeoff_fr, 'toeoff_v': toeoff_v}


def automark_events(vicon, vel_thresholds={'L_strike': None, 'L_toeoff': None,
                    'R_strike': None, 'R_toeoff': None}, context=None,
                    strike_frame=None,
                    events_context=(0, 1), events_nocontext=(-1, 0, 1),
                    mark_window_hw=None, plot=False):
    """ Mark events based on velocity thresholding. Absolute thresholds
    can be specified as arguments. Otherwise relative thresholds will be
    calculated based on the data. Optimal results will be obtained when
    thresholds based on force plate data are available.

    vel_threshold gives velocity thresholds for identifying events. These
    can be obtained from forceplate data.

    context gives forceplate context for the trial: 'R', 'L', or None.
    strike_frame is the frame where forceplate contact occurs.

    events_context specified which events to mark for the side where forceplate
    strike occurs. For example (-1, 1) would mark one event before forceplate
    and one event after (forceplate strike event is always marked).
    events_nocontext is applied for the side where there is no forceplate
    contact.
    If plot=True, velocity curves and events are plotted.

    Before automark, run reconstruct, label and gap fill pipelines.
    """

    frate = vicon.GetFrameRate()
    if not frate:
        raise Exception('Cannot get framerate from Nexus')

    # relative thresholds (of maximum velocity)
    REL_THRESHOLD_FALL = .2
    REL_THRESHOLD_RISE = .5
    # marker data is assumed to be in mm
    # mm/frame = 1000 m/frame = 1000/frate m/s
    VEL_CONV = 1000/frate
    # reasonable limits for peak velocity (m/s before multiplier)
    MAX_PEAK_VELOCITY = 12 * VEL_CONV
    MIN_PEAK_VELOCITY = .5 * VEL_CONV
    # reasonable limits for velocity on slope (increasing/decreasing)
    MAX_SLOPE_VELOCITY = 6 * VEL_CONV
    MIN_SLOPE_VELOCITY = .05 * VEL_CONV
    # median prefilter width
    MEDIAN_WIDTH = 3
    # right feet markers
    RIGHT_FOOT_MARKERS = ['RHEE', 'RTOE', 'RANK']
    # left foot markers
    LEFT_FOOT_MARKERS = ['LHEE', 'LTOE', 'LANK']
    # tolerance between forceplate strike (parameter) and detected event
    FP_STRIKE_TOL = 7
    # marker for finding trial center frame
    TRACK_MARKER = 'LASI'

    # get subject info
    subjectnames = vicon.GetSubjectNames()
    if not subjectnames:
        raise ValueError('No subject defined in Nexus')
    subjectname = subjectnames[0]

    # get foot center velocity vectors and scalar velocities
    mrkdata = get_marker_data(vicon, RIGHT_FOOT_MARKERS+LEFT_FOOT_MARKERS)

    rfootctrV = np.zeros(mrkdata[RIGHT_FOOT_MARKERS[0]+'_V'].shape)
    for marker in RIGHT_FOOT_MARKERS:
        rfootctrV += mrkdata[marker+'_V'] / len(RIGHT_FOOT_MARKERS)
    rfootctrv = np.sqrt(np.sum(rfootctrV[:, 1:3]**2, 1))

    lfootctrV = np.zeros(mrkdata[LEFT_FOOT_MARKERS[0]+'_V'].shape)
    for marker in LEFT_FOOT_MARKERS:
        lfootctrV += mrkdata[marker+'_V'] / len(LEFT_FOOT_MARKERS)
    lfootctrv = np.sqrt(np.sum(lfootctrV[:, 1:3]**2, 1))

    strikes_all = {}
    toeoffs_all = {}

    # loop: same operations for left / right foot
    for ind, footctrv in enumerate((rfootctrv, lfootctrv)):
        this_side = 'R' if ind == 0 else 'L'
        print('automark: side ', this_side)
        # filter to scalar velocity data to suppress noise and spikes
        footctrv = signal.medfilt(footctrv, MEDIAN_WIDTH)

        # compute local maxima of velocity: derivative crosses zero, values ok
        vd = np.gradient(footctrv)
        vdz_ind = falling_zerocross(vd)
        inds = np.where(np.logical_and(footctrv[vdz_ind] > MIN_PEAK_VELOCITY,
                        footctrv[vdz_ind] < MAX_PEAK_VELOCITY))
        maxv = np.median(footctrv[vdz_ind[inds]])

        if maxv > MAX_PEAK_VELOCITY:
            raise ValueError('Velocity thresholds too high, data may be noisy')

        # compute thresholds
        threshold_fall_ = (vel_thresholds[this_side+'_strike'] or
                           maxv * REL_THRESHOLD_FALL)
        threshold_rise_ = (vel_thresholds[this_side+'_toeoff'] or
                           maxv * REL_THRESHOLD_RISE)

        print('automark: rel. thresholds: fall: %.2f rise %.2f' % (
            maxv * REL_THRESHOLD_FALL, maxv * REL_THRESHOLD_RISE))
        print('automark: using fall threshold: %s=%.2f' % (
            this_side, threshold_fall_))
        print('automark: using rise threshold: %s=%.2f' % (
            this_side, threshold_rise_))

        # find point where velocity crosses threshold
        # strikes (velocity decreases)
        cross = falling_zerocross(footctrv - threshold_fall_)
        # exclude edges of data vector
        cross = cross[np.where(np.logical_and(cross > 0,
                                              cross < (len(footctrv) - 1)))]
        cind_min = np.logical_and(footctrv[cross-1] < MAX_SLOPE_VELOCITY,
                                  footctrv[cross-1] > MIN_SLOPE_VELOCITY)
        cind_max = np.logical_and(footctrv[cross+1] < MAX_SLOPE_VELOCITY,
                                  footctrv[cross+1] > MIN_SLOPE_VELOCITY)
        strikes = cross[np.logical_and(cind_min, cind_max)]
        # toeoffs (velocity increases)
        cross = rising_zerocross(footctrv - threshold_rise_)
        cross = cross[np.where(np.logical_and(cross > 0,
                                              cross < len(footctrv)))]
        cind_min = np.logical_and(footctrv[cross-1] < MAX_SLOPE_VELOCITY,
                                  footctrv[cross-1] > MIN_SLOPE_VELOCITY)
        cind_max = np.logical_and(footctrv[cross+1] < MAX_SLOPE_VELOCITY,
                                  footctrv[cross+1] > MIN_SLOPE_VELOCITY)
        toeoffs = cross[np.logical_and(cind_min, cind_max)]

        # if fp data available, mark only events around forceplate strike
        if context and strike_frame:
            strikes_ = []
            if context == this_side:
                # find event corresponding to forceplate strike
                auto_strike_ind = np.argmin(abs(strikes - strike_frame))
                if abs(strikes[auto_strike_ind] -
                        strike_frame) > FP_STRIKE_TOL:
                    raise ValueError('Detected strike event does not match',
                                     'strike_frame')
                # add other events as required
                for fr in events_context:
                    if 0 <= auto_strike_ind + fr <= len(strikes) - 1:
                        strikes_.append(strikes[auto_strike_ind + fr])
            else:  # opposite side
                # find the next strike following the (opposite) fp strike
                diffv = strikes - strike_frame
                nextdiff = [x for x in diffv if x > 0][0]
                closest_next_ind = np.where(diffv == nextdiff)[0][0]
                for fr in events_nocontext:
                    if 0 <= closest_next_ind + fr <= len(strikes) - 1:
                        strikes_ += [strikes[closest_next_ind + fr]]
            strikes = strikes_
        # else mark around 'center frame' if specified
        elif mark_window_hw:
            ctr = get_center_frame(vicon, TRACK_MARKER)
            if not ctr:
                raise ValueError('Cannot find center frame (y crossing)')
            strikes = [fr for fr in strikes if abs(fr - ctr) <= mark_window_hw]
        # mark toeoffs that are between strike events
        toeoffs = [fr for fr in toeoffs
                   if any(strikes < fr) and any(strikes > fr)]

        # create the events in Nexus
        side_str = 'Right' if this_side == 'R' else 'Left'
        for fr in strikes:
                vicon.CreateAnEvent(subjectname, side_str,
                                    'Foot Strike', fr, 0.0)
        for fr in toeoffs:
                vicon.CreateAnEvent(subjectname, side_str, 'Foot Off', fr, 0.0)
        strikes_all[this_side] = strikes
        toeoffs_all[this_side] = toeoffs

        # plot velocities w/ thresholds
        if plot:
            if ind == 0:
                plt.figure()
            plt.subplot(2, 1, ind+1)
            plt.plot(footctrv, 'g', label='foot center velocity ' + this_side)
            # algorithm, fixed thresholds
            plt.plot(strikes, footctrv[strikes], 'kD', markersize=10,
                     label='strike')
            plt.plot(toeoffs, footctrv[toeoffs], 'k^', markersize=10,
                     label='toeoff')
            plt.legend(numpoints=1)
            plt.ylim(0, maxv+10)
            plt.xlabel('Frame')
            plt.ylabel('Velocity (mm/frame)')
            plt.title('Automark ' + this_side)

    return (strikes_all['R'], strikes_all['L'],
            toeoffs_all['R'], toeoffs_all['L'])
