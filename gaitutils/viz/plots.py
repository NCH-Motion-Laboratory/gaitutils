# -*- coding: utf-8 -*-
"""
Higher level plotting functions (backend agnostic).

@author: Jussi (jnu@iki.fi)
"""

import numpy as np
import os.path as op
import logging

from .. import cfg, trial, GaitDataError, sessionutils, stats, utils
from . import layouts
from .plot_misc import get_backend

logger = logging.getLogger(__name__)


def plot_trials(
    trials,
    layout_name=None,
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
    """Plot gait trials.

    Parameters
    ----------
    trials : list
        Nist of Trial objects to plot.
    layout_name : str | None
        Name of the plot layout to use (defined in cfg).
    backend : str | None
        Name of backend to use, currently 'plotly' or 'matplotlib'. None for default backend.
    model_normaldata : dict | None
        Normaldata for model variables. None to use default normaldata (from cfg)
    cycles : dict | str | int | tuple | list
        Cycles to plot. See Trial.get_cycles()
    max_cycles : dict | None
        Maximum number of cycles to plot for each variable type. If None, taken from cfg.
    emg_mode : str | None
        Use 'rms' to plot EMG in RMS mode.
    legend_type : str | None
        Legend type for gait cycles (see _get_cycle_name for options). None to use cfg option.
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
    """

    backend_lib = get_backend(backend)
    layout = layouts.get_layout(layout_name)
    return backend_lib.plot_trials(
        trials,
        layout,
        model_normaldata=model_normaldata,
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


def plot_nexus_trial(
    layout_name=None,
    backend=None,
    cycles=None,
    max_cycles=None,
    emg_mode=None,
    maintitle=None,
    from_c3d=True,
    model_normaldata=None,
):
    """Plot the currently loaded trial from Vicon Nexus"""
    backend_lib = get_backend(backend)
    tr = trial.nexus_trial(from_c3d=from_c3d)
    layout = layouts.get_layout(layout_name)
    layout = layouts.rm_dead_channels(tr.emg, layout)
    # force unnormalized plot for static trial
    if tr.is_static:
        cycles = 'unnormalized'
    return backend_lib.plot_trials(
        [tr],
        layout,
        model_normaldata=model_normaldata,
        cycles=cycles,
        max_cycles=max_cycles,
        emg_mode=emg_mode,
        legend_type='short_name_with_cyclename',
    )


def plot_sessions(
    sessions,
    tagged_only=True,
    tags=None,
    layout_name=None,
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
    """Plot tagged trials or all trials from given session(s)."""

    # collect c3d files from all sessions
    if not isinstance(sessions, list):
        sessions = [sessions]
    if tags is None:
        tags = cfg.eclipse.tags
    if not tagged_only:
        tags = None
    c3ds_all = list()
    for session in sessions:
        c3ds = sessionutils.get_c3ds(session, tags=tags, trial_type='dynamic')
        if not c3ds:
            raise GaitDataError('No tagged trials found for session %s' % session)
        c3ds_all.extend(c3ds)
    trials = [trial.Trial(c3d) for c3d in c3ds_all]

    # remove dead channels from EMG layout
    # emgs = [tr.emg for tr in trials]
    # layout = layouts.rm_dead_channels_multitrial(emgs, layout)

    return plot_trials(
        trials,
        layout_name=layout_name,
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


def plot_session_average(
    session,
    layout_name=None,
    tagged_only=True,
    tags=None,
    model_normaldata=None,
    backend=None,
):
    """Plot average of tagged or all session trials"""

    layout = layouts.get_layout(layout_name)
    backend_lib = get_backend(backend)

    if tags is None:
        tags = cfg.eclipse.tags
    if not tagged_only:
        tags = None

    c3ds = sessionutils.get_c3ds(session, tags=tags, trial_type='dynamic')
    if not c3ds:
        raise GaitDataError('No dynamic trials found for %s' % session)

    reject_outliers = cfg.trial.outlier_rejection_threshold
    atrial = stats.AvgTrial(c3ds, reject_outliers=reject_outliers, sessionpath=session)
    maintitle_ = '%s (%d trial average)' % (atrial.sessiondir, atrial.nfiles)

    return backend_lib.plot_trials(
        atrial,
        layout,
        model_normaldata=model_normaldata,
        color_by='context',
        figtitle=maintitle_,
    )


def plot_trial_velocities(session, backend=None):
    """Plot median velocities for each dynamic trial in Nexus session."""
    c3ds = sessionutils.get_c3ds(session, trial_type='dynamic')
    if not c3ds:
        raise GaitDataError('No dynamic trials found for %s' % session)

    labels = [op.splitext(op.split(f)[1])[0] for f in c3ds]
    vels = np.array([utils._trial_median_velocity(trial) for trial in c3ds])

    return get_backend(backend)._plot_vels(vels, labels)


def plot_trial_timedep_velocities(session, backend=None):
    """Plot time-dependent velocity for each dynamic trial in session."""
    c3ds = sessionutils.get_c3ds(session, trial_type='dynamic')
    if not c3ds:
        raise GaitDataError('No dynamic trials found for %s' % session)

    vels = list()
    labels = list()
    for c3d in c3ds:
        v, vel = utils._trial_median_velocity(c3d, return_curve=True)
        # vel = signal.medfilt(vel, 3)  # if spikes
        tname = op.split(c3d)[-1]
        vels.append(vel)
        labels.append(tname)

    return get_backend(backend)._plot_timedep_vels(vels, labels)
