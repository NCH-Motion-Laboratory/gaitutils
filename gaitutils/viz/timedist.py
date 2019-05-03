#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Various time-distance statistics plots

@author: Jussi (jnu@iki.fi)
"""

from builtins import zip
from builtins import range
import logging
import os.path as op
import numpy as np

from .. import nexus, analysis, GaitDataError, sessionutils, cfg
from .plot_matplotlib import time_dist_barchart

logger = logging.getLogger(__name__)


def do_session_average_plot(sessionpath=None, tags=None):
    """Find tagged trials from current session dir and plot average"""

    if sessionpath is None:
        sessionpath = nexus.get_sessionpath()
    if tags is None:
        tags = cfg.eclipse.tags

    trials = sessionutils.get_c3ds(sessionpath, tags=tags,
                                   trial_type='dynamic')
    if not trials:
        raise GaitDataError('No marked trials found for session %s'
                            % sessionpath)
    fig = _plot_trials([trials])
    session = op.split(sessionpath)[-1]
    fig.suptitle('Time-distance average, session %s' % session)

    return fig


def do_single_trial_plot(c3dfile):
    """Plot a single trial time-distance."""

    fig = _plot_trials([[c3dfile]])
    c3dpath, c3dfile_ = op.split(c3dfile)
    fig.suptitle('Time-distance variables, %s' % c3dfile_)

    return fig


def do_multitrial_plot(c3dfiles, show=True, make_pdf=True):
    """Plot multiple trial comparison time-distance.
    PDF goes into Nexus session dir"""

    cond_labels = [op.split(c3d)[-1] for c3d in c3dfiles]
    fig = _plot_trials([[c3d] for c3d in c3dfiles], cond_labels)

    return fig


def do_comparison_plot(sessions, tags=None, show=True):
    """Time-dist comparison of multiple sessions. Tagged trials from each
    session will be picked."""

    if tags is None:
        tags = cfg.eclipse.tags

    trials = list()
    for session in sessions:
        c3ds = sessionutils.get_c3ds(session, tags=tags, trial_type='dynamic')
        if not c3ds:
            raise ValueError('No tagged trials found in session %s' % session)
        trials.append(c3ds)

    cond_labels = [op.split(session)[-1] for session in sessions]
    fig = _plot_trials(trials, cond_labels)

    return fig


def _plot_trials(trials, cond_labels=None):
    """Make a time-distance variable barchart from given trials (.c3d files).
    trials: list of lists, where inner lists represent conditions
    and list elements represent trials.
    Conditions is a matching list of condition labels.
    If there are multiple trials per condition, they will be averaged.
    plotvars specifies variables to plot (if not all) and their order
    """
    # XXX: hardcoded time-distance variables, to set a certain order
    # set plotvars=None to plot all analysis variables from c3d
    plotvars = ['Walking Speed', 'Cadence', 'Foot Off', 'Opposite Foot Off',
                'Opposite Foot Contact', 'Double Support', 'Single Support',
                'Stride Time', 'Stride Length', 'Step Width', 'Step Length']

    if cond_labels is None:
        cond_labels = ['Condition %d' % k for k in range(len(trials))]
    res_avg_all = dict()
    res_std_all = dict()
    for cond_files, cond_label in zip(trials, cond_labels):
        ans = list()
        for c3dfile in cond_files:
            an = analysis.get_analysis(c3dfile, condition=cond_label)
            ans.append(an)
        if len(ans) > 1:  # do average for this condition
            res_avg = analysis.group_analysis(ans)
            res_std = analysis.group_analysis(ans, fun=np.std)
        else:  # do single-trial plot for this condition
            res_avg = ans[0]
            res_std = dict()
            res_std[cond_label] = None
        res_avg_all.update(res_avg)
        res_std_all.update(res_std)

    return time_dist_barchart(res_avg_all, stddev=res_std_all,
                              stddev_bars=False, plotvars=plotvars)

