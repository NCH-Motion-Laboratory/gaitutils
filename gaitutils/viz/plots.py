# -*- coding: utf-8 -*-
"""
Higher level plotting functions (backend agnostic).

@author: Jussi (jnu@iki.fi)
"""

import logging

from .. import (cfg, layouts, trial, GaitDataError, sessionutils,
                stats)
from .plot_misc import get_backend


logger = logging.getLogger(__name__)


def plot_nexus_trial(layout_name=None, backend=None, model_cycles=None,
                     emg_cycles=None, maintitle=None, from_c3d=True):
    """Plot the currently loaded trial from Vicon Nexus"""

    backend_lib = get_backend(backend)

    tr = trial.nexus_trial(from_c3d=from_c3d)
    layout = layouts.get_layout(layout_name)
    layout = layouts.rm_dead_channels(tr.emg, layout)

    # force unnormalized plot for static trial
    model_cycles = 'unnormalized' if tr.is_static else model_cycles

    return backend_lib.plot_trials([tr], layout, model_cycles=model_cycles,
                                   emg_cycles=emg_cycles,
                                   legend_type='short_name_with_cyclename')


def plot_sessions(sessions, layout_name=None, tags=None, make_pdf=False,
                  style_by=None, color_by=None, legend_type=None,
                  model_cycles=None, emg_cycles=None,
                  backend=None, figtitle=None):
    """Plot tagged trials from given session(s)."""

    if not isinstance(sessions, list):
        sessions = [sessions]

    if tags is None:
        tags = cfg.eclipse.tags

    backend_lib = get_backend(backend)
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
    #emgs = [tr.emg for tr in trials]
    #layout = layouts.rm_dead_channels_multitrial(emgs, layout)

    return backend_lib.plot_trials(trials, layout, legend_type=legend_type,
                                   style_by=style_by, color_by=color_by,
                                   model_cycles=model_cycles,
                                   emg_cycles=emg_cycles,
                                   figtitle=figtitle)


def plot_session_average(session, layout_name=None, make_pdf=False,
                         backend=None):
    """Plot average of all session trials"""

    layout = layouts.get_layout(layout_name)
    backend_lib = get_backend(backend)

    c3ds = sessionutils.get_c3ds(session, trial_type='dynamic')
    if not c3ds:
        raise GaitDataError('No dynamic trials found for current session')

    atrial = stats.AvgTrial(c3ds)
    maintitle_ = '%d trial average from %s' % (atrial.nfiles, session)

    fig = backend_lib.plot_trials(atrial, layout, 
                                  model_stddev=atrial.stddev_data,
                                  figtitle=maintitle_)
    return fig
