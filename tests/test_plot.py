# -*- coding: utf-8 -*-
"""

Test plotting functions.

@author: Jussi (jnu@iki.fi)
"""

import pytest
import logging
import tempfile

from gaitutils.viz import plots, timedist, layouts
from gaitutils import sessionutils, trial, cfg
from utils import _file_path

logger = logging.getLogger(__name__)


# test session
sessiondir_ = 'test_subjects/D0063_RR/2018_12_17_preOp_RR'
sessiondir_abs = _file_path(sessiondir_)
sessiondir2_ = 'test_subjects/D0063_RR/2018_12_17_preOp_tuet_RR'
sessiondir2_abs = _file_path(sessiondir2_)
sessions = [sessiondir_abs, sessiondir2_abs]
tmpdir = tempfile.gettempdir()


def test_check_layout():
    """Check layout checker"""
    with pytest.raises(TypeError):
        layouts._check_layout('a')
    with pytest.raises(TypeError):
        layouts._check_layout(['foo'])
    with pytest.raises(TypeError):
        layouts._check_layout([['foo'], []])
    with pytest.raises(TypeError):
        layouts._check_layout([['foo'], 'a'])
    lout = [['a', 'b'], ['c', 'd'], ['e', 'f']]  # being unimaginative here
    assert layouts._check_layout(lout) == (3, 2)


def test_rm_dead_channels():
    """Test removing dead chs from EMG layout"""
    cfg.emg.autodetect_bads = True    
    c3ds = sessionutils.get_c3ds(sessiondir2_abs, trial_type='dynamic')
    emgs = [trial.Trial(fn).emg for fn in c3ds]
    emg = emgs[0]
    lout = [
        ['LGlut', 'RGlut'],
        ['LHam', 'RHam'],
        ['LRec', 'RRec'],
        ['LVas', 'RVas'],
        ['LTibA', 'RTibA'],
        ['LPer', 'RPer'],
        ['LGas', 'RGas'],
        ['LSol', 'RSol'],
    ]
    lout_ = [
        ['LHam', 'RHam'],
        ['LRec', 'RRec'],
        ['LTibA', 'RTibA'],
        ['LPer', 'RPer'],
        ['LGas', 'RGas'],
        ['LSol', 'RSol'],
    ]
    # assert that Glut and Vas get removed for both single and multiple EMG
    # instances
    assert layouts._rm_dead_channels(emg, lout) == lout_
    assert layouts._rm_dead_channels(emgs, lout) == lout_
    cfg.emg.autodetect_bads = False


def test_plot_trials():
    """Test individual trial plotter"""
    c3ds = sessionutils.get_c3ds(sessiondir_abs)
    trials = [trial.Trial(fn) for fn in c3ds]
    for backend in ['plotly', 'matplotlib']:
        # XXX: we don't test the figs for the time being
        fig = plots.plot_trials(trials, backend=backend)
        # fig = plots.plot_trials(trials, backend='plotly')
        tr = trials[0]
        # test different cycle args
        fig = plots.plot_trials(tr, cycles='all', backend=backend)
        fig = plots.plot_trials(tr, cycles='forceplate', backend=backend)
        fig = plots.plot_trials(tr, cycles='unnormalized', backend=backend)
        with pytest.raises(ValueError):
            fig = plots.plot_trials(tr, cycles='foo', backend=backend)
        fig = plots.plot_trials(tr, cycles={'emg': 'all'}, backend=backend)
        fig = plots.plot_trials(tr, cycles={'emg': 0}, backend=backend)


def test_plot_sessions():
    """Test individual trial plotter"""
    for backend in ['plotly', 'matplotlib']:
        fig = plots._plot_sessions(sessions, backend=backend)


def test_plot_session_average():
    for backend in ['plotly', 'matplotlib']:
        fig = plots._plot_session_average(sessiondir_abs, backend=backend)


def test_plot_trial_velocities():
    for backend in ['plotly', 'matplotlib']:
        fig = plots.plot_trial_velocities(sessiondir_abs, backend=backend)


def test_plot_trial_timedep_velocities():
    for backend in ['plotly', 'matplotlib']:
        fig = plots.plot_trial_timedep_velocities(sessiondir_abs, backend=backend)


def test_timedist_average():
    for backend in ['plotly', 'matplotlib']:
        fig = timedist.plot_session_average(sessiondir2_abs, backend=backend)


def test_timedist_comparison():
    for backend in ['plotly', 'matplotlib']:
        fig = timedist.plot_comparison(sessions, backend=backend)
