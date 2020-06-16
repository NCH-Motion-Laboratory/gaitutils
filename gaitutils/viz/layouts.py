# -*- coding: utf-8 -*-
"""
layout handling

@author: Jussi (jnu@iki.fi)
"""

from builtins import str
from builtins import zip
import logging

from ..config import cfg
from ..envutils import GaitDataError

logger = logging.getLogger(__name__)


def get_layout(layout_name):
    """Get a layout from config.

    Parameters
    ----------
    layout_name : str
        Name of layout.

    Returns
    -------
    list
        The layout.
    """
    # our default layout is PiG lower body kinematics
    if layout_name is None:
        layout_name = 'lb_kinematics'
    try:
        return getattr(cfg.layouts, layout_name)
    except AttributeError:
        raise GaitDataError('No such layout %s' % layout_name)


def _check_layout(layout):
    """Check consistency of layout.
    
    Returns a tuple (n_of_rows, n_of_cols) if layout is ok.
    Otherwise raises a TypeError.
    """
    if not layout:
        raise TypeError('Empty plotting layout: %s. If EMG layout, check that channels are ok.' % layout)
    if not isinstance(layout, list):
        raise TypeError('Invalid plotting layout')
    if not isinstance(layout[0], list):
        raise TypeError('Invalid plotting layout')
    nrows = len(layout)
    ncols = len(layout[0])
    if ncols < 1:
        raise TypeError('Invalid plotting layout: %s' % layout)
    for col in layout:
        if not isinstance(col, list) or len(col) != ncols:
            raise TypeError('Inconsistent plotting layout: %s' % layout)
    return nrows, ncols


def _rm_dead_channels(emgs, layout):
    """From EMG layout, remove rows that do not have any good data"""
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
