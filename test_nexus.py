# -*- coding: utf-8 -*-
"""

unit tests for gaitutils requiring running instance of Vicon Nexus
automatically run by 'nose2'

@author: jussi (jnu@iki.fi)
"""


import numpy as np
from nose.tools import (assert_set_equal, assert_in, assert_equal,
                        assert_raises, assert_less_equal)
from numpy.testing import (assert_allclose, assert_array_equal,
                           assert_array_almost_equal)
import os.path as op
import os
import subprocess
import time

from gaitutils import nexus, utils, models
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
nexus_sessionpath = 'testdata/test_session_IN'


def _nexus_open_trial(trial):
    """Helper to open given trial from test session"""
    trial_ = op.abspath(op.join(nexus_sessionpath, trial))
    vicon.OpenTrial(trial_, 60)


def test_nexus_reader():
    """Test loading & trial instance creation"""
    trialname = '2015_10_22_girl6v_IN03'
    _nexus_open_trial(trialname)
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
    _nexus_open_trial('2015_10_22_girl6v_IN02')
    valid = detect_forceplate_events(vicon)['valid']
    assert_equal(valid, 'R')
    _nexus_open_trial('2015_10_22_girl6v_IN03')
    valid = detect_forceplate_events(vicon)['valid']
    assert_equal(valid, 'R')
    _nexus_open_trial('2015_10_22_girl6v_IN06')
    valid = detect_forceplate_events(vicon)['valid']
    assert_equal(valid, '')


def test_read_data_compare_nexus_and_c3d():
    """Compare data reads from Nexus and corresponding Nexus written .c3d """
    trialname = '2015_10_22_girl6v_IN03'
    NDEC = 3  # can only get 3 decimals of agreement between Nexus/c3d model vars (??)
    # vars to test
    modelvars = models.pig_lowerbody.varlabels.keys()
    emg_chs = cfg.emg.channel_labels.keys()
    c3dfile = op.join(nexus_sessionpath, trialname+'.c3d')
    _nexus_open_trial(trialname)
    tr_nexus = Trial(vicon)
    tr_c3d = Trial(c3dfile)
    # metadata
    attrs = ['analograte', 'framerate', 'bodymass', 'name', 'n_forceplates',
             'samplesperframe', 'length', 'trialname', 'ncycles']
    for attr in attrs:
        assert_equal(getattr(tr_nexus, attr), getattr(tr_c3d, attr))
    # model data
    for var in modelvars:
        # read unnormalized model and compare
        xn, dn = tr_nexus[var]
        assert_array_equal(xn, range(tr_nexus.length))
        xc, dc = tr_c3d[var]
        assert_array_equal(xc, range(tr_nexus.length))
        assert_array_almost_equal(dn, dc, decimal=NDEC)
    # read normalized model and compare
    for j in range(4):
        tr_nexus.set_norm_cycle(j)
        tr_c3d.set_norm_cycle(j)
        for var in modelvars:
            xn, dn = tr_nexus[var]
            xc, dc = tr_c3d[var]
            assert_array_equal(xn, np.arange(101))
            assert_array_equal(xc, np.arange(101))
            assert_array_almost_equal(dn, dc, decimal=NDEC)
    # read unnormalized EMG and compare
    tr_nexus.set_norm_cycle(None)
    tr_c3d.set_norm_cycle(None)
    for ch in emg_chs:
        xn, dn = tr_nexus[ch]
        xc, dc = tr_c3d[ch]
        assert_array_equal(xn,
                           np.arange(tr_nexus.length*tr_nexus.samplesperframe))
        assert_array_equal(xn, xc)
        assert_array_almost_equal(dn, dc, decimal=NDEC)
    # read normalized EMG and compare
    for j in range(4):
        tr_nexus.set_norm_cycle(j)
        tr_c3d.set_norm_cycle(j)
        for ch in emg_chs:
            xn, dn = tr_nexus[ch]
            xc, dc = tr_c3d[ch]
            assert_array_equal(xn, xc)
            assert_array_almost_equal(dn, dc, decimal=NDEC)


def test_read_data_errors():
    """Test exceptions raised by invalid reads"""
    trialname = '2015_10_22_girl6v_IN03'
    c3dfile = op.join(nexus_sessionpath, trialname+'.c3d')
    _nexus_open_trial(trialname)
    tr_nexus = Trial(vicon)
    tr_c3d = Trial(c3dfile)
    assert_raises(KeyError, tr_nexus.__getitem__, 'foo')
    assert_raises(KeyError, tr_c3d.__getitem__, 'foo')


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

    _nexus_open_trial('2015_10_22_girl6v_IN02')

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
