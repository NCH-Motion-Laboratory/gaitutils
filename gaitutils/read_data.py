# -*- coding: utf-8 -*-
"""

Wrapper methods that read from either Vicon Nexus or c3d files.

@author: jnu@iki.fi



"""

from __future__ import print_function
import nexus, c3d
from nexus import is_vicon_instance
from c3d import is_c3dfile


def reader_module(source):
    """ Determine the appropriate module to use """
    if is_vicon_instance(source):
        return nexus
    elif is_c3dfile(source):
        return c3d
    else:
        raise ValueError('Unknown source')


def get_forceplate_data(source):
    return reader_module(source).get_forceplate_data(source)


def get_marker_data(source, markers):
    return reader_module(source).get_marker_data(source, markers)


def kinetics_available(source):
    return reader_module(source).kinetics_available(source)




def get_roi(vicon):
    return reader_module(source).get_marker_data(source, markers)






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

        print('automark: rel. thresholds: fall: %.2f rise %.2f' % (maxv * REL_THRESHOLD_FALL, maxv * REL_THRESHOLD_RISE))
        print('automark: using fall threshold: %s=%.2f' % (this_side, threshold_fall_))
        print('automark: using rise threshold: %s=%.2f' % (this_side, threshold_rise_))

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
