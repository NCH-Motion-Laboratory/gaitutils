# -*- coding: utf-8 -*-
"""
Created on Thu Sep 03 14:54:34 2015

Kin* consistency plot from Nexus. Automatically picks trials based on Eclipse
description and defined search strings.

@author: Jussi
"""

from gaitutils import Plotter, cfg, register_gui_exception_handler
from gaitutils.nexus import enf2c3d, find_trials

import logging
import argparse
logger = logging.getLogger(__name__)


def do_plot(search=None, show=True):

    MAX_TRIALS = 8

    if search is None:
        # default Eclipse search strings
        search = ['R1', 'R2', 'R3', 'R4', 'L1', 'L2', 'L3', 'L4']

    eclkeys = ['DESCRIPTION', 'NOTES']
    marked_trials = list(find_trials(eclkeys, search))

    if not marked_trials:
        raise Exception('Did not find any matching trials in current '
                        'session directory')

    if len(marked_trials) > MAX_TRIALS:
        raise Exception('Too many marked trials found!')

    pl = Plotter()
    pl.open_trial(enf2c3d(marked_trials[0]))
    pl.layout = cfg.layouts.overlay_lb_kin

    linecolors = ['b', 'g', 'r', 'c', 'm', 'y', 'k', 'pink']

    for i, trialpath in enumerate(marked_trials):
        logger.debug('plotting %s' % marked_trials[i])
        pl.open_trial(enf2c3d(marked_trials[i]))
        maintitle = ('Kinematics/kinetics consistency plot, '
                     'session %s' % pl.trial.trialdirname)
        pl.plot_trial(model_tracecolor=linecolors[i], linestyles_context=True,
                      maintitle=maintitle, superpose=True, show=False)
    if show:
        pl.show()
        
    pl.create_pdf('kin_consistency.pdf')


if __name__ == '__main__':

    parser = argparse.ArgumentParser()
    parser.add_argument('--search', metavar='p', type=str, nargs='+',
                        help='strings that must appear in trial '
                        'description or notes')
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG)
    register_gui_exception_handler()
    do_plot(search=args.search)



