# -*- coding: utf-8 -*-
"""

c3d unit tests.
This is not super important since btk has its own test suite


@author: jussi (jnu@iki.fi)
"""

import pickle
import numpy as np
from numpy.testing import assert_allclose, assert_equal
import logging

from gaitutils import read_data, utils
from gaitutils.trial import Trial
from gaitutils.utils import detect_forceplate_events
from utils import _trial_path, _c3d_path, _file_path, cfg


logger = logging.getLogger(__name__)



def test_c3d_marker_data():
    """Test marker data reads from c3d"""
    # lowerbody PiG marker set
    c3dfile = _c3d_path('double_contact.c3d')
    mkrset = utils._pig_markerset().keys()
    mkrdata = read_data.get_marker_data(c3dfile, mkrset)
    assert utils.is_plugingait_set(mkrdata)
    assert len(mkrdata) == 5 * len(mkrset)  # vars = P*2, V, A & gaps
    # check array dimensions for all markers (gap data has different dims)
    for mkr in mkrdata:
        if '_gaps' not in mkr:
            assert mkrdata[mkr].shape == (442, 3)
    # LHEE gaps from 360 to 388
    assert_equal(mkrdata['LHEE_gaps'], np.arange(360, 389))
    lhee_file = _file_path('lhee_data.npy')
    lhee_data = np.load(lhee_file)
    # allow some deviation from saved reference data (was read using btk)
    assert_allclose(mkrdata['LHEE'], lhee_data, rtol=1e-4)


def test_c3d_analysis_data():
    """Test analysis var reads from c3d"""
    c3dfile = _c3d_path('double_contact.c3d')
    an_ = read_data.get_analysis(c3dfile, 'c3dtest')
    assert 'c3dtest' in an_
    an = an_['c3dtest']
    an_vars = ['Stride Time', 'Opposite Foot Off', 'Double Support',
               'Step Time', 'Single Support', 'Step Length', 'Foot Off',
               'Walking Speed', 'Stride Length', 'Opposite Foot Contact',
               'Cadence']
    assert all([var in an for var in an_vars])
    assert all(['Left' in an[var] for var in an_vars])
    assert all(['Right' in an[var] for var in an_vars])
    an_file = _file_path('analysis_testdata.p')
    an_g = pickle.load(open(an_file, 'rb'))
    for context in ['Left', 'Right']:
        assert_allclose(an_g['unknown'][var][context], an[var][context])


def test_c3d_fp_detection():
    """Test forceplate contact detection on c3d files"""
    c3dfile = _trial_path('adult_3fp', 'astrid_080515_02.c3d')
    res = detect_forceplate_events(c3dfile)['coded']
    assert res == 'LRL'
    c3dfile = _trial_path('runner', 'JL brooks 2,8 51.c3d')
    res = detect_forceplate_events(c3dfile)['coded']
    assert res == 'XRLXX'
    c3dfile = _trial_path('girl6v', '2015_10_22_girl6v_IN02.c3d')
    res = detect_forceplate_events(c3dfile)['coded']
    assert res == 'R'
    # detect slight overstep (toeoff not on plate)
    c3d1 = _c3d_path('slight_overstep.c3d')
    res = detect_forceplate_events(c3d1)['coded']
    assert res == 'X'
    # detect double contact (both feet on plate)
    c3d2 = _c3d_path('double_contact.c3d')
    res = detect_forceplate_events(c3d2)['coded']
    assert res == 'X'
    # almost overstepped but should be flagged as ok
    # too hard - disabled for now
    #c3d3 = 'testdata/test_c3ds/barely_ok.c3d'
    #res = detect_forceplate_events(c3d3)['coded']
    #assert res == 'R'
    # inside but on the edge
    c3d4 = _c3d_path('side_edge.c3d')
    res = detect_forceplate_events(c3d4)['coded']
    assert res == 'L'
    c3d4 = _c3d_path('adult_barely_overstepped.c3d')
    res = detect_forceplate_events(c3d4)['coded']
    assert res == 'X'
    c3d4 = _c3d_path('adult_almost_overstepped.c3d')
    res = detect_forceplate_events(c3d4)['coded']
    assert res == 'L'
    c3d4 = _c3d_path('adult_overstep.c3d')
    res = detect_forceplate_events(c3d4)['coded']
    assert res == 'X'
    c3d4 = _c3d_path('adult_ok.c3d')
    res = detect_forceplate_events(c3d4)['coded']
    assert res == 'L'

