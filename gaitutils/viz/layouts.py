# -*- coding: utf-8 -*-
"""
layout handling

@author: Jussi (jnu@iki.fi)
"""

from builtins import str
from builtins import zip
import logging

from .. import cfg, GaitDataError

logger = logging.getLogger(__name__)


def get_layout(layout_name):
    """Get layout from config"""
    # default layout is lower body kinematics
    if layout_name is None:
        layout_name = 'lb_kinematics'
    try:
        return getattr(cfg.layouts, layout_name)
    except AttributeError:
        raise GaitDataError('No such layout %s' % layout_name)


def check_layout(layout):
    """Check layout consistency. Return tuple (n_of_rows, n_of_cols)"""
    if not layout or not isinstance(layout, list):
        raise TypeError('Invalid layout')
    if not isinstance(layout[0], list):
        raise TypeError('Invalid layout')
    nrows = len(layout)
    ncols = len(layout[0])
    if ncols < 1:
        raise TypeError('Invalid layout: %s' % layout)
    for col in layout:
        if not isinstance(col, list) or len(col) != ncols:
            raise TypeError('Inconsistent layout: %s' % layout)
    return nrows, ncols


def rm_dead_channels(emgs, layout):
    """From layout, drop rows that do not have good data in any of the
    EMG() instances given """
    if not isinstance(emgs, list):
        emgs = [emgs]
    chs_ok = None
    for i, emg in enumerate(emgs):
        # accept channels w/ status ok, or anything that is NOT a
        # preconfigured EMG channel
        chs_ok_ = [
            ch not in cfg.emg.channel_labels or emg.status_ok(ch)
            for row in layout
            for ch in row
        ]
        # previously OK chs propagated as ok
        chs_ok = [a or b for a, b in zip(chs_ok, chs_ok_)] if i > 0 else chs_ok_
    if not chs_ok:
        raise GaitDataError('No acceptable channels in any of the EMGs')
    rowlen = len(layout[0])
    lout = list(zip(*[iter(chs_ok)] * rowlen))  # grouper recipe from itertools
    rows_ok = [any(row) for row in lout]
    layout = [row for i, row in enumerate(layout) if rows_ok[i]]
    return layout
