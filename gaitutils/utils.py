# -*- coding: utf-8 -*-
"""

Utility functions for processing gait data.

@author: Jussi (jnu@iki.fi)
"""

from __future__ import print_function
from read_data import get_marker_data, get_forceplate_data, get_metadata
from numutils import rising_zerocross, falling_zerocross
from scipy import signal
import numpy as np


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
    ddiff = np.median(np.diff(P[:, dir]))  # median of derivative
    return 1 if ddiff > 0 else -1


def kinetics_available(source, check_weight=True):
    """ See whether the trial has valid forceplate contact (ground reaction
    forces available) for left/right side.
    Uses forceplate data, gait events and marker positions.
    For now support for one forceplate only.
    TODO: evaluate all forceplates and return e.g. 'RL' when kinetics
    is available for both sides.
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
    # TODO: should be read from config / source
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
    if not check_weight:
        print('(ignoring subject weight)')
    elif max(forcetot) < FMAX_REL_MIN * subj_weight:
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
