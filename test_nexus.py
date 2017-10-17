# -*- coding: utf-8 -*-
"""

unit tests for gaitutils requiring running instance of Vicon Nexus
automatically run by 'nose2'

@author: jussi (jnu@iki.fi)
"""


import numpy as np
from nose.tools import (assert_set_equal, assert_in, assert_equal,
                        assert_raises, assert_less_equal)
from numpy.testing import assert_allclose
import os.path as op
import os
import subprocess
import time

from gaitutils import nexus, utils
from gaitutils.config import cfg
from gaitutils import Trial
from gaitutils.utils import detect_forceplate_events

cfg.load_default()  # so that user settings will not affect testing
if not nexus.pid():
    # try to start Nexus for tests...
    exe = op.join(cfg.general.nexus_path, 'Nexus.exe')
    # silence Nexus output
    blackhole = file(os.devnull, 'w')
    subprocess.Popen([exe], stdout=blackhole)
    time.sleep(9)
    if not nexus.pid():
        raise Exception('Please start Vicon Nexus first')

vicon = nexus.viconnexus()


def _open_trial(trial):
    """Helper to open given trial from test session"""
    nexus_sessionpath = 'testdata/test_session_IN'
    trial_ = op.abspath(op.join(nexus_sessionpath, trial))
    vicon.OpenTrial(trial_, 60)


def test_nexus_reader():
    """Test loading & trial instance creation"""
    trialname = '2015_10_22_girl6v_IN03'
    _open_trial(trialname)
    tr = Trial(vicon)
    assert_equal(tr.analograte, 1000.)
    assert_equal(tr.framerate, 100.)
    assert_equal(tr.bodymass, 24.)
    assert_equal(tr.name, 'Iiris')
    assert_equal(tr.n_forceplates, 1)
    assert_equal(tr.samplesperframe, 10.0)
    assert_equal(tr.length, 418)
    assert_equal(tr.trialname, trialname)
    assert_equal(tr.ncycles, 4)
    assert_equal(tr.offset, 1)
    cyc = tr.get_cycle('R', 1)
    assert_equal(cyc.start, 103)
    assert_equal(cyc.end, 195)
    assert_equal(cyc.context, 'R')
    assert_equal(cyc.on_forceplate, False)
    assert_equal(cyc.toeoff, 157)
    cyc = tr.get_cycle('R', 2)
    assert_equal(cyc.on_forceplate, True)


def test_fp_detection():
    """Test autodetection of forceplate contact"""
    _open_trial('2015_10_22_girl6v_IN02')
    valid = detect_forceplate_events(vicon)['valid']
    assert_equal(valid, 'R')
    _open_trial('2015_10_22_girl6v_IN03')
    valid = detect_forceplate_events(vicon)['valid']
    assert_equal(valid, 'R')
    _open_trial('2015_10_22_girl6v_IN06')
    valid = detect_forceplate_events(vicon)['valid']
    assert_equal(valid, '')


def test_event_marking():
    """Test automarking of events"""
    ev_tol = 3  # tolerance for event marking (frames)
    events_dict = dict()  # ground truth
    events_dict['Right'] = dict()
    events_dict['Right']['Foot Strike'] = [381, 503, 614]
    events_dict['Right']['Foot Off'] = [465, 570]
    events_dict['Left'] = dict()
    events_dict['Left']['Foot Strike'] = [311, 441, 562]
    events_dict['Left']['Foot Off'] = [402, 517]

    def _events_check(events_dict):
        """Helper to check whether Nexus events are close to ground truth"""
        for side, sidedict in events_dict.items():
            for event_type, events in sidedict.items():
                nexus_events = vicon.GetEvents(vicon.GetSubjectNames()[0],
                                               side, event_type)[0]
                assert_equal(len(events), len(nexus_events))
                for j, ev in enumerate(nexus_events):
                    assert_less_equal(abs(ev-events[j]), ev_tol)

    _open_trial('2015_10_22_girl6v_IN02')

    # automatic thresholding
    vicon.ClearAllEvents()
    nexus.automark_events(vicon, events_range=[-1500, 1500])
    _events_check(events_dict)

    # using forceplate thresholds
    vicon.ClearAllEvents()
    fpe = utils.detect_forceplate_events(vicon)
    vel = utils.get_foot_velocity(vicon, fpe)
    nexus.automark_events(vicon, vel_thresholds=vel,
                          events_range=[-1500, 1500], fp_events=fpe)
    _events_check(events_dict)
    vicon.SaveTrial(60)  # to prevent 'Save trial?' dialog on subsequent loads
