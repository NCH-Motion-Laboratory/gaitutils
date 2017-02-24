# -*- coding: utf-8 -*-
"""

Utility functions for processing gait data.

@author: Jussi (jnu@iki.fi)
"""

from read_data import get_marker_data, get_forceplate_data, get_metadata
from numutils import rising_zerocross, falling_zerocross, _baseline
from scipy import signal
from scipy.signal import medfilt
import numpy as np
import logging
import matplotlib.pyplot as plt

logger = logging.getLogger(__name__)


def get_crossing_frame(source, marker, dim=1, p0=0):
    """ Return frame(s) where marker position (dimension dim) crosses r0
    (units are as returned by Nexus, usually mm).
    Dims are x=0, y=1, z=2. """
    mrkdata = get_marker_data(source, marker)
    P = mrkdata[marker + '_P']
    y = P[:, dim]
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


def get_movement_direction(source, marker, dir):
    """ Return average direction of movement for given marker """
    dir = dir.lower()
    dir = {'x': 0, 'y': 1, 'z': 2}[dir]
    mrkdata = get_marker_data(source, marker)
    P = mrkdata[marker+'_P']
    ddiff = np.median(np.diff(P[:, dir]))  # median of derivative
    return 1 if ddiff > 0 else -1


def butter_filt(data, passband, sfreq, bord=5):
    """ Design a filter and forward-backward filter given data to
    passband, e.g. [1, 40].
    Passband is given in Hz. None for no filtering.
    Implemented as pure lowpass/highpass, if highpass/lowpass freq == 0
    """
    if passband is None:
        return data
    elif len(passband) != 2:
        raise Exception('Passband must be a vector of length 2')
    passbandn = 2 * np.array(passband) / sfreq
    if passbandn[0] == 0:  # lowpass
        b, a = signal.butter(bord, passbandn[1], btype='lowpass')
    elif passbandn[1] == 0:  # highpass
        b, a = signal.butter(bord, passbandn[1], btype='highpass')
    else:  # bandpass
        b, a = signal.butter(bord, passbandn, btype='bandpass')
    return signal.filtfilt(b, a, data)


