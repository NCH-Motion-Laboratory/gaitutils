# -*- coding: utf-8 -*-
"""

Utility functions for processing gait data.

@author: Jussi (jnu@iki.fi)
"""

from scipy import signal
import numpy as np
import logging
from .envutils import GaitDataError

from .numutils import rising_zerocross, falling_zerocross, _baseline
from .config import cfg

logger = logging.getLogger(__name__)


def get_crossing_frame(source, marker, dim=1, p0=0):
    """ Return frame(s) where marker position (dimension dim) crosses p0
    (units are as returned by Nexus, usually mm).
    Dims are x=0, y=1, z=2. """
    from . import read_data
    mrkdata = read_data.get_marker_data(source, marker)
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
    from . import read_data
    dir = dir.lower()
    dir = {'x': 0, 'y': 1, 'z': 2}[dir]
    mrkdata = read_data.get_marker_data(source, marker)
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
        raise ValueError('Passband must be a vector of length 2')
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
    from . import read_data
    mrkdata = read_data.get_marker_data(source, markers)
    pos = sum([mrkdata[name+'_P'] for name in markers])
    fwd_dir = np.argmax(np.var(pos, axis=0))
    return fwd_dir


def detect_forceplate_events(source, fp_info=None):
    """ Detect frames where valid forceplate strikes and toeoffs occur.
    Uses forceplate data and marker positions.

    If fp_info dict is set, no marker and COP checks will be done;
    instead the Eclipse forceplate info will be used. Eclipse info is written
    e.g. as {FP1: 'Left'} where plate indices start from 1 and the value can be
    'Left', 'Right' or 'Invalid'. Even if Eclipse info is used, the foot strike
    and toeoff frames must be determined from forceplate data.

    Conditions:
    -check max total force, must correspond to subject weight
    -center of pressure must not change too much during contact time
    -foot markers must be inside plate edges at strike time

    Returns dict with keys R_strikes, L_strikes, R_toeoffs, L_toeoffs.
    Dict values are lists of frames where valid forceplate contact occurs.
    """

    # get subject info
    logger.debug('detect forceplate events from %s' % source)
    from . import read_data
    info = read_data.get_metadata(source)
    fpdata = read_data.get_forceplate_data(source)

    results = dict()
    results['R_strikes'] = []
    results['R_toeoffs'] = []
    results['L_strikes'] = []
    results['L_toeoffs'] = []
    results['valid'] = ''

    # get marker data and find "forward" direction (by max variance)
    mrkdata = read_data.get_marker_data(source, cfg.autoproc.right_foot_markers +
                                        cfg.autoproc.left_foot_markers)
    pos = sum([mrkdata[name+'_P'] for name in
               cfg.autoproc.left_foot_markers+cfg.autoproc.right_foot_markers])
    fwd_dir = np.argmax(np.var(pos, axis=0))
    orth_dir = 0 if fwd_dir == 1 else 1
    logger.debug('gait forward direction seems to be %s' %
                 {0: 'x', 1: 'y', 2: 'z'}[fwd_dir])

    for plate_ind, fp in enumerate(fpdata):
        # first identify candidates for footstrike by looking at fp data
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
            f_threshold = (cfg.autoproc.forceplate_contact_threshold *
                           bodymass * 9.81)
            if fmax < cfg.autoproc.forceplate_min_weight * bodymass * 9.81:
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

        # confirm whether it's a valid foot strike; look at Eclipse info or
        # use our own autodetection routine
        detect = True
        plate = 'FP' + str(plate_ind+1)
        if fp_info is not None and plate in fp_info:
            # TODO: are we sure that the plate indices match Eclipse?
            valid = fp_info[plate]
            detect = False
            logger.debug('using Eclipse forceplate info: %s' % valid)
            if valid == 'Right':
                this_valid = 'R'
            elif valid == 'Left':
                this_valid = 'L'
            elif valid == 'Invalid':
                this_valid = None
            elif valid == 'Auto':
                detect = True
            else:
                raise Exception('unexpected Eclipse forceplate field')

        if detect:
            logger.debug('using autodetection')
            # check shift of center of pressure during roi in fwd dir
            cop_roi = fp['CoP'][friseind:ffallind, fwd_dir]
            cop_shift = cop_roi.max() - cop_roi.min()
            total_shift = np.sqrt(np.sum(cop_shift**2))
            logger.debug('CoP total shift %.2f mm' % total_shift)
            if total_shift > cfg.autoproc.cop_shift_max:
                logger.debug('center of pressure shifts too much '
                             '(double contact?)')
                continue

            # first compute plate boundaries in world coords
            mins = fp['lowerbounds']
            maxes = fp['upperbounds']

            # check markers
            this_valid = None
            for side, markers in zip(['R', 'L'],
                                     [cfg.autoproc.right_foot_markers,
                                      cfg.autoproc.left_foot_markers]):
                logger.debug('checking forceplate contact for side %s' % side)

                # check foot height at toeoff
                data_shape = mrkdata[markers[0]+'_P'].shape
                footctrP = np.zeros(data_shape)
                for marker in markers:
                    footctrP += mrkdata[marker+'_P'] / len(markers)
                foot_h = footctrP[:, 2]
                min_h = foot_h[np.nonzero(foot_h)].min()
                rel_h = footctrP[toeoff_fr, 2] / min_h
                logger.debug('toeoff rel. height: %.2f' % rel_h)
                if (rel_h < cfg.autoproc.toeoff_rel_height):
                    logger.debug('toeoff height too low')
                    ok = False
                    continue
                else:
                    ok = True

                # individual marker checks
                for marker_ in markers:
                    logger.debug('checking %s' % marker_)
                    mins_s, maxes_s = mins.copy(), maxes.copy()
                    mins_t, maxes_t = mins.copy(), maxes.copy()
                    # extra tolerance for ankle marker in sideways direction
                    if 'ANK' in marker_:
                        mins_t[orth_dir] -= cfg.autoproc.ankle_sideways_tol
                        maxes_t[orth_dir] += cfg.autoproc.ankle_sideways_tol
                        mins_s[orth_dir] -= cfg.autoproc.ankle_sideways_tol
                        maxes_s[orth_dir] += cfg.autoproc.ankle_sideways_tol
                    # extra tol for all markers in gait direction @ toeoff
                    maxes_t[fwd_dir] += cfg.autoproc.toeoff_marker_tol
                    mins_t[fwd_dir] -= cfg.autoproc.toeoff_marker_tol
                    # extra tol for heel marker in gait dir during foot strike
                    if 'HEE' in marker_:
                        maxes_s[fwd_dir] += cfg.autoproc.heel_strike_tol
                        mins_s[fwd_dir] -= cfg.autoproc.heel_strike_tol
                    marker = marker_ + '_P'
                    ok &= (mins_s[0] < mrkdata[marker][strike_fr, 0] <
                           maxes_s[0])
                    ok &= (mins_s[1] < mrkdata[marker][strike_fr, 1] <
                           maxes_s[1])
                    if not ok:
                        logger.debug('marker %s failed on-plate check during '
                                     'foot strike' % marker_)
                        break
                    ok &= (mins_t[0] < mrkdata[marker][toeoff_fr, 0] <
                           maxes_t[0])
                    ok &= (mins_t[1] < mrkdata[marker][toeoff_fr, 1] <
                           maxes_t[1])
                    if not ok:
                        logger.debug('marker %s failed on-plate check during '
                                     'toeoff ' % marker_)
                        break

                if ok:
                    if this_valid:
                        raise GaitDataError('valid contact on both feet (?)')
                    this_valid = side
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
    from . import read_data
    mrkdata = read_data.get_marker_data(source, cfg.autoproc.right_foot_markers +
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
