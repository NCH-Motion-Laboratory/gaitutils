# -*- coding: utf-8 -*-
"""
Created on Thu Sep 03 14:54:34 2015

EMG consistency plot from Nexus. Automatically picks trials based on Eclipse
description and defined search strings.

@author: Jussi
"""

from gaitutils import Plotter, layouts, nexus, guiutils
import os.path as op

def enf2c3d(fname):
    enfstr = '.Trial.enf'
    if enfstr not in fname:
        raise ValueError('Filename is not a trial .enf')
    return fname.replace(enfstr, '.c3d')


MAX_TRIALS = 8

if not nexus.pid():
    guiutils.error_exit('Vicon Nexus not running')

# Eclipse trial notes/description must contain one of these strings
strs = ['R1', 'R2', 'R3', 'R4', 'L1', 'L2', 'L3', 'L4']

eclkeys = ['DESCRIPTION', 'NOTES']
marked_trials = list(nexus.find_trials(eclkeys, strs))

if len(marked_trials) > MAX_TRIALS:
    guiutils.error_exit('Too many marked trials found!')

if not marked_trials:
    # try to find anything marked with 'ok' (kinematics-only sessions)
    strs = ['ok']
    marked_trials = list(nexus.find_trials(eclkeys, strs))
    if not marked_trials:
        guiutils.error_exit('Did not find any marked trials in current '
                            'session directory.')

pl = Plotter()
pl.open_trial(enf2c3d(marked_trials[0]))
pl.layout = (layouts.overlay_kinetics if pl.trial.kinetics else
             layouts.overlay_kinematics)

print(pl.layout)

linecolors = ['b', 'g', 'r', 'c', 'm', 'y', 'k', 'pink']

for i, trialpath in enumerate(marked_trials):
    pl.open_trial(enf2c3d(marked_trials[i]))
    maintitle = ('Kinematics/kinetics consistency plot, '
                 'session %s' % pl.trial.trialdirname)
    pl.plot_trial(model_tracecolor=linecolors[i], maintitle=maintitle,
                  show=False)

pl.show()
pl.create_pdf('kin_consistency.pdf')
