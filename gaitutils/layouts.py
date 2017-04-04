# -*- coding: utf-8 -*-
"""
Handling layouts.

@author: Jussi
"""

from emg import EMG
import logging

logger = logging.getLogger(__name__)


def rm_dead_channels(source, layout):
    """ From EMG layout, remove rows with no functional channels """
    layout_ = list()
    emg = EMG(source)
    for j, row in enumerate(layout):
        if any([emg.status_ok(ch) for ch in row]):
            layout_.append(row)
    if not layout_:
        logger.warning('removed all - no valid EMG channels')
    return layout_
