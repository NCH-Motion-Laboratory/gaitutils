# -*- coding: utf-8 -*-
"""

Higher level plotting functions. Plots should:
    -take backend argument
    -return created figure object

@author: Jussi (jnu@iki.fi)
"""

import os.path as op
import logging
import plotly.graph_objs as go

from .. import (cfg, layouts, trial, GaitDataError, sessionutils,
                normaldata, stats, utils, emg, nexus)
from . import plot_matplotlib, plot_plotly
from .plot_misc import backend_selector


logger = logging.getLogger(__name__)


def plot_nexus_trial(layout_name=None, backend=None, model_cycles=None,
                     emg_cycles=None, maintitle=None, from_c3d=True):
    """Plot the currently loaded trial from Vicon Nexus"""

    if layout_name is None:
        layout_name = 'lb_kinematics'

    backend_lib = backend_selector(backend)

    tr = trial.nexus_trial(from_c3d=from_c3d)
    layout = layouts.get_layout(layout_name)
    layout = layouts.rm_dead_channels(tr.emg, layout)

    # force unnormalized plot for static trial
    model_cycles = 'unnormalized' if tr.is_static else model_cycles

    return backend_lib.plot_trials([tr], layout, model_cycles=model_cycles, emg_cycles=emg_cycles,
                                   legend_type='short_name_with_cyclename')


def plot_nexus_session(tags=None, model_cycles=None, emg_cycles=None):
    """Plot tagged trials from Nexus session"""
    sessions = [nexus.get_sessionpath()]
    return plot_sessions(sessions, tags=tags, model_cycles=model_cycles,
                         emg_cycles=emg_cycles)


def plot_nexus_session_average(tags=None):
    """Plot tagged trials from Nexus session"""
    session = nexus.get_sessionpath()
    return plot_session_average(session)


def plot_sessions(sessions, layout_name=None, tags=None, make_pdf=False,
                  style_by=None, color_by=None, legend_type=None,
                  model_cycles=None, emg_cycles=None,
                  backend=None, figtitle=None):
    """Plot tagged trials from given session(s)."""

    if not isinstance(sessions, list):
        sessions = [sessions]

    if layout_name is None:
        layout_name = 'lb_kinematics'

    if tags is None:
        tags = cfg.eclipse.tags

    backend_lib = backend_selector(backend)
    layout = layouts.get_layout(layout_name)

    # collect c3d files across sessions
    c3ds_all = list()
    for session in sessions:
        c3ds = sessionutils.get_c3ds(session, tags=tags,
                                     trial_type='dynamic')
        if not c3ds:
            raise GaitDataError('No marked trials found for session %s'
                                % session)
        c3ds_all.extend(c3ds)
    trials = [trial.Trial(c3d) for c3d in c3ds_all]
    # remove dead channels from EMG layout
    if 'EMG' in layout_name.upper():
        emgs = [tr.emg for tr in trials]
        layout = layouts.rm_dead_channels_multitrial(emgs, layout)
    return backend_lib.plot_trials(trials, layout, legend_type=legend_type,
                                   style_by=style_by, color_by=color_by,
                                   model_cycles=model_cycles, emg_cycles=emg_cycles,
                                   figtitle=figtitle)


def plot_session_average(session, layout_name, make_pdf=False,
                         backend=None):
    """Plot average of all session trials"""

    layout = layouts.get_layout(layout_name)
    backend_lib = backend_selector(backend)

    c3ds = sessionutils.get_c3ds(session, trial_type='dynamic')
    if not c3ds:
        raise GaitDataError('No dynamic trials found for current session')
    atrial = stats.AvgTrial(c3ds)

    maintitle_ = '%d trial average from %s' % (atrial.nfiles, session)
    figs = []

    for side in ['R', 'L']:
        side_str = 'right' if side == 'R' else 'left'
        maintitle = maintitle_ + ' (%s)' % side_str
        layout_ = layouts.onesided_layout(layout, side)
        # FIXME: model_stddev=atrial.stddev_data
        fig = backend_lib.plot_trials(atrial, layout_, model_stddev=atrial.stddev_data,
                                      figtitle=maintitle)
        figs.append(fig)

    return figs

# XXX: plotly only; into web report?
def _plot_vel_curves(session):
    """Plot time-dependent velocity for each dynamic trial in session."""
    c3ds = sessionutils.get_c3ds(session, trial_type='dynamic')
    if not c3ds:
        raise GaitDataError('No dynamic trials found for current session')
    traces = list()
    for c3d in c3ds:
        v, vel = utils._trial_median_velocity(c3d, return_curve=True)
        # vel = signal.medfilt(vel, 3)  # if spikes
        tname = op.split(c3d)[-1]
        trace = go.Scatter(y=vel, text=tname, name=tname, hoverinfo='x+y+text')
        traces.append(trace)
    return traces

# FIXME: do not import plt
def plot_trial_velocities(session, show=True, make_pdf=True):
    """Plot median velocities for each dynamic trial in Nexus session."""
    c3ds = sessionutils.get_c3ds(session, trial_type='dynamic')

    if len(c3ds) == 0:
        raise Exception('Did not find any dynamic trials in current '
                        'session directory')

    labels = [op.splitext(op.split(f)[1])[0] for f in c3ds]
    vels = np.array([utils._trial_median_velocity(trial) for trial in c3ds])
    vavg = np.nanmean(vels)

    fig = plt.figure()
    plt.stem(vels)
    plt.xticks(range(len(vels)), labels, rotation='vertical')
    plt.ylabel('Speed (m/s)')
    plt.tick_params(axis='both', which='major', labelsize=8)
    plt.title('Walking speed for dynamic trials (average %.2f m/s)' % vavg)
    plt.tight_layout()

    if make_pdf:
        pdf_name = op.join(nexus.get_sessionpath(), 'trial_velocity.pdf')
        with PdfPages(pdf_name) as pdf:
            pdf.savefig(fig)

    if show:
        plt.show()

    return fig







