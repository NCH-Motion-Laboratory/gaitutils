# -*- coding: utf-8 -*-
"""
Gaitplotter predefined plot layouts.

Created on Thu Aug 27 14:16:50 2015

@author: Jussi
"""

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
std_emg = [['RGlut', 'LGlut'],
           ['RHam', 'LHam'],
           ['RRec', 'LRec'],
           ['RVas', 'LVas'],
           ['RTibA', 'LTibA'],
           ['RPer', 'LPer'],
           ['RGas', 'LGas'],
           ['RSol', 'LSol']]

# kinetics + kinematics
std_kinall = std_kinematics + std_kinetics
# kin *overlay
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


""" Mixed layouts (EMG+model) for given side. These also return suitable height
ratios for plotting the rows (EMG plots can be a bit smaller in vertical size).
Example call:
layout, heightratios = kinetics_emg('R')

"""


# Kinetics-EMG. Will return EMG channels according to the given side
def kinetics_emg(side):
    return [['HipAnglesX', 'KneeAnglesX', 'AnkleAnglesX'],
            [side+'Ham', side+'Rec', side+'TibA'],
            [side+'Glut', side+'Vas', side+'Per'],
            ['HipMomentX', 'KneeMomentX', 'AnkleMomentX'],
            [side+'Rec', side+'Ham', side+'Gas'],
            [None, side+'Glut', side+'Sol'],
            [None, side+'Gas', None],
            ['HipPowerZ', 'KneePowerZ', 'AnklePowerZ']]


# Kinematics-only EMG. Will return EMG channels according to the given side
def kinematics_emg(side):
    return [['HipAnglesX', 'KneeAnglesX', 'AnkleAnglesX'],
            [side+'Ham', side+'Rec', side+'TibA'],
            [side+'Glut', side+'Vas', side+'Per'],
            [side+'Rec', side+'Ham', side+'Gas'],
            [None, side+'Glut', side+'Sol'],
            [None, side+'Gas', None]]















