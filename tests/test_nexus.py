# -*- coding: utf-8 -*-
"""

Unit tests on a running instance of Vicon Nexus.

@author: jussi (jnu@iki.fi)
"""

import pytest
import numpy as np
from numpy.testing import (
    assert_allclose,
    assert_array_equal,
    assert_array_almost_equal,
    assert_equal,
)

import gaitutils
from gaitutils import nexus, utils, models, read_data
from gaitutils.trial import Trial
from gaitutils.utils import detect_forceplate_events
from utils import _nexus_open_trial, _trial_path, start_nexus, cfg


vicon = None


@pytest.mark.nexus
def test_nexus_init_for_tests():
    """This is not really a test, it is initialization. However by marking it as
    Nexus test, we ensure that it only runs when we are running Nexus test
    (otherwise, we don't want to init Nexus)
    """
    global vicon
    start_nexus()
    vicon = nexus.viconnexus()


@pytest.mark.nexus
def test_nexus_reader():
    """Test loading & trial instance creation"""
    trialname = '2015_10_22_girl6v_IN03'
    _nexus_open_trial('girl6v', trialname)
    tr = Trial(vicon)
    assert_equal(tr.analograte, 1000.0)
    assert_equal(tr.framerate, 100.0)
    assert_equal(tr.bodymass, 24.0)
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

    trialname = 'astrid_080515_02'
    _nexus_open_trial('adult_3fp', trialname)
    tr = Trial(vicon)
    assert_equal(tr.analograte, 1000.0)
    assert_equal(tr.framerate, 200.0)
    assert_equal(tr.bodymass, 70.0)
    assert_equal(tr.name, 'Astrid')
    assert_equal(tr.n_forceplates, 3)
    assert_equal(tr.samplesperframe, 5.0)
    assert_equal(tr.length, 1986)
    assert_equal(tr.trialname, trialname)
    assert_equal(tr.ncycles, 4)
    assert_equal(tr.offset, 1)
    cyc = tr.get_cycle('R', 2)
    assert_equal(cyc.start, 1049)
    assert_equal(cyc.end, 1275)
    assert_equal(cyc.context, 'R')
    assert_equal(cyc.on_forceplate, True)
    assert_equal(cyc.toeoff, 1186)


@pytest.mark.nexus
def test_nexus_plot():
    """Test basic plot from Nexus"""
    trialname = '2015_10_22_girl6v_IN03'
    _nexus_open_trial('girl6v', trialname)
    pl = gaitutils.Plotter(interactive=False)
    pl.open_nexus_trial()
    pl.layout = [['HipAnglesX']]
    pl.plot_trial(model_cycles='all')


@pytest.mark.nexus
def test_fp_detection():
    """Test autodetection of forceplate contact"""
    BOTH_OK = set(['L', 'R'])
    L_OK = set(['L'])
    R_OK = set(['R'])
    NOT_OK = set()
    _nexus_open_trial('girl6v', '2015_10_22_girl6v_IN02')
    valid = detect_forceplate_events(vicon)['valid']
    assert_equal(valid, R_OK)
    _nexus_open_trial('girl6v', '2015_10_22_girl6v_IN03')
    valid = detect_forceplate_events(vicon)['valid']
    assert_equal(valid, R_OK)
    _nexus_open_trial('girl6v', '2015_10_22_girl6v_IN06')
    valid = detect_forceplate_events(vicon)['valid']
    assert_equal(valid, NOT_OK)


@pytest.mark.nexus
def test_read_data_compare_nexus_and_c3d():
    """Compare data reads from Nexus and corresponding Nexus written .c3d """
    # can only get 3 decimals of agreement between Nexus/c3d model vars (??)
    NDEC = 3
    # vars to test
    modelvars = models.pig_lowerbody.varlabels.keys()
    emg_chs = cfg.emg.channel_labels.keys()

    subj = 'girl6v'
    trialname = '2015_10_22_girl6v_IN03.c3d'
    _nexus_open_trial(subj, trialname)
    c3dfile = _trial_path(subj, trialname)
    tr_nexus = Trial(vicon)
    tr_c3d = Trial(c3dfile)
    # metadata
    attrs = [
        'analograte',
        'framerate',
        'bodymass',
        'name',
        'n_forceplates',
        'samplesperframe',
        'length',
        'trialname',
        'ncycles',
    ]
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
        assert_array_equal(xn, np.arange(tr_nexus.length * tr_nexus.samplesperframe))
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


@pytest.mark.nexus
def test_read_data_errors():
    """Test exceptions raised by invalid reads"""
    subj = 'girl6v'
    trialname = '2015_10_22_girl6v_IN03.c3d'
    _nexus_open_trial(subj, trialname)
    c3dfile = _trial_path(subj, trialname)
    tr_nexus = Trial(vicon)
    tr_c3d = Trial(c3dfile)
    assert_raises(KeyError, tr_nexus.__getitem__, 'foo')
    assert_raises(KeyError, tr_c3d.__getitem__, 'foo')


@pytest.mark.nexus
def test_event_marking():
    """Test automarking of events"""
    ev_tol = 4  # tolerance for event marking (frames)
    events_dict = dict()  # ground truth with forceplate info
    events_dict['Right'] = dict()
    events_dict['Right']['Foot Strike'] = [384, 505, 616]
    events_dict['Right']['Foot Off'] = [465, 570]
    events_dict['Left'] = dict()
    events_dict['Left']['Foot Strike'] = [311, 441, 562]
    events_dict['Left']['Foot Off'] = [402, 517]
    events_dict_nofp = dict()  # ground truth without forceplate info
    events_dict_nofp['Right'] = dict()
    events_dict_nofp['Right']['Foot Strike'] = [379, 501, 613]
    events_dict_nofp['Right']['Foot Off'] = [468, 572]
    events_dict_nofp['Left'] = dict()
    events_dict_nofp['Left']['Foot Strike'] = [310, 440, 561]
    events_dict_nofp['Left']['Foot Off'] = [401, 516]

    def _events_check(events_dict):
        """Helper to check whether Nexus events are close to ground truth"""
        for side, sidedict in events_dict.items():
            for event_type, events in sidedict.items():
                nexus_events = vicon.GetEvents(
                    vicon.GetSubjectNames()[0], side, event_type
                )[0]
                assert_equal(len(events), len(nexus_events))
                for j, ev in enumerate(nexus_events):
                    assert_less_equal(abs(ev - events[j]), ev_tol)

    _nexus_open_trial('girl6v', '2015_10_22_girl6v_IN02')

    # automatic thresholding (do not respect fp events)
    vicon.ClearAllEvents()
    nexus.automark_events(vicon, events_range=[-1500, 1500])
    _events_check(events_dict_nofp)

    # using forceplate thresholds
    vicon.ClearAllEvents()
    fpe = utils.detect_forceplate_events(vicon)
    mkrdata = read_data.get_marker_data(
        vicon, cfg.autoproc.left_foot_markers + cfg.autoproc.right_foot_markers
    )
    vel = utils._get_foot_contact_vel(mkrdata, fpe)
    nexus.automark_events(
        vicon, vel_thresholds=vel, events_range=[-1500, 1500], fp_events=fpe
    )
    _events_check(events_dict)
    vicon.SaveTrial(60)  # to prevent 'Save trial?' dialog on subsequent loads
