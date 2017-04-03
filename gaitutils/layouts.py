# -*- coding: utf-8 -*-
"""
Predefined plot layouts.

Created on Thu Aug 27 14:16:50 2015

@author: Jussi
"""

from emg import EMG
import logging
from config import cfg

logger = logging.getLogger(__name__)


def rm_dead_channels(source, layout):
    """ From EMG layout, remove rows with no functional channels """
    layout_ = list()
    emg = EMG(source)
    for j, row in enumerate(layout):
        if all([emg.status_ok(ch) for ch in row]):
            layout_.append(row)
    if not layout_:
        logger.warning('removed all - no EMG channels active')
    return layout_

# kinetics + kinematics
std_kinall = cfg.layouts.std_kinematics + cfg.layouts.std_kinetics

# kin* overlays
# add legend to bottom row
overlay_kinall = list(std_kinall)
overlay_kinall.pop()
overlay_kinall.append(['model_legend', None, 'AnklePowerZ'])

overlay_kinematics = list(cfg.layouts.std_kinematics)
overlay_kinematics.append(['model_legend', None, None])

# EMG overlay - add legend
overlay_emg = list(cfg.layouts.std_emg)
overlay_emg.append(['emg_legend', None])

# kinetics overlay - add legend
overlay_kinetics = list(cfg.layouts.std_kinetics)
overlay_kinetics.append(['model_legend', None, None])


# Kinetics-EMG. Will return EMG channels according to the given side
def kinetics_emg(side):
    return [['HipAnglesX', 'KneeAnglesX', 'AnkleAnglesX'],
            [side+'Ham', side+'Rec', side+'TibA'],
            [side+'Glut', side+'Vas', side+'Per'],
            [side+'HipMomentX', side+'KneeMomentX', side+'AnkleMomentX'],
            [side+'Rec', side+'Ham', side+'Gas'],
            [None, side+'Glut', side+'Sol'],
            [None, side+'Gas', None],
            [side+'HipPowerZ', side+'KneePowerZ', side+'AnklePowerZ']]


# Kinematics-only EMG. Will return EMG channels according to the given side
def kinematics_emg(side):
    return [['HipAnglesX', 'KneeAnglesX', 'AnkleAnglesX'],
            [side+'Ham', side+'Rec', side+'TibA'],
            [side+'Glut', side+'Vas', side+'Per'],
            [side+'Rec', side+'Ham', side+'Gas'],
            [None, side+'Glut', side+'Sol'],
            [None, side+'Gas', None]]















