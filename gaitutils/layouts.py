# -*- coding: utf-8 -*-
"""
Handling layouts.

@author: Jussi
"""
import logging


logger = logging.getLogger(__name__)


def rm_dead_channels(source, emg, layout):
    """ From EMG layout, remove rows with no valid EMG data """
    layout_ = list()
    for j, row in enumerate(layout):
        if any([emg.status_ok(ch) for ch in row]):
            layout_.append(row)
        else:
            logger.debug('no valid data for %s, removed row' % str(row))
    if not layout_:
        logger.warning('removed all - no valid EMG channels')
    return layout_


def onesided_layout(layout, side):
    """ Add 'R' or 'L' to layout variable names """
    if side not in ['R', 'L']:
        raise ValueError('Invalid side')
    return [[side + item for item in row] for row in layout]