def kinetics_available(source, check_weight=True, check_cop=True):
    """ See whether the trial has valid forceplate contact.
    Uses forceplate data and marker positions.

    Conditions:
    -check max total force, must correspond to subject weight
    (disable by check_weight=False)
    -center of pressure must not change too much during contact time
    (disable by check_cop=False)
    -foot markers must be inside plate edges at strike time

    Returns dict as:
    return {'context': context, 'strikes': strike_fr, 'toeoffs': toeoff_fr}
    
    """

    # autodetection parameters
    # TODO: move into config
    F_REL_THRESHOLD = .2  # force rise / fall threshold
    FMAX_REL_MIN = .8  # maximum force as % of bodyweight must exceed this
    MAX_COP_SHIFT = 300  # maximum CoP shift (in x or y dir) in mm
    # time specified in seconds -> analog frames
    # FRISE_WINDOW = .05 * fp0['sfrate']
    # FMAX_MAX_DELAY = .95 * fp0['sfrate']
    # right feet markers
    RIGHT_FOOT_MARKERS = ['RHEE', 'RTOE']
    # left foot markers
    LEFT_FOOT_MARKERS = ['LHEE', 'LTOE']
    # tolerance for toeoff in forward dir (mm)
    Y_TOEOFF_TOL = 20
    # ankle marker tolerance in perpendicular dir (mm)
    X_ANKLE_TOL = 20

    # get subject info
    info = get_metadata(source)

    fpdata = get_forceplate_data(source)

    results = {'context': '', 'strikes': None, 'toeoffs': None}
    results['strikes'] = {'R': [], 'L': []}
    results['toeoffs'] = {'R': [], 'L': []}

    for plate_ind, fp in enumerate(fpdata):
        logger.debug('analyzing plate %d' % plate_ind)
        # test the force data
        forcetot = signal.medfilt(fp['Ftot'])  # remove spikes
        forcetot = _baseline(forcetot)
        fmax = max(forcetot)
        fmaxind = np.where(forcetot == fmax)[0][0]  # first maximum
        logger.debug('max force: %.2f N at %.2f' % (fmax, fmaxind))
        bodymass = info['bodymass']
        if bodymass is None:
            f_threshold = F_REL_THRESHOLD * fmax
            logger.warning('body mass unknown, thresholding force at %.2f N',
                           f_threshold)
        else:
            logger.debug('body mass %.2f kg' % bodymass)
            f_threshold = F_REL_THRESHOLD * bodymass
            if check_weight:
                if fmax < FMAX_REL_MIN * bodymass * 9.81:
                    logger.debug('insufficient max. force on plate')
                    continue
            else:
                logger.debug('ignoring subject weight')
        # find indices where force crosses threshold
        try:
            logger.debug('force threshold: %.2f N' % f_threshold)
            friseind = rising_zerocross(forcetot-f_threshold)[0]  # first rise
            ffallind = falling_zerocross(forcetot-f_threshold)[-1]  # last fall
            logger.debug('force rise: %d fall: %d' % (friseind, ffallind))
        except IndexError:
            logger.debug('cannot detect force rise/fall')
            continue
        # check shift of center of pressure during roi
        # cop is here in plate coordinates, but it does not matter as we're
        # only looking for the magnitude of the shift
        if check_cop:
            cop_roi = np.arange(friseind, ffallind)
            copx, copy = np.array(fp['CoP'][:, 0]), np.array(fp['CoP'][:, 1])
            copx_shift = np.max(copx[cop_roi]) - np.min(copx[cop_roi])
            copy_shift = np.max(copy[cop_roi]) - np.min(copy[cop_roi])
            logger.debug('CoP x shift %.2f mm, y shift %.2f mm'
                         % (copx_shift, copy_shift))
            if copx_shift > MAX_COP_SHIFT or copy_shift > MAX_COP_SHIFT:
                logger.debug('center of pressure shifts too much '
                             '(double contact?)')
                continue
        else:
            logger.debug('ignoring center of pressure')

        # frame indices are 1-based so need to add 1 (what about c3d?)
        strike_fr = int(np.round(friseind / fp['samplesperframe'])) + 1
        toeoff_fr = int(np.round(ffallind / fp['samplesperframe'])) + 1
        logger.debug('strike %d, toeoff %d' % (strike_fr, toeoff_fr))

        mrkdata = get_marker_data(source, RIGHT_FOOT_MARKERS+LEFT_FOOT_MARKERS)
        this_valid = None

        # if we got here, force data looked ok; next, check marker data
        # first compute plate boundaries in world coords
        wR = fp['wR']
        wT = fp['wT']
        c = np.stack([fp['lowerbounds'], fp['upperbounds']])
        cw = np.dot(wR, c.T).T + wT
        mins = np.min(cw, axis=0)
        maxes = np.max(cw, axis=0)
        fp_xmax = maxes[0]
        fp_xmin = mins[0]
        fp_ymax = maxes[1]
        fp_ymin = mins[1]
        logger.debug('plate boundaries: x %.2f -> %.2f mm, y %.2f -> %.2f mm'
                     % (fp_xmin, fp_xmax, fp_ymin, fp_ymax))

        ok = True
        for marker in RIGHT_FOOT_MARKERS:
            marker += '_P'
            fp_xmin_ = fp_xmin
            fp_xmax_ = fp_xmax
            ok &= np.logical_and(mrkdata[marker][:, 0] > fp_xmin,
                                 mrkdata[marker][:, 0] < fp_xmax)[strike_fr]
            ok &= np.logical_and(mrkdata[marker][:, 0] > fp_xmin,
                                 mrkdata[marker][:, 0] < fp_xmax)[toeoff_fr]
            ok &= np.logical_and(mrkdata[marker][:, 1] > fp_ymin,
                                 mrkdata[marker][:, 1] < fp_ymax)[strike_fr]
            ok &= np.logical_and(mrkdata[marker][:, 1] > fp_ymin - Y_TOEOFF_TOL,
                                 mrkdata[marker][:, 1] <
                                 fp_ymax + Y_TOEOFF_TOL)[toeoff_fr]
            if not ok:
                logger.debug('marker %s failed on-plate check' % marker[:-2])
                break
        if ok:
            this_valid = 'R'

        ok = True
        for marker in LEFT_FOOT_MARKERS:
            marker += '_P'
            fp_xmin_ = fp_xmin
            fp_xmax_ = fp_xmax
            ok &= np.logical_and(mrkdata[marker][:, 0] > fp_xmin_,
                                 mrkdata[marker][:, 0] < fp_xmax_)[strike_fr]
            ok &= np.logical_and(mrkdata[marker][:, 0] > fp_xmin_,
                                 mrkdata[marker][:, 0] < fp_xmax_)[toeoff_fr]
            ok &= np.logical_and(mrkdata[marker][:, 1] > fp_ymin,
                                 mrkdata[marker][:, 1] < fp_ymax)[strike_fr]
            ok &= np.logical_and(mrkdata[marker][:, 1] > fp_ymin - Y_TOEOFF_TOL,
                                 mrkdata[marker][:, 1] <
                                 fp_ymax + Y_TOEOFF_TOL)[toeoff_fr]
            if not ok:
                logger.debug('marker %s failed on-plate check' % marker[:-2])
                break
        if ok:
            this_valid = 'L'

        if not this_valid:
            logger.debug('plate %d: markers off plate during strike/toeoff' %
                         plate_ind)
        else:
            logger.debug('plate %d: valid foot strike on %s at frame %d'
                         % (plate_ind, this_valid, strike_fr))
            if this_valid not in results['context']:
                results['context'] += this_valid
            results['strikes'][this_valid].append(strike_fr)
            results['toeoffs'][this_valid].append(toeoff_fr)

    logger.debug(results)
    return results
