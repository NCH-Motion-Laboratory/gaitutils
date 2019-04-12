# -*- coding: utf-8 -*-
"""

Higher level plotting functions. Plots should:
    -take backend argument (in case default backend is not ok)
    -return created figure object

@author: Jussi (jnu@iki.fi)
"""

import os.path as op
from itertools import cycle
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

    if backend is None:
        backend = cfg.plot.backend
    
    backend_lib = backend_selector(backend)

    tr = trial.nexus_trial(from_c3d=from_c3d)
    layout = layouts.get_layout(layout_name)
    layout = layouts.rm_dead_channels(tr.emg, layout)

    # force unnormalized plot for static trial
    model_cycles = 'unnormalized' if tr.is_static else model_cycles

    return backend_lib.plot_trials([tr], layout, model_cycles=model_cycles, emg_cycles=emg_cycles,
                                   legend_type='short_name_with_cyclename')


def plot_nexus_session(tags=None):
    """Plot tagged trials from Nexus session"""
    sessions = [nexus.get_sessionpath()]
    return plot_sessions(sessions, tags=tags)


def plot_nexus_session_average(tags=None):
    """Plot tagged trials from Nexus session"""
    session = nexus.get_sessionpath()
    return plot_session_average(session)


def plot_sessions(sessions, layout_name=None, tags=None, make_pdf=False,
                  style_by=None, color_by=None, legend_type=None,
                  backend=None):
    """Plot given sessions."""

    if layout_name is None:
        layout_name = 'lb_kinematics'

    if backend is None:
        backend = cfg.plot.backend

    backend_lib = backend_selector(backend)
    layout = layouts.get_layout(layout_name)

    if tags is None:
        tags = cfg.eclipse.tags

    c3ds_all = list()
    for session in sessions:
        c3ds = sessionutils.get_c3ds(session, tags=tags,
                                     trial_type='dynamic')
        if not c3ds:
            raise GaitDataError('No marked trials found for session %s'
                                % session)
        c3ds_all.extend(c3ds)
    trials = [trial.Trial(c3d) for c3d in c3ds_all]
    if 'EMG' in layout_name.upper():
        emgs = [tr.emg for tr in trials]
        layout = layouts.rm_dead_channels_multitrial(emgs, layout)
    return backend_lib.plot_trials(trials, layout,
                                   legend_type=legend_type,
                                   style_by=style_by, color_by=color_by)


def plot_session_emg(session, tags=None, show=True, make_pdf=True,
                     backend=None):
    """Plot EMG for tagged trials from session.
    FIXME: should be merged with plot_sessions"""

    if backend is None:
        backend = cfg.plot.backend

    c3dfiles = sessionutils.get_c3ds(session, tags=cfg.eclipse.tags,
                                     trial_type='dynamic')

    if not c3dfiles:
        raise GaitDataError('No marked trials found for current session')

    linecolors = cfg.plot.overlay_colors
    ccolors = cycle(linecolors)

    layout = cfg.layouts.overlay_std_emg
    emgs = [emg.EMG(tr) for tr in c3dfiles]
    layout = layouts.rm_dead_channels_multitrial(emgs, layout)

    if backend == 'matplotlib':
        pl = plot_matplotlib.Plotter()
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

        trials = [trial.Trial(c3d) for c3d in c3dfiles]
        maintitle = ('EMG consistency plot, session %s' %
                     op.split(session)[-1])
        plot_plotly.plot_trials_browser(trials, layout,
                                        legend_type='short_name_with_tag',
                                        maintitle=None)


def plot_session_musclelen(session, tags=None, age=None, show=True,
                           make_pdf=True):
    """Plot muscle length for tagged trials from session.
    FIXME: should be merged with plot_sessions"""

    tags = tags or cfg.eclipse.tags
    tagged_trials = sessionutils.get_c3ds(session, tags=tags,
                                          trial_type='dynamic')

    if not tagged_trials:
        raise GaitDataError('No marked trials found for current session')

    pl = plot_matplotlib.Plotter()

    if age is not None:
        ndata = normaldata.normaldata_age(age)
        if ndata:
            pl.add_normaldata(ndata)

    pl.layout = cfg.layouts.overlay_musclelen

    linecolors = cfg.plot.overlay_colors
    ccolors = cycle(linecolors)

    for i, trialpath in enumerate(tagged_trials):
        logger.debug('plotting %s' % tagged_trials[i])
        pl.open_trial(tagged_trials[i])
        if i > len(linecolors):
            logger.warning('not enough colors for plot!')
        # only plot normaldata for last trial to speed up things
        plot_model_normaldata = (trialpath == tagged_trials[-1])
        pl.plot_trial(model_tracecolor=next(ccolors), linestyles_context=True,
                      toeoff_markers=False, add_zeroline=False, show=False,
                      maintitle='', superpose=True, sharex=False,
                      plot_model_normaldata=plot_model_normaldata)

    maintitle = ('Muscle length consistency plot, '
                 'session %s' % pl.trial.sessiondir)
    pl.set_title(maintitle)

    if show:
        pl.show()

    if make_pdf:
        pl.create_pdf('musclelen_consistency.pdf')

    return pl.fig


def plot_session_average(session, make_pdf=False):

    figs = []
    c3ds = sessionutils.get_c3ds(session, trial_type='dynamic')
    if not c3ds:
        raise GaitDataError('No dynamic trials found for current session')

    atrial = stats.AvgTrial(c3ds)

    pl = plot_matplotlib.Plotter()
    pl.trial = atrial

    layout = cfg.layouts.lb_kin

    maintitle_ = '%d trial average from %s' % (atrial.nfiles, session)

    for side in ['R', 'L']:
        side_str = 'right' if side == 'R' else 'left'
        maintitle = maintitle_ + ' (%s)' % side_str
        pl.layout = layouts.onesided_layout(layout, side)
        figs.append(pl.plot_trial(split_model_vars=False,
                                  model_stddev=atrial.stddev_data,
                                  maintitle=maintitle))
        if make_pdf:
            pl.create_pdf(pdf_name='kin_average_%s.pdf' % side,
                          sessionpath=session)
    return figs


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







