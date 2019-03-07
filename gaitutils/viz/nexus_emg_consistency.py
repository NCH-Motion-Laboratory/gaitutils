#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Created on Thu Sep 03 14:54:34 2015

EMG consistency plot from Nexus. Automatically picks trials based on Eclipse
description and defined search strings.

@author: Jussi (jnu@iki.fi)
"""

import logging
import argparse
import os.path as op
from itertools import cycle

from gaitutils import (Plotter, cfg, register_gui_exception_handler, EMG,
                       GaitDataError, sessionutils, nexus, Trial, plot_plotly)
from gaitutils.layouts import rm_dead_channels_multitrial

logger = logging.getLogger(__name__)


def do_plot(sessionpath=None, tags=None, show=True, make_pdf=True,
            backend=None):

    if sessionpath is None:
        sessionpath = nexus.get_sessionpath()

    if backend is None:
        backend = cfg.plot.backend

    c3dfiles = sessionutils.get_c3ds(sessionpath, tags=cfg.eclipse.tags,
                                     trial_type='dynamic')

    if not c3dfiles:
        raise GaitDataError('No marked trials found for current session')

    linecolors = cfg.plot.overlay_colors
    ccolors = cycle(linecolors)

    layout = cfg.layouts.overlay_std_emg
    emgs = [EMG(tr) for tr in c3dfiles]
    layout = rm_dead_channels_multitrial(emgs, layout)

    if backend == 'matplotlib':
        pl = Plotter()
        pl.layout = layout

        for i, trialpath in enumerate(c3dfiles):
            if i > len(linecolors):
                logger.warning('not enough colors for plot!')
            pl.open_trial(c3dfiles[i])

            emg_active = any([pl.trial.emg.status_ok(ch) for ch in
                              cfg.emg.channel_labels])
            if not emg_active:
                continue

            plot_emg_normaldata = (trialpath == c3dfiles[-1])

            pl.plot_trial(emg_tracecolor=next(ccolors),
                          maintitle='', annotate_emg=False,
                          superpose=True, show=False,
                          plot_emg_normaldata=plot_emg_normaldata)

        if not pl.fig:
            raise GaitDataError('None of the trials have valid EMG data')

        maintitle = ('EMG consistency plot, '
                     'session %s' % pl.trial.sessiondir)
        pl.set_title(maintitle)

        if show:
            pl.show()

        if make_pdf:
            pl.create_pdf('emg_consistency.pdf')

        return pl.fig

    elif backend == 'plotly':

        trials = [Trial(c3d) for c3d in c3dfiles]
        maintitle = ('EMG consistency plot, session %s' %
                     op.split(sessionpath)[-1])
        plot_plotly.plot_trials_browser(trials, layout,
                                        legend_type='short_name_with_tag',
                                        maintitle=None)


if __name__ == '__main__':

    parser = argparse.ArgumentParser()
    parser.add_argument('--tags', metavar='p', type=str, nargs='+',
                        help='strings that must appear in trial '
                        'description or notes')
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG)
    register_gui_exception_handler()
    do_plot(tags=args.tags)
