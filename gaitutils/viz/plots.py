# -*- coding: utf-8 -*-
"""
Higher level plotting functions (backend agnostic).

@author: Jussi (jnu@iki.fi)
"""

import numpy as np
import os.path as op
import logging

from ..config import cfg
from ..envutils import GaitDataError
from .. import trial, sessionutils, stats, utils
from . import layouts
from .plot_misc import get_backend

logger = logging.getLogger(__name__)


def plot_trials(
    trials,
    layout_name=None,
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
    layout_name : str | None
        Name of the plot layout to use (layouts are defined in cfg).
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
        If 'rms', plot EMG in RMS mode.
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
    layout = layouts.get_layout(layout_name)

    if auto_adjust_emg_layout and 'EMG' in layout_name.upper():
        emgs = [tr.emg for tr in trials]
        layout = layouts._rm_dead_channels(emgs, layout)

    return backend_lib.plot_trials(
        trials,
        layout,
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


def _plot_session_average(
    session,
    layout_name=None,
    tagged_only=True,
    tags=None,
    model_normaldata=None,
    backend=None,
):
    """Average trials from session and plot."""

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
    atrial = stats.AvgTrial.from_trials(
        c3ds, reject_outliers=reject_outliers, sessionpath=session
    )
    maintitle_ = '%s (%d trial average)' % (atrial.sessiondir, atrial.nfiles)

    return backend_lib.plot_trials(
        atrial,
        layout,
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
    c3ds = sessionutils.get_c3ds(session, trial_type='dynamic')
    if not c3ds:
        raise GaitDataError('No dynamic trials found for %s' % session)
    labels = [op.splitext(op.split(f)[1])[0] for f in c3ds]
    vels = np.array([utils._trial_median_velocity(tr) for tr in c3ds])
    figtitle = 'Walking speed for %s (average %.2f m/s)' % (
        op.split(session)[-1],
        np.nanmean(vels),
    )
    return get_backend(backend)._plot_vels(vels, labels, title=figtitle)


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
        raise GaitDataError('No dynamic trials found for %s' % session)
    vels = list()
    labels = [op.splitext(op.split(f)[1])[0] for f in c3ds]
    # get velocity curves
    for c3d in c3ds:
        _, vel = utils._trial_median_velocity(c3d, return_curve=True)
        # vel = signal.medfilt(vel, 3)  # can be used to filter out spikes
        vels.append(vel)
    figtitle = 'Time-dependent trial velocities for %s' % op.split(session)[-1]
    return get_backend(backend)._plot_timedep_vels(vels, labels, title=figtitle)


def _compose_varname(vardef):
    """Compose a variable name for extracted variable.

    E.g. ['HipAnglesX', 'peaks', 'swing', 'max']
    -> 'Hip flexion maximum during swing phase'
    """
    varname = vardef[0]
    # get variable description from gaitutils.models
    themodel = gaitutils.models.model_from_var(varname)
    name = themodel.varlabels_noside[varname]
    if vardef[1] == 'contact':
        name += ' at initial contact'
    elif vardef[1] in ['peaks', 'extrema']:
        phase = vardef[2]  # swing, stance etc.
        valtype = vardef[3]  # min, max etc.
        val_trans = {'max': 'maximum', 'min': 'minimum'}
        if phase == 'overall':
            name += ', %s %s' % (phase, val_trans[valtype])
        else:
            name += ', %s phase %s' % (phase, val_trans[valtype])
        if vardef[1] == 'peaks':
            name += ' peak'
    return name


def _var_unit(vardef):
    """Return unit for a vardef"""
    varname = vardef[0]
    themodel = gaitutils.models.model_from_var(varname)
    return themodel.units[varname]


def plot_extracted_box(curve_vals, vardefs):
    """Plot comparison of extracted gait curve values as box plot.

    Parameters
    ----------
    vardefs : list
        Nested list of variable definitions.
    curve_vals : dict
        The curve extracted data, keyed by session.
    """
    nvars = len(vardefs)
    subtitles = [_compose_varname(nested_keys) for nested_keys in vardefs]
    fig = make_subplots(rows=nvars, cols=1, subplot_titles=subtitles)
    legendgroups = set()

    # the plotting logic is a bit weird due to the way go.Box() works:
    # -we first consolidate one variable's data from all sessions into a 1-d array
    # -this is done separately for L/R context
    # -the consolidated data is then plotted along with the session identifier
    for row, vardef in enumerate(vardefs):
        for ctxt in 'LR':
            vals = list()
            sessionnames = list()
            vardef_ctxt = [ctxt + vardef[0]] + vardef[1:]
            for session, session_vals in curve_vals.items():
                this_vals = _nested_get(session_vals, vardef_ctxt)
                vals.extend(this_vals)
                sessiondir = op.split(session)[-1]
                sessionnames.extend([sessiondir] * len(this_vals))
            # show entry in legend only if it was not already shown
            show_legend = ctxt not in legendgroups
            legendgroups.add(ctxt)

            box = go.Box(
                x=sessionnames,
                y=vals,
                # boxpoints='all',
                name=ctxt,
                offsetgroup=ctxt,
                legendgroup=ctxt,
                showlegend=show_legend,
                opacity=0.5,
                # mode='lines+markers',
                marker_color=cfg.plot.context_colors[ctxt],
            )
            fig.append_trace(box, row=row + 1, col=1)
            xlabel = _var_unit(vardef_ctxt)
            xaxis, yaxis = _get_plotly_axis_labels(row, 0, ncols=1)
            fig['layout'][yaxis].update(
                title={
                    'text': xlabel,
                    'standoff': 0,
                }
            )
    fig.update_layout(
        boxmode='group'  # group together boxes of the different traces for each value of x
    )
    return fig
