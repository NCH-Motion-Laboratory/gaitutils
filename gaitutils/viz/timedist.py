#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Time-distance plots.

@author: Jussi (jnu@iki.fi)
"""

import logging

from ..envutils import GaitDataError
from ..config import cfg
from .. import sessionutils
from ..timedist import _group_analysis_trials
from ..report.text import _timedist_vars
from .plot_misc import get_backend

logger = logging.getLogger(__name__)


def plot_session_average(session, tags=None, backend=None):
    """Plot time-distance average of session trials.

    Parameters
    ----------
    session : str
        The session directory.
    tags : list | None, optional
        Pick trials with given Eclipse tags. None to use default tags from cfg.
        To collect all trials, use tags=[].
    backend : str | None
        Name of backend to use, currently 'plotly' or 'matplotlib'. If None,
        taken from cfg.

    Returns
    -------
    fig : Figure | dict
        The figure object. Type depends on backend. Use show_fig() to show it.
    """
    if tags is None:
        tags = cfg.eclipse.tags
    trials = sessionutils.get_c3ds(session, tags=tags, trial_type='dynamic')
    if not trials:
        raise GaitDataError('No tagged trials found for session %s' % session)
    session_ = session.name
    fig = plot_trials(
        {session_: trials},
        title='Time-distance average, session %s' % session_,
        backend=backend,
    )
    return fig


def plot_comparison(
    sessions, tags=None, timedist_normaldata=None, big_fonts=False, backend=None
):
    """Plot time-dist comparison of multiple sessions.

    Parameters
    ----------
    sessions : list
        The session directories.
    tags : list | None, optional
        Pick trials with given Eclipse tags. None to use default tags from
        config. To collect all trials, use tags=[].
    timedist_normaldata : dict | None
        Scaling of the bars. Should be a dict with varnames as keys and
        the x scales as values.
    big_fonts : bool, optional
        Increase font size (plotly backend only).
    backend : str | None
        Name of backend to use, currently 'plotly' or 'matplotlib'. If None,
        taken from cfg.

    Returns
    -------
    fig : Figure | dict
        The figure object. Type depends on backend. Use show_fig() to show it.
    """
    if not isinstance(sessions, list):
        sessions = [sessions]

    if tags is None:
        tags = cfg.eclipse.tags
    trials = dict()

    for session in sessions:
        c3ds = sessionutils.get_c3ds(session, tags=tags, trial_type='dynamic')
        if not c3ds:
            raise RuntimeError('No tagged trials found in session %s' % session)
        cond_label = session.name
        trials[cond_label] = c3ds

    return plot_trials(
        trials,
        timedist_normaldata=timedist_normaldata,
        big_fonts=big_fonts,
        backend=backend,
    )


def plot_trials(
    c3dfiles,
    plotvars=None,
    title=None,
    timedist_normaldata=None,
    big_fonts=False,
    backend=None,
):
    """Plot a time-distance barchart from given c3d files.

    Parameters
    ----------
    c3dfiles : dict
        The c3d files to plot. Dict of lists keyed by condition name.
    plotvars : list, optional
        The time-distance variables to plot. This also determines the plotting
        order.
    title : str, optional
        Plot title.
    timedist_normaldata : dict | None
        Scaling of the bars. Should be a dict with varnames as keys and
        the x scales as values.
    big_fonts : bool, optional
        Increase font size (plotly backend only).
    backend : str | None
        Name of backend to use, currently 'plotly' or 'matplotlib'. If None,
        taken from cfg.

    Returns
    -------
    fig : Figure | dict
        The figure object. Type depends on backend. Use show_fig() to show it.
    """
    if plotvars is None:
        plotvars = _timedist_vars
    res_avg_all, res_std_all = _group_analysis_trials(c3dfiles)
    backend_lib = get_backend(backend)
    return backend_lib.time_dist_barchart(
        res_avg_all,
        stddev=res_std_all,
        stddev_bars=False,
        plotvars=plotvars,
        figtitle=title,
        timedist_normaldata=timedist_normaldata,
        big_fonts=big_fonts,
    )
