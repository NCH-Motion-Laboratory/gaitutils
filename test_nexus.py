# -*- coding: utf-8 -*-
"""

unit tests for gaitutils requiring running instance of Vicon Nexus
automatically run by 'nose2'

@author: jussi (jnu@iki.fi)
"""


from gaitutils import nexus
from gaitutils.config import cfg
from gaitutils.numutils import segment_angles, best_match
from gaitutils import eclipse, Trial
from gaitutils.utils import detect_forceplate_events
import numpy as np
from nose.tools import (assert_set_equal, assert_in, assert_equal,
                        assert_raises)
from numpy.testing import assert_allclose
from shutil import copyfile
import os.path as op
    
# so that user settings will not affect testing
cfg.load_default()


if not nexus.pid():
    raise Exception('Start Vicon Nexus first')

vicon = nexus.viconnexus()


def _open_trial(trial):
    """Helper to open trial from test session"""
    nexus_sessionpath = 'testdata/test_session_IN'
    trial_ = op.abspath(op.join(nexus_sessionpath, trial))
    vicon.OpenTrial(trial_, 60)


def test_nexus_reader():
    _open_trial('2015_10_22_girl6v_IN02')
    tr = Trial(vicon)
    assert_equal(tr.analograte, 1000.)
    assert_equal(tr.framerate, 100.)
    assert_equal(tr.bodymass, 24.)


def test_fp_detection():
    _open_trial('2015_10_22_girl6v_IN02')
    valid = detect_forceplate_events(vicon)['valid']
    assert_equal(valid, 'R')
    _open_trial('2015_10_22_girl6v_IN03')
    valid = detect_forceplate_events(vicon)['valid']
    assert_equal(valid, 'R')
    _open_trial('2015_10_22_girl6v_IN06')
    valid = detect_forceplate_events(vicon)['valid']
    assert_equal(valid, '')
    
    
    

