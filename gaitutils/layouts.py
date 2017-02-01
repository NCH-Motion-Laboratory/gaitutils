# -*- coding: utf-8 -*-
"""
Predefined plot layouts.

Created on Thu Aug 27 14:16:50 2015

@author: Jussi
"""

from emg import EMG


def rm_dead_channels(source, layout):
    """ Remove non-functional EMG channels from a layout """
    layout_ = list()
    emg = EMG(source)
    for j, row in enumerate(layout):
        print row
        if all([emg.status_ok(ch) for ch in row]):
            layout_.append(row)
    return layout_

# online kinematics plot
std_kinematics = [['PelvisAnglesX', 'PelvisAnglesY', 'PelvisAnglesZ'],
                  ['HipAnglesX', 'HipAnglesY', 'HipAnglesZ'],
                  ['KneeAnglesX', 'KneeAnglesY', 'KneeAnglesZ'],
                  ['AnkleAnglesX', 'FootProgressAnglesZ', 'AnkleAnglesZ']]

# online kinetics plot
std_kinetics = [['HipMomentX', 'HipMomentY', 'HipMomentZ'],
                ['HipPowerZ', 'KneeMomentX', 'KneeMomentY'],
                ['KneeMomentZ', 'KneePowerZ', 'AnkleMomentX'],
                [None, None, 'AnklePowerZ']]

# muscle lengths
std_musclelen = [['PsoaLength', 'GracLength', 'ReFeLength'],
                 ['BiFLLength', 'SeTeLength', 'SeMeLength'],
                 ['MeGaLength', 'LaGaLength', 'SoleLength']]

# EMG only
std_emg = [['LGlut', 'RGlut'],
           ['LHam', 'RHam'],
           ['LRec', 'RRec'],
           ['LVas', 'RVas'],
           ['LTibA', 'RTibA'],
           ['LPer', 'RPer'],
           ['LGas', 'RGas'],
           ['LSol', 'RSol']]

std_emg_left = [[None, 'LGlut'],
                [None, 'LHam'],
                [None, 'LRec'],
                [None, 'LVas'],
                [None, 'LTibA'],
                [None, 'LPer'],
                [None, 'LGas'],
                [None, 'LSol']]

std_emg_right = [['RGlut', None],
                 ['RHam', None],
                 ['RRec', None],
                 ['RVas', None],
                 ['RTibA', None],
                 ['RPer', None],
                 ['RGas', None],
                 ['RSol', None]]


# kinetics + kinematics
std_kinall = std_kinematics + std_kinetics

# kin* overlays
# add legend to bottom row
overlay_kinall = list(std_kinall)
overlay_kinall.pop()
overlay_kinall.append(['model_legend', None, 'AnklePowerZ'])

overlay_kinematics = list(std_kinematics)
overlay_kinematics.append(['model_legend', None, None])

# EMG overlay - add legend
overlay_emg = list(std_emg)
overlay_emg.append(['emg_legend', None])

# kinetics overlay - add legend
overlay_kinetics = list(std_kinetics)
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















