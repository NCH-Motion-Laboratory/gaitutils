# -*- coding: utf-8 -*-
"""
Created on Thu Sep 03 14:54:34 2015

EMG consistency plot from Nexus. Automatically picks trials based on Eclipse
description and defined search strings.

@author: Jussi
"""

from gaitutils import Plotter, layouts, nexus
from gaitutils.nexus import enf2c3d, find_trials
from gaitutils.guiutils import error_exit

MAX_TRIALS = 8

if not nexus.pid():
    error_exit('Vicon Nexus not running')

# Eclipse trial notes/description must contain one of these strings
strs = ['R1', 'R2', 'R3', 'R4', 'L1', 'L2', 'L3', 'L4']

eclkeys = ['DESCRIPTION', 'NOTES']
marked_trials = list(find_trials(eclkeys, strs))


if not marked_trials:
    # try to find anything marked with 'ok' (kinematics-only sessions)
    strs = ['ok']
    marked_trials = list(find_trials(eclkeys, strs))
    if not marked_trials:
        error_exit('Did not find any marked trials in current '
                   'session directory.')

if len(marked_trials) > MAX_TRIALS:
    error_exit('Too many marked trials found!')

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
    pl.plot_trial(model_tracecolor=linecolors[i], linestyles_context=True,
                  maintitle=maintitle, show=False)

pl.show()
pl.create_pdf('kin_consistency.pdf')
