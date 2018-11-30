# -*- coding: utf-8 -*-
"""

c3d unit tests.

@author: jussi (jnu@iki.fi)
"""


from numpy.testing import assert_allclose, assert_equal
import logging

from gaitutils.config import cfg
from gaitutils import Trial, c3d, read_data
from gaitutils.utils import detect_forceplate_events
from utils import run_tests_if_main, _trial_path, _c3d_path


# load default cfg so that user settings will not affect testing
cfg.load_default()
logger = logging.getLogger(__name__)


def test_c3d_metadata():
    """Test metadata reading from c3d"""
    # 1-forceplate system
    c3dfile = _trial_path('girl6v', '2015_10_22_girl6v_IN02.c3d')
    tr = Trial(c3dfile)
    # default tolerance of assert_allclose is 1e-7
    # could also use pytest.approx()
    assert_allclose(tr.analograte, 1000.)
    assert_equal(tr.framerate, 100.)
    assert_allclose(tr.bodymass, 24.)
    assert_equal(tr.name, 'Iiris')
    assert_equal(tr.n_forceplates, 1)
    assert_equal(tr.length, 794)
    assert_equal(tr.samplesperframe, 10.0)
    # 3-fp system
    c3dfile = _trial_path('adult_3fp', 'astrid_080515_02.c3d')
    tr = Trial(c3dfile)
    assert_equal(tr.analograte, 1000.)
    assert_equal(tr.framerate, 200.)
    assert_allclose(tr.bodymass, 65.59999, rtol=1e-4)
    assert_equal(tr.name, 'Astrid')
    assert_equal(tr.n_forceplates, 3)
    assert_equal(tr.length, 639)
    assert_equal(tr.samplesperframe, 5)
    # 5-fp system
    c3dfile = _trial_path('runner', 'JL brooks 2,8 51.c3d')
    tr = Trial(c3dfile)
    assert_equal(tr.analograte, 1500.)
    assert_equal(tr.framerate, 300.)
    assert_allclose(tr.bodymass, 74., rtol=1e-4)
    assert_equal(tr.name, 'JL')
    assert_equal(tr.n_forceplates, 5)
    assert_equal(tr.length, 391)
    assert_equal(tr.samplesperframe, 5)


def test_c3d_marker_data():
    """Test marker data reads from c3d"""
    # lowerbody PiG marker set
    c3dfile = _trial_path('girl6v', '2015_10_22_girl6v_IN02.c3d')
    assert read_data.get_marker_data(c3dfile)
    



def test_c3d_fp_detection():
    """Test forceplate contact detection on c3d files"""
    c3dfile = _trial_path('adult_3fp', 'astrid_080515_02.c3d')
    res = detect_forceplate_events(c3dfile)['coded']
    assert res == 'LRL'
    c3dfile = _trial_path('runner', 'JL brooks 2,8 51.c3d')
    res = detect_forceplate_events(c3dfile)['coded']
    assert res == '0RL00'
    c3dfile = _trial_path('girl6v', '2015_10_22_girl6v_IN02.c3d')
    res = detect_forceplate_events(c3dfile)['coded']
    assert res == 'R'
    # detect slight overstep (toeoff not on plate)
    c3d1 = _c3d_path('slight_overstep.c3d')
    res = detect_forceplate_events(c3d1)['coded']
    assert res == '0'
    # detect double contact (both feet on plate)
    c3d2 = _c3d_path('double_contact.c3d')
    res = detect_forceplate_events(c3d2)['coded']
    assert res == '0'
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
    assert res == '0'
    c3d4 = _c3d_path('adult_almost_overstepped.c3d')
    res = detect_forceplate_events(c3d4)['coded']
    assert res == 'L'
    c3d4 = _c3d_path('adult_overstep.c3d')
    res = detect_forceplate_events(c3d4)['coded']
    assert res == '0'
    c3d4 = _c3d_path('adult_ok.c3d')
    res = detect_forceplate_events(c3d4)['coded']
    assert res == 'L'


run_tests_if_main()
