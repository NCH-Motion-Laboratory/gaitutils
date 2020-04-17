# -*- coding: utf-8 -*-
"""

Test plotting functions.

@author: Jussi (jnu@iki.fi)
"""

import pytest
import logging
import tempfile
import os.path as op

from gaitutils.viz import plots, timedist
from gaitutils import sessionutils, trial
from utils import _file_path

logger = logging.getLogger(__name__)


# test session
sessiondir_ = 'test_subjects/D0063_RR/2018_12_17_preOp_RR'
sessiondir_abs = _file_path(sessiondir_)
sessiondir2_ = 'test_subjects/D0063_RR/2018_12_17_preOp_tuet_RR'
sessiondir2_abs = _file_path(sessiondir2_)
sessiondir__ = op.split(sessiondir_)[-1]
sessions = [sessiondir_abs, sessiondir2_abs]
tmpdir = tempfile.gettempdir()


def test_plot_trials():
    """Test individual trial plotter"""
    c3ds = sessionutils.get_c3ds(sessiondir_abs)
    trials = [trial.Trial(fn) for fn in c3ds]
    fig = plots.plot_trials(trials, backend='matplotlib')
    # fig = plots.plot_trials(trials, backend='plotly')


def test_plot_sessions():
    """Test individual trial plotter"""
    fig = plots.plot_sessions(sessions, backend='matplotlib')


def test_plot_session_average():
    fig = plots.plot_session_average(sessiondir_abs, backend='matplotlib')


def test_plot_trial_velocities():
    fig = plots.plot_trial_velocities(sessiondir_abs, backend='matplotlib')


def test_plot_trial_timedep_velocities():
    fig = plots.plot_trial_timedep_velocities(sessiondir_abs, backend='matplotlib')


def test_timedist_average():
    fig = timedist.plot_session_average(sessiondir2_abs, backend='matplotlib')


def test_timedist_comparison():
    fig = timedist.plot_comparison(sessions, backend='matplotlib')
