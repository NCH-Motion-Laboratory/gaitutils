# -*- coding: utf-8 -*-
"""
Created on Thu Sep 03 14:54:34 2015

EMG consistency plot from Nexus. Automatically picks trials based on Eclipse
description and defined search strings.

@author: Jussi
"""

from gaitutils import Plotter, cfg, register_gui_exception_handler, EMG
from gaitutils.nexus import enf2c3d, find_trials
import logging
import argparse

logger = logging.getLogger(__name__)


def do_plot(search=None, show=True):

    MAX_TRIALS = 8
    linecolors = ['b', 'g', 'r', 'c', 'm', 'y', 'k', 'pink']

    # Eclipse trial notes/description must contain one of these strings
    if search is None:
        search = ['R1', 'R2', 'R3', 'R4', 'L1', 'L2', 'L3', 'L4']

    eclkeys = ['DESCRIPTION', 'NOTES']
    marked_trials = list(find_trials(eclkeys, search))

    if not marked_trials:
        raise Exception('Did not find any marked trials in current '
                        'session directory')

    if len(marked_trials) > MAX_TRIALS:
        raise Exception('Too many marked trials found!')

    pl = Plotter()
    pl.open_trial(enf2c3d(marked_trials[0]))
    layout = cfg.layouts.overlay_std_emg

    # from layout, drop rows that do not have good data in any of the trials
    chs_ok = None
    for i, enf in enumerate(marked_trials):
        emg = EMG(enf2c3d(enf))
        chs_prev_ok = chs_ok if i > 0 else None
        chs_ok = [not emg.is_channel(ch) or emg.status_ok(ch) for row in
                  layout for ch in row]
        if i > 0:
            chs_ok = chs_ok or chs_prev_ok
    rowlen = len(layout[0])
    lout = zip(*[iter(chs_ok)]*rowlen)  # grouper recipe from itertools
    rows_ok = [any(row) for row in lout]
    layout = [row for i, row in enumerate(layout) if rows_ok[i]]
    pl.layout = layout

    for i, trialpath in enumerate(marked_trials):
        pl.open_trial(enf2c3d(marked_trials[i]))
        maintitle = ('EMG consistency plot, '
                     'session %s' % pl.trial.trialdirname)
        pl.plot_trial(emg_tracecolor=linecolors[i],
                      maintitle=maintitle, annotate_emg=False,
                      superpose=True, show=False)

    if show:
        pl.show()

    pl.create_pdf('emg_consistency.pdf')


if __name__ == '__main__':

    parser = argparse.ArgumentParser()
    parser.add_argument('--search', metavar='p', type=str, nargs='+',
                        help='strings that must appear in trial '
                        'description or notes')
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG)
    register_gui_exception_handler()
    do_plot(search=args.search)
