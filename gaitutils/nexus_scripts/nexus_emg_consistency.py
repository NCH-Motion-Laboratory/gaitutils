# -*- coding: utf-8 -*-
"""
Created on Thu Sep 03 14:54:34 2015

EMG consistency plot from Nexus. Automatically picks trials based on Eclipse
description and defined search strings.

@author: Jussi (jnu@iki.fi)
"""

import logging
import argparse

from gaitutils import Plotter, cfg, register_gui_exception_handler, EMG
from gaitutils.nexus import enf2c3d
from gaitutils.nexus_scripts.nexus_kin_consistency import find_tagged

logger = logging.getLogger(__name__)


def do_plot(search=None, show=True):

    tagged_trials = find_tagged(search)

    linecolors = ['b', 'g', 'r', 'c', 'm', 'y', 'k', 'pink']

    pl = Plotter()
    pl.open_trial(enf2c3d(tagged_trials[0]))
    layout = cfg.layouts.overlay_std_emg

    # from layout, drop rows that do not have good data in any of the trials
    chs_ok = None
    for i, enf in enumerate(tagged_trials):
        emg = EMG(enf2c3d(enf))
        chs_prev_ok = chs_ok if i > 0 else None
        # plot channels w/ status ok, or anything that is not a
        # configured EMG channel
        chs_ok = [ch not in cfg.emg.channel_labels or emg.status_ok(ch) for
                  row in layout for ch in row]
        if i > 0:
            chs_ok = chs_ok or chs_prev_ok
    rowlen = len(layout[0])
    lout = zip(*[iter(chs_ok)]*rowlen)  # grouper recipe from itertools
    rows_ok = [any(row) for row in lout]
    layout = [row for i, row in enumerate(layout) if rows_ok[i]]
    pl.layout = layout

    for i, trialpath in enumerate(tagged_trials):
        pl.open_trial(enf2c3d(tagged_trials[i]))
        maintitle = ('EMG consistency plot, '
                     'session %s' % pl.trial.trialdirname)
        plot_emg_normaldata = (trialpath == tagged_trials[-1])
        pl.plot_trial(emg_tracecolor=linecolors[i],
                      maintitle=maintitle, annotate_emg=False,
                      superpose=True, show=False,
                      plot_emg_normaldata=plot_emg_normaldata)

    if show:
        pl.show()

    pl.create_pdf('emg_consistency.pdf')

    return pl.fig


if __name__ == '__main__':

    parser = argparse.ArgumentParser()
    parser.add_argument('--search', metavar='p', type=str, nargs='+',
                        help='strings that must appear in trial '
                        'description or notes')
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG)
    register_gui_exception_handler()
    do_plot(search=args.search)
