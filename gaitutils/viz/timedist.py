#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Various time-distance statistics plots

@author: Jussi (jnu@iki.fi)
"""

import logging
import os.path as op
from collections import OrderedDict

from .. import GaitDataError, sessionutils, cfg
from ..timedist import _timedist_vars, _multitrial_analysis
from .plot_misc import get_backend

logger = logging.getLogger(__name__)


def do_session_average_plot(session, tags=None, backend=None):
    """Find tagged trials from current session dir and plot average"""
    if tags is None:
        tags = cfg.eclipse.tags
    trials = sessionutils.get_c3ds(session, tags=tags,
                                   trial_type='dynamic')
    if not trials:
        raise GaitDataError('No tagged trials found for session %s'
                            % session)
    session_ = op.split(session)[-1]
    fig = _plot_trials({session_: trials},
                       title='Time-distance average, session %s' % session_,
                       backend=backend)
    return fig


def do_single_trial_plot(c3dfile, backend=None):
    """Plot a single trial time-distance."""
    c3dpath, c3dfile_ = op.split(c3dfile)
    fig = _plot_trials({c3dfile: [c3dfile]}, title='Time-distance variables, %s' % c3dfile_)
    return fig


def do_multitrial_plot(c3dfiles, show=True, backend=None):
    """Plot multiple trial comparison time-distance"""
    trials = {op.split(c3d)[-1]: [c3d] for c3d in c3dfiles}
    return _plot_trials(trials, backend=backend)


def do_comparison_plot(sessions, tags=None, big_fonts=False, backend=None):
    """Time-dist comparison of multiple sessions. Tagged trials from each
    session will be picked. big_fonts option for plotly (web report) only"""
    if tags is None:
        tags = cfg.eclipse.tags
    trials = OrderedDict()

    for session in sessions:
        c3ds = sessionutils.get_c3ds(session, tags=tags, trial_type='dynamic')
        if not c3ds:
            raise ValueError('No tagged trials found in session %s' % session)
        cond_label = op.split(session)[-1]
        trials[cond_label] = c3ds

    return _plot_trials(trials, big_fonts=big_fonts, backend=backend)


def _plot_trials(trials, plotvars=None, title=None, interactive=True,
                 big_fonts=False, backend=None):
    """Make a time-distance variable barchart from given trials (.c3d files).
    trials: dict of lists keyed by condition name
    If there are multiple trials per condition, they will be averaged.
    plotvars: variables to plot and their order
    """
    if plotvars is None:
        plotvars = _timedist_vars
    res_avg_all, res_std_all = _multitrial_analysis(trials)
    backend_lib = get_backend(backend)
    return backend_lib.time_dist_barchart(res_avg_all, stddev=res_std_all,
                                          stddev_bars=False, plotvars=plotvars,
                                          title=title, big_fonts=big_fonts)

