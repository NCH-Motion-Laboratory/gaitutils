# -*- coding: utf-8 -*-
"""
Created on Thu Sep 03 14:54:34 2015

EMG consistency plot from Nexus. Automatically picks trials based on Eclipse
description and defined search strings.

@author: Jussi (jnu@iki.fi)
"""

import logging
import argparse
from itertools import cycle

from gaitutils import (Plotter, cfg, register_gui_exception_handler, EMG,
                       GaitDataError)
from gaitutils.nexus import find_tagged
from gaitutils.layouts import rm_dead_channels_multitrial

logger = logging.getLogger(__name__)


def do_plot(tags=None, show=True, make_pdf=True):

    tagged_trials = find_tagged(tags)

    if not tagged_trials:
        raise GaitDataError('No marked trials found for current session')

    linecolors = cfg.plot.overlay_colors
    ccolors = cycle(linecolors)

    pl = Plotter()
    layout = cfg.layouts.overlay_std_emg
    emgs = [EMG(tr) for tr in tagged_trials]
    pl.layout = rm_dead_channels_multitrial(emgs, layout)

    for i, trialpath in enumerate(tagged_trials):
        if i > len(linecolors):
            logger.warning('not enough colors for plot!')
        pl.open_trial(tagged_trials[i])

        emg_active = any([pl.trial.emg.status_ok(ch) for ch in
                          cfg.emg.channel_labels])
        if not emg_active:
            continue

        plot_emg_normaldata = (trialpath == tagged_trials[-1])

        pl.plot_trial(emg_tracecolor=ccolors.next(),
                      maintitle='', annotate_emg=False,
                      superpose=True, show=False,
                      plot_emg_normaldata=plot_emg_normaldata)

    if not pl.fig:
        raise GaitDataError('None of the marked trials have valid EMG data')

    maintitle = ('EMG consistency plot, '
                 'session %s' % pl.trial.sessiondir)
    pl.set_title(maintitle)

    if show:
        pl.show()

    if make_pdf:
        pl.create_pdf('emg_consistency.pdf')

    return pl.fig


if __name__ == '__main__':

    parser = argparse.ArgumentParser()
    parser.add_argument('--tags', metavar='p', type=str, nargs='+',
                        help='strings that must appear in trial '
                        'description or notes')
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG)
    register_gui_exception_handler()
    do_plot(tags=args.tags)
