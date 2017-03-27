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

from config import cfg

logger = logging.getLogger(__name__)


def get_crossing_frame(source, marker, dim=1, p0=0):
    """ Return frame(s) where marker position (dimension dim) crosses p0
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
    """ Return direction of movement (negative/positive)
    for given marker and movement direction """
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


def principal_movement_direction(source, markers):
    """ Return principal movement direction """
    mrkdata = get_marker_data(source, markers)
    pos = sum([mrkdata[name+'_P'] for name in markers])
    fwd_dir = np.argmax(np.var(pos, axis=0))
    return fwd_dir


def detect_forceplate_events(source, check_weight=True, check_cop=True):
    """ See whether the trial has valid forceplate contact.
    Uses forceplate data and marker positions.

    Conditions:
    -check max total force, must correspond to subject weight
    (disable by check_weight=False)
    -center of pressure must not change too much during contact time
    (disable by check_cop=False)
    -foot markers must be inside plate edges at strike time

    Returns dict with keys R_strikes, L_strikes, R_toeoffs, L_toeoffs:
    lists of frames where valid forceplate contact occurs for each event

    """

    # get subject info
    info = get_metadata(source)
    fpdata = get_forceplate_data(source)

    results = dict()
    results['R_strikes'] = []
    results['R_toeoffs'] = []
    results['L_strikes'] = []
    results['L_toeoffs'] = []
    results['valid'] = ''

    # get marker data and find "forward" direction
    mrkdata = get_marker_data(source, cfg.autoproc.right_foot_markers +
                              cfg.autoproc.left_foot_markers)
    pos = sum([mrkdata[name+'_P'] for name in
               cfg.autoproc.left_foot_markers+cfg.autoproc.right_foot_markers])
    fwd_dir = np.argmax(np.var(pos, axis=0))
    orth_dir = 0 if fwd_dir == 1 else 1
    logger.debug('gait forward direction seems to be %s' %
                 {0: 'x', 1: 'y', 2: 'z'}[fwd_dir])

    for plate_ind, fp in enumerate(fpdata):
        logger.debug('analyzing plate %d' % plate_ind)
        # test the force data
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
            f_threshold = cfg.autoproc.forceplate_contact_threshold * bodymass
            if check_weight:
                if fmax < cfg.autoproc.forceplate_min_weight * bodymass * 9.81:
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
        # check shift of center of pressure during roi in fwd dir
        if check_cop:
            cop_roi = fp['CoP'][friseind:ffallind, fwd_dir]
            cop_shift = cop_roi.max() - cop_roi.min()
            total_shift = np.sqrt(np.sum(cop_shift**2))
            logger.debug('CoP total shift %.2f mm' % total_shift)
            if total_shift > cfg.autoproc.cop_shift_max:
                logger.debug('center of pressure shifts too much '
                             '(double contact?)')
                continue
        else:
            logger.debug('ignoring center of pressure')

        # we work with 0-based frame indices (=1 less than Nexus frame index)
        strike_fr = int(np.round(friseind / info['samplesperframe']))
        toeoff_fr = int(np.round(ffallind / info['samplesperframe']))
        logger.debug('strike @ frame %d, toeoff @ %d' % (strike_fr, toeoff_fr))

        # if we got here, force data looked ok; next, check marker data
        # first compute plate boundaries in world coords
        mins = fp['lowerbounds']
        maxes = fp['upperbounds']

        # check markers
        this_valid = None
        for markers in [cfg.autoproc.right_foot_markers,
                        cfg.autoproc.left_foot_markers]:
            ok = True
            for marker_ in markers:
                mins_s, maxes_s = mins.copy(), maxes.copy()
                mins_t, maxes_t = mins.copy(), maxes.copy()
                # extra tolerance for ankle marker in sideways direction
                if 'ANK' in marker_:
                    mins_t[orth_dir] -= cfg.autoproc.ankle_sideways_tol
                    maxes_t[orth_dir] += cfg.autoproc.ankle_sideways_tol
                    mins_s[orth_dir] -= cfg.autoproc.ankle_sideways_tol
                    maxes_s[orth_dir] += cfg.autoproc.ankle_sideways_tol
                # extra tolerance for all markers in gait direction @ toeoff
                maxes_t[fwd_dir] += cfg.autoproc.toeoff_marker_tol
                mins_t[fwd_dir] -= cfg.autoproc.toeoff_marker_tol
                marker = marker_ + '_P'
                ok &= mins_s[0] < mrkdata[marker][strike_fr, 0] < maxes_s[0]
                ok &= mins_s[1] < mrkdata[marker][strike_fr, 1] < maxes_s[1]
                if not ok:
                    logger.debug('marker %s failed on-plate check during foot '
                                 'strike' % marker_)
                    break
                ok &= mins_t[0] < mrkdata[marker][toeoff_fr, 0] < maxes_t[0]
                ok &= mins_t[1] < mrkdata[marker][toeoff_fr, 1] < maxes_t[1]
                if not ok:
                    logger.debug('marker %s failed on-plate check during '
                                 'toeoff ' % marker_)
                    break
            if ok:
                if this_valid:
                    raise Exception('valid contact on both feet, how come?')
                this_valid = ('R' if markers == cfg.autoproc.right_foot_markers
                              else 'L')
                logger.debug('on-plate check ok for side %s' % this_valid)

        if not this_valid:
            logger.debug('plate %d: no valid foot strike' % plate_ind)
        else:
            logger.debug('plate %d: valid foot strike on %s at frame %d'
                         % (plate_ind, this_valid, strike_fr))
            if this_valid not in results['valid']:
                results['valid'] += this_valid
            results[this_valid+'_strikes'].append(strike_fr)
            results[this_valid+'_toeoffs'].append(toeoff_fr)
    logger.debug(results)
    return results


def get_foot_velocity(source, fp_events, medians=True):
    """ Return foot velocities during forceplate strike/toeoff frames.
    fp_events is from detect_forceplate_events()
    If medians=True, return median values. """
    mrkdata = get_marker_data(source, cfg.autoproc.right_foot_markers +
                              cfg.autoproc.left_foot_markers)
    results = dict()
    for context, markers in zip(('R', 'L'), [cfg.autoproc.right_foot_markers,
                                cfg.autoproc.left_foot_markers]):
        # average velocities for different markers
        footctrV = np.zeros(mrkdata[markers[0]+'_V'].shape)
        for marker in markers:
            footctrV += mrkdata[marker+'_V'] / float(len(markers))
        # scalar velocity
        footctrv = np.sqrt(np.sum(footctrV**2, 1))
        strikes = fp_events[context+'_strikes']
        toeoffs = fp_events[context+'_toeoffs']
        results[context + '_strike'] = footctrv[strikes]
        results[context + '_toeoff'] = footctrv[toeoffs]
    if medians:
        results = {key: (np.array([np.median(x)]) if x.size > 0 else x)
                   for key, x in results.items()}
    return results
