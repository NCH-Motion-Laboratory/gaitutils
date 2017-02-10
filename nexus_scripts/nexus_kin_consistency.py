# -*- coding: utf-8 -*-
"""
Created on Thu Sep 03 14:54:34 2015

EMG consistency plot from Nexus. Automatically picks trials based on Eclipse
description and defined search strings.

@author: Jussi
"""

from gaitutils import Plotter, layouts, register_gui_exception_handler
from gaitutils.nexus import enf2c3d, find_trials

import logging
logging.basicConfig(level=logging.DEBUG)


def do_plot():

    MAX_TRIALS = 8

    # Eclipse trial notes/description must contain one of these strings
    strs = ['R1', 'R2', 'R3', 'R4', 'L1', 'L2', 'L3', 'L4']

    eclkeys = ['DESCRIPTION', 'NOTES']
    marked_trials = list(find_trials(eclkeys, strs))

    if not marked_trials:
        # try to find anything marked with 'ok' (kinematics-only sessions)
        marked_trials = list(find_trials(eclkeys, strs))
        if not marked_trials:
            raise Exception('Did not find any marked trials in current '
                            'session directory')

    if len(marked_trials) > MAX_TRIALS:
        raise Exception('Too many marked trials found!')

    pl = Plotter()
    pl.open_trial(enf2c3d(marked_trials[0]))
    pl.layout = (layouts.overlay_kinetics if pl.trial.kinetics else
                 layouts.overlay_kinematics)

    linecolors = ['b', 'g', 'r', 'c', 'm', 'y', 'k', 'pink']

    for i, trialpath in enumerate(marked_trials):
        pl.open_trial(enf2c3d(marked_trials[i]))
        maintitle = ('Kinematics/kinetics consistency plot, '
                     'session %s' % pl.trial.trialdirname)
        pl.plot_trial(model_tracecolor=linecolors[i], linestyles_context=True,
                      maintitle=maintitle, superpose=True, show=False)

    pl.show()
    pl.create_pdf('kin_consistency.pdf')

if __name__ == '__main__':
    register_gui_exception_handler()
    do_plot()
