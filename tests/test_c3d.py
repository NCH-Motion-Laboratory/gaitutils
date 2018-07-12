# -*- coding: utf-8 -*-
"""

c3d unit tests.

@author: jussi (jnu@iki.fi)
"""

from nose.tools import (assert_set_equal, assert_in, assert_equal,
                        assert_raises, assert_true)
from numpy.testing import assert_allclose
import logging

from gaitutils.config import cfg
from gaitutils import Trial
from gaitutils.utils import detect_forceplate_events
from utils import run_tests_if_main, _subj_path


# load default cfg so that user settings will not affect testing
cfg.load_default()
logger = logging.getLogger(__name__)


def test_c3d_metadata():
    """Test basic c3d reading for different files"""
    # Lastenlinna
    c3dfile = _subj_path('girl6v', '2015_10_22_girl6v_IN02.c3d')
    tr = Trial(c3dfile)
    assert_equal(tr.analograte, 1000.)
    assert_equal(tr.framerate, 100.)
    assert_allclose(tr.bodymass, 24.)
    assert_equal(tr.name, 'Iiris')
    assert_equal(tr.n_forceplates, 1)
    assert_equal(tr.length, 794)
    assert_equal(tr.samplesperframe, 10.0)
    # 3-fp system
    c3dfile = _subj_path('adult_3fp', 'astrid_080515_02.c3d')
    tr = Trial(c3dfile)
    assert_equal(tr.analograte, 1000.)
    assert_equal(tr.framerate, 200.)
    assert_allclose(tr.bodymass, 65.59999, rtol=1e-4)
    assert_equal(tr.name, 'Astrid')
    assert_equal(tr.n_forceplates, 3)
    assert_equal(tr.length, 639)
    assert_equal(tr.samplesperframe, 5)
    # 5-fp system
    c3dfile = _subj_path('runner', 'JL brooks 2,8 51.c3d')
    tr = Trial(c3dfile)
    assert_equal(tr.analograte, 1500.)
    assert_equal(tr.framerate, 300.)
    assert_allclose(tr.bodymass, 74., rtol=1e-4)
    assert_equal(tr.name, 'JL')
    assert_equal(tr.n_forceplates, 5)
    assert_equal(tr.length, 391)
    assert_equal(tr.samplesperframe, 5)


def test_c3d_fp_detection():
    """Test autodetection of forceplate events"""
    BOTH_OK = set(['L', 'R'])
    L_OK = set(['L'])
    R_OK = set(['R'])
    NOT_OK = set()
    c3dfile = _subj_path('adult_3fp', 'astrid_080515_02.c3d')
    valid = detect_forceplate_events(c3dfile)['valid']
    assert_equal(valid, BOTH_OK)
    c3dfile = _subj_path('runner', 'JL brooks 2,8 51.c3d')
    valid = detect_forceplate_events(c3dfile)['valid']
    assert_equal(valid, BOTH_OK)
    c3dfile = _subj_path('girl6v', '2015_10_22_girl6v_IN02.c3d')
    valid = detect_forceplate_events(c3dfile)['valid']
    assert_equal(valid, R_OK)
    # detect slight overstep (toeoff not on plate)
    c3d1 = 'testdata/test_c3ds/slight_overstep.c3d'
    valid = detect_forceplate_events(c3d1)['valid']
    assert_equal(valid, NOT_OK)
    # detect double contact (both feet on plate)
    c3d2 = 'testdata/test_c3ds/double_contact.c3d'
    valid = detect_forceplate_events(c3d2)['valid']
    assert_equal(valid, NOT_OK)
    # almost overstepped but should be flagged as ok - disabled for now
    # c3d3 = 'testdata/test_c3ds/barely_ok.c3d'
    # valid = detect_forceplate_events(c3d3)['valid']
    # assert_equal(valid, R_OK)
    # inside but on the edge
    c3d4 = 'testdata/test_c3ds/side_edge.c3d'
    valid = detect_forceplate_events(c3d4)['valid']
    assert_equal(valid, L_OK)
    c3d4 = 'testdata/test_c3ds/adult_barely_overstepped.c3d'
    valid = detect_forceplate_events(c3d4)['valid']
    assert_equal(valid, NOT_OK)
    c3d4 = 'testdata/test_c3ds/adult_almost_overstepped.c3d'
    valid = detect_forceplate_events(c3d4)['valid']
    assert_equal(valid, L_OK)
    c3d4 = 'testdata/test_c3ds/adult_overstep.c3d'
    valid = detect_forceplate_events(c3d4)['valid']
    assert_equal(valid, NOT_OK)
    c3d4 = 'testdata/test_c3ds/adult_ok.c3d'
    valid = detect_forceplate_events(c3d4)['valid']
    assert_equal(valid, L_OK)


run_tests_if_main()
