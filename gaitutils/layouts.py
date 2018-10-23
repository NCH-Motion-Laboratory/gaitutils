# -*- coding: utf-8 -*-
"""
Handling layouts.

@author: Jussi (jnu@iki.fi)
"""

import logging

from gaitutils import cfg, GaitDataError

logger = logging.getLogger(__name__)


def rm_dead_channels(emg, layout):
    """ From EMG layout, remove rows with no valid EMG data """
    layout_ = list()
    for row in layout:
        if any([emg.status_ok(ch) for ch in row]):
            layout_.append(row)
        else:
            logger.debug('no valid data for %s, removed row' % str(row))
    if not layout_:
        logger.warning('removed all - no valid EMG channels')
    return layout_


def rm_dead_channels_multitrial(emgs, layout):
    """From layout, drop rows that do not have good data in any of the
    EMG() instances given """
    chs_ok = None
    for i, emg in enumerate(emgs):
        # accept channels w/ status ok, or anything that is NOT a
        # preconfigured EMG channel
        chs_ok_ = [ch not in cfg.emg.channel_labels or emg.status_ok(ch) for
                   row in layout for ch in row]
        # previously OK chs propagated as ok
        chs_ok = ([a or b for a, b in zip(chs_ok, chs_ok_)] if i > 0 else
                  chs_ok_)
    if not chs_ok:
        raise GaitDataError('No acceptable channels in any of the EMGs')
    rowlen = len(layout[0])
    lout = zip(*[iter(chs_ok)]*rowlen)  # grouper recipe from itertools
    rows_ok = [any(row) for row in lout]
    layout = [row for i, row in enumerate(layout) if rows_ok[i]]
    return layout


def onesided_layout(layout, side):
    """ Add 'R' or 'L' to layout variable names """
    if side not in ['R', 'L']:
        raise ValueError('Invalid side')
    return [[(side + item) if item is not None else None for item in row]
            for row in layout]


def filter_layout(layout, key, repl):
    """ Replace layout items """
    return [[repl if (item and key in item) else item for item in row]
            for row in layout]
