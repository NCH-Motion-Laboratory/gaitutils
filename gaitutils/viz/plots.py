# -*- coding: utf-8 -*-
"""
Higher level plotting functions (backend agnostic).

@author: Jussi (jnu@iki.fi)
"""

import numpy as np
import logging

from ..config import cfg
from ..envutils import GaitDataError
from ..numutils import modified_zscore
from .. import trial, sessionutils, stats, utils
from . import layouts
from .plot_misc import get_backend

logger = logging.getLogger(__name__)


def plot_trials(
    trials,
    layout=None,
    backend=None,
    model_normaldata=None,
    emg_normaldata=None,
    cycles=None,
    max_cycles=None,
    emg_mode=None,
    legend_type=None,
    style_by=None,
    color_by=None,
    supplementary_data=None,
    legend=True,
    figtitle=None,
    auto_adjust_emg_layout=False,
):
    """Plot gait trials.

    Create a plot of gait trials using the given layout. Output depends on the
    backend.

    Parameters
    ----------
    trials : list
        List of Trial instances to plot.
    layout : str | None | list
        Name of the plot layout to use (layouts are defined in config). Alternatively,
        can directly specify a layout as a list of lists.
    backend : str | None
        Name of backend to use, currently 'plotly' or 'matplotlib'. If None,
        taken from cfg.
    model_normaldata : dict | None
        Normal data for model variables. If None, taken from cfg.
    emg_normaldata : dict | None
        Normal data for EMG variables. If None, taken from cfg.
    cycles : dict | str | int | tuple | list
        Cycles to plot. See Trial.get_cycles() for details.
    max_cycles : dict | None
        Maximum number of cycles to plot for each variable type. If None, taken
        from cfg.
    emg_mode : str | None
        If 'envelope', plot EMG in envelope mode.
    legend_type : str | None
        Legend type for gait cycles (see _get_cycle_name for options). If None,
        taken from cfg.
    style_by : dict | None
        How to style each variable type. If None, taken from cfg.
    color_by : dict | None
        How to color each variable type. If None, taken from cfg.
    supplementary_data : dict | None
        Supplementary data to plot for each variable.
    legend : bool
        Whether to plot legend or not.
    figtitle : str | None
        Main title for the figure.

    Returns
    -------
    fig : Figure | dict
        The figure object. Type depends on backend. Use show_fig() to show it.
    """

    backend_lib = get_backend(backend)
    the_layout = layouts.get_layout(layout)

    if auto_adjust_emg_layout and 'EMG' in layout.upper():
        emgs = [tr.emg for tr in trials]
        the_layout = layouts._rm_dead_channels(emgs, the_layout)

    return backend_lib.plot_trials(
        trials,
        the_layout,
        model_normaldata=model_normaldata,
        emg_normaldata=emg_normaldata,
        cycles=cycles,
        max_cycles=max_cycles,
        emg_mode=emg_mode,
        legend_type=legend_type,
        style_by=style_by,
        color_by=color_by,
        supplementary_data=supplementary_data,
        legend=legend,
        figtitle=figtitle,
    )


def _plot_sessions(
    sessions,
    tagged_only=True,
    tags=None,
    layout=None,
    backend=None,
    model_normaldata=None,
    cycles=None,
    max_cycles=None,
    emg_mode=None,
    legend_type=None,
    style_by=None,
    color_by=None,
    supplementary_data=None,
    legend=True,
    figtitle=None,
):
    """Gather trials across given sessions and plot them."""
    if not isinstance(sessions, list):
        sessions = [sessions]
    if tags is None:
        tags = cfg.eclipse.tags
    if not tagged_only:
        tags = None
    c3ds_all = sessionutils._get_tagged_dynamic_c3ds_from_sessions(sessions, tags=tags)
    trials = [trial.Trial(c3d) for c3d in c3ds_all]

    return plot_trials(
        trials,
        layout=layout,
        backend=backend,
        model_normaldata=model_normaldata,
        cycles=cycles,
        max_cycles=max_cycles,
        emg_mode=emg_mode,
        legend_type=legend_type,
        style_by=style_by,
        color_by=color_by,
        supplementary_data=None,
        legend=legend,
        figtitle=figtitle,
    )


def _plot_session_average(
    session,
    layout=None,
    tagged_only=True,
    tags=None,
    model_normaldata=None,
    backend=None,
):
    """Average trials from session and plot."""

    the_layout = layouts.get_layout(layout)
    backend_lib = get_backend(backend)

    if tags is None:
        tags = cfg.eclipse.tags
    if not tagged_only:
        tags = None

    c3ds = sessionutils.get_c3ds(session, tags=tags, trial_type='dynamic')
    if not c3ds:
        raise GaitDataError(f'No dynamic trials found for {session}')

    reject_outliers = cfg.trial.outlier_rejection_threshold
    atrial = stats.AvgTrial.from_trials(
        c3ds, reject_outliers=reject_outliers, sessionpath=session
    )
    maintitle_ = '%s (%d trial average)' % (atrial.sessiondir, atrial.nfiles)

    return backend_lib.plot_trials(
        atrial,
        the_layout,
        model_normaldata=model_normaldata,
        color_by='context',
        figtitle=maintitle_,
    )


def plot_trial_velocities(session, backend=None):
    """Plot median velocities of dynamic trials.

    Parameters
    ----------
    session : str
        Path to session.
    backend : str | None
        Name of backend to use, currently 'plotly' or 'matplotlib'. If None,
        taken from cfg.

    Returns
    -------
    fig : Figure | dict
        The figure object. Type depends on backend. Use show_fig() to show it.
    """
    REJECT_THRESHOLD = 6  # reject velocities that differ from median by more than x stds
    c3ds = sessionutils.get_c3ds(session, trial_type='dynamic')
    if not c3ds:
        raise GaitDataError(f'No dynamic trials found for {session}')
    labels = [f.stem for f in c3ds]
    vels = np.array([utils._trial_median_velocity(tr) for tr in c3ds])
    zsc = modified_zscore(vels)
    ok_inds = np.where(abs(zsc) < REJECT_THRESHOLD)[0]
    logger.debug(f'rejected {len(vels) - len(ok_inds)} trials as velocity outliers')
    vels_ok = vels[ok_inds]
    labels_ok = [labels[k] for k in ok_inds]
    figtitle = f'Walking speed for {session.name} (average {np.nanmean(vels):.2f} m/s)'
    return get_backend(backend)._plot_vels(vels_ok, labels_ok, title=figtitle)


def plot_trial_timedep_velocities(session, backend=None):
    """Plot time-dependent velocity of dynamic trials in session.

    Parameters
    ----------
    session : str
        Path to session.
    backend : str | None
        Name of backend to use, currently 'plotly' or 'matplotlib'. If None,
        taken from cfg.

    Returns
    -------
    fig : Figure | dict
        The figure object. Type depends on backend. Use show_fig() to show it.

    """
    c3ds = sessionutils.get_c3ds(session, trial_type='dynamic')
    if not c3ds:
        raise GaitDataError(f'No dynamic trials found for {session}')
    vels = list()
    labels = [f.stem for f in c3ds]
    # get velocity curves
    for c3d in c3ds:
        _, vel = utils._trial_median_velocity(c3d, return_curve=True)
        # vel = signal.medfilt(vel, 3)  # can be used to filter out spikes
        vels.append(vel)
    figtitle = f'Time-dependent trial velocities for {session.name}'
    return get_backend(backend)._plot_timedep_vels(vels, labels, title=figtitle)
