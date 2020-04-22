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
from matplotlib.figure import Figure

import gaitutils
from gaitutils import nexus, utils, models, read_data, cfg
from gaitutils.trial import Trial
from gaitutils.viz import plots
from gaitutils.utils import detect_forceplate_events
from utils import _trial_path, start_nexus

# this global is a 'caching' mechanism for starting Nexus and acquiring the
# ViconNexus control object
vicon = None


@pytest.mark.nexus
def test_nexus_reader():
    """Test basic data reading and Trial instance creation"""
    global vicon
    if vicon is None:
        vicon = start_nexus()
    # from old Helsinki lab
    trialname = '2015_10_22_girl6v_IN13'
    subject = 'girl6v'
    trialpath = _trial_path(subject, trialname)
    nexus._open_trial(trialpath)
    tr = Trial(vicon)
    assert_equal(tr.analograte, 1000.0)
    assert_equal(tr.framerate, 100.0)
    # assert_equal(tr.bodymass, 24.0)
    assert_equal(tr.name, 'Iiris')
    assert_equal(tr.n_forceplates, 1)
    assert_equal(tr.samplesperframe, 10.0)
    assert_equal(tr.length, 488)
    assert_equal(tr.trialname, trialname)
    assert_equal(tr.ncycles, 5)
    assert_equal(tr.offset, 1)
    cycs = tr.get_cycles({'R': 'all'})
    cyc = cycs[1]
    assert_equal(cyc.start, 230)
    assert_equal(cyc.end, 321)
    assert_equal(cyc.context, 'R')
    assert_equal(cyc.on_forceplate, True)
    assert_equal(cyc.toeoff, 282)
    cyc = cycs[0]
    assert_equal(cyc.start, 145)
    assert_equal(cyc.context, 'R')
    assert_equal(cyc.on_forceplate, False)
    # from Trondheim
    trialname = 'astrid_080515_02'
    subject = 'adult_3fp'
    trialpath = _trial_path(subject, trialname)
    nexus._open_trial(trialpath)
    tr = Trial(vicon)
    assert_equal(tr.analograte, 1000.0)
    assert_equal(tr.framerate, 200.0)
    # assert_equal(tr.bodymass, 70.0)
    assert_equal(tr.name, 'Astrid')
    assert_equal(tr.n_forceplates, 3)
    assert_equal(tr.samplesperframe, 5.0)
    assert_equal(tr.length, 1986)
    assert_equal(tr.trialname, trialname)
    assert_equal(tr.ncycles, 4)
    assert_equal(tr.offset, 1)
    cycs = tr.get_cycles({'L': 'all'})
    cyc = cycs[1]
    assert_equal(cyc.start, 1161)
    assert_equal(cyc.end, 1387)
    assert_equal(cyc.context, 'L')
    assert_equal(cyc.on_forceplate, True)
    assert_equal(cyc.toeoff, 1303)


@pytest.mark.nexus
def test_nexus_plot():
    """Test basic plot from Nexus"""
    global vicon
    if vicon is None:
        vicon = start_nexus()
    trialname = '2015_10_22_girl6v_IN13'
    subject = 'girl6v'
    trialpath = _trial_path(subject, trialname)
    nexus._open_trial(trialpath)
    tr = Trial(vicon)
    pl = plots.plot_trials([tr], backend='matplotlib')
    assert isinstance(pl, Figure)


@pytest.mark.nexus
def test_compare_to_c3d():
    """Compare data reads from Nexus and corresponding Nexus written .c3d"""
    global vicon
    if vicon is None:
        vicon = start_nexus()
    # set the correct EMG device name for the old data
    cfg.emg.devname = 'Myon'
    # can only get 3 decimals of agreement between Nexus/c3d model vars (??)
    NDEC = 3
    # vars to test
    modelvars = models.pig_lowerbody.varlabels.keys()
    emg_chs = cfg.emg.channel_labels.keys()
    subj = 'girl6v'
    trialname = '2015_10_22_girl6v_IN03.c3d'
    trialpath = _trial_path(subj, trialname)
    nexus._open_trial(trialpath)
    tr_nexus = Trial(vicon)
    tr_c3d = Trial(trialpath)
    # metadata
    attrs = [
        'analograte',
        'framerate',
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
        xn, dn = tr_nexus.get_model_data(var)
        assert_array_equal(xn, range(tr_nexus.length))
        xc, dc = tr_c3d.get_model_data(var)
        assert_array_equal(xc, range(tr_nexus.length))
        assert_array_almost_equal(dn, dc, decimal=NDEC)
    # read normalized model and compare
    for j in range(4):
        for var in modelvars:
            xn, dn = tr_nexus.get_model_data(var, j)
            xc, dc = tr_c3d.get_model_data(var, j)
            assert_array_equal(xn, np.arange(101))
            assert_array_equal(xc, np.arange(101))
            assert_array_almost_equal(dn, dc, decimal=NDEC)
    # read unnormalized EMG and compare
    for ch in emg_chs:
        xn, dn = tr_nexus.get_emg_data(ch)
        xc, dc = tr_c3d.get_emg_data(ch)
        assert_array_equal(xn, np.arange(tr_nexus.length * tr_nexus.samplesperframe))
        assert_array_equal(xn, xc)
        assert_array_almost_equal(dn, dc, decimal=NDEC)
    # read normalized EMG and compare
    for j in range(4):
        for ch in emg_chs:
            xn, dn = tr_nexus.get_emg_data(ch, j)
            xc, dc = tr_c3d.get_emg_data(ch, j)
            assert_array_equal(xn, xc)
            assert_array_almost_equal(dn, dc, decimal=NDEC)


@pytest.mark.nexus
def test_event_marking():
    """Test automarking of events"""
    global vicon
    if vicon is None:
        vicon = start_nexus()
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
                    assert abs(ev - events[j]) <= ev_tol

    subj = 'girl6v'
    trialname = '2015_10_22_girl6v_IN02.c3d'
    trialpath = _trial_path(subj, trialname)
    nexus._open_trial(trialpath)

    # automatic thresholding (do not respect fp events)
    vicon.ClearAllEvents()
    utils.automark_events(vicon, events_range=[-1500, 1500])
    _events_check(events_dict_nofp)

    # using forceplate thresholds
    vicon.ClearAllEvents()
    fpe = utils.detect_forceplate_events(vicon)
    mkrdata = read_data.get_marker_data(
        vicon, cfg.autoproc.left_foot_markers + cfg.autoproc.right_foot_markers
    )
    vel = utils._get_foot_contact_vel(mkrdata, fpe)
    utils.automark_events(
        vicon, vel_thresholds=vel, events_range=[-1500, 1500], fp_events=fpe
    )
    _events_check(events_dict)
