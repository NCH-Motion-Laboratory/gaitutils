# -*- coding: utf-8 -*-
"""

Higher level plotting functions

@author: Jussi (jnu@iki.fi)
"""

import os.path as op
from itertools import cycle
import logging

from .. import cfg, layouts, trial, GaitDataError, sessionutils, Trial
from . import plot_matplotlib, plot_plotly


logger = logging.getLogger(__name__)


def plot_nexus_trial(layout_name=None, backend=None, model_cycles=None,
                     emg_cycles=None, maintitle=None, from_c3d=True):
    """Plot the currently loaded trial from Vicon Nexus"""

    if layout_name is None:
        layout_name = 'lb_kinematics'

    try:
        layout = getattr(cfg.layouts, layout_name)
    except AttributeError:
        raise GaitDataError('No such layout %s' % layout_name)

    tr = trial.nexus_trial(from_c3d=from_c3d)
    model_cycles = ('unnormalized' if tr.is_static else
                    model_cycles)
    emg_cycles = ('unnormalized' if tr.is_static else
                  emg_cycles)

    # remove dead EMG channel
    # should be a no-op for non-EMG layouts, but restrict it to '*EMG*' anyway
    if 'EMG' in layout_name.upper():
        layout = layouts.rm_dead_channels(tr.emg, layout)

    if backend is None:
        backend = cfg.plot.backend

    if backend == 'matplotlib':
        pl = plot_matplotlib.Plotter(interactive=False)
        pl.layout = layout
        pl.plot_trial(tr, model_cycles=model_cycles, emg_cycles=emg_cycles,
                      show=False)
        fig = pl.fig

    elif backend == 'plotly':
        fig = plot_plotly.plot_trials([tr], layout, model_cycles=model_cycles,
                                      emg_cycles=emg_cycles,
                                      legend_type='short_name_with_cyclename')
    else:
        raise ValueError('Invalid plotting backend %s' % cfg.plot.backend)

    return fig


def plot_sessions(sessions, tags=None, show=True, make_pdf=True,
                  session_styles=False, backend=None):
    """Plot kinematics for given sessions"""
    if backend is None:
        backend = cfg.plot.backend

    layout = cfg.layouts.overlay_lb_kin

    if tags is None:
        tags = cfg.eclipse.tags

    if backend == 'matplotlib':
        pl = plot_matplotlib.Plotter()
        pl.layout = layout

        linecolors = cfg.plot.overlay_colors
        ccolors = cycle(linecolors)
        linestyles = [':', '--', '-']

        ind = 0
        for session in sessions:
            c3ds = sessionutils.get_c3ds(session, tags=tags,
                                         trial_type='dynamic')
            if not c3ds:
                raise GaitDataError('No marked trials found for session %s'
                                    % session)
            session_style = linestyles.pop()
            for c3d in c3ds:
                pl.open_trial(c3d)
                ind += 1
                if ind > len(linecolors):
                    logger.warning('not enough colors for plot!')
                # only plot normaldata for last trial to speed up things
                plot_model_normaldata = (c3d == c3ds[-1] and
                                         session == sessions[-1])
                # select style/color according to either session or trial
                model_tracecolor = next(ccolors)
                if session_styles:
                    model_linestyle = session_style
                    linestyles_context = False
                else:
                    model_linestyle = None
                    linestyles_context = True

                pl.plot_trial(model_tracecolor=model_tracecolor,
                              model_linestyle=model_linestyle,
                              linestyles_context=linestyles_context,
                              toeoff_markers=False, legend_maxlen=10,
                              maintitle='', superpose=True, show=False,
                              plot_model_normaldata=plot_model_normaldata)

        # auto set title
        if len(sessions) > 1:
            maintitle = 'Kinematics comparison '
            maintitle += ' vs. '.join([op.split(s)[-1] for s in sessions])
        else:
            maintitle = ('Kinematics consistency plot, session %s' %
                         op.split(sessions[0])[-1])
        pl.set_title(maintitle)

        if show:
            pl.show()

        # to recreate old behavior...
        if make_pdf and len(sessions) == 1:
            pl.create_pdf(pdf_name=op.join(sessions[0], 'kin_consistency.pdf'))

        return pl.fig

    elif backend == 'plotly':
        c3ds_all = list()
        for session in sessions:
            c3ds = sessionutils.get_c3ds(session, tags=tags,
                                         trial_type='dynamic')
            if not c3ds:
                raise GaitDataError('No marked trials found for session %s'
                                    % session)
            c3ds_all.extend(c3ds)
        trials = [Trial(c3d) for c3d in c3ds]
        maintitle = ('Kinematics consistency plot, session %s' %
                     op.split(sessions[0])[-1])
        plot_plotly.plot_trials_browser(trials, layout,
                                        legend_type='short_name_with_tag',
                                        maintitle=None)

    else:
        raise ValueError('Invalid backend')

