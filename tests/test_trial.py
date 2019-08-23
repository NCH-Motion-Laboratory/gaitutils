# -*- coding: utf-8 -*-
"""

Test trial related functionality

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


def test_trial_metadata():
    """Test metadata reading from c3d"""
    # 1-forceplate system
    c3dfile = _trial_path('girl6v', '2015_10_22_girl6v_IN02.c3d')
    tr = Trial(c3dfile)
    # default tolerance of assert_allclose is 1e-7
    # could also use pytest.approx()
    assert_allclose(tr.analograte, 1000.)
    assert_equal(tr.framerate, 100.)
    assert_allclose(tr.subj_params['Bodymass'], 24.)
    assert_equal(tr.name, 'Iiris')
    assert_equal(tr.n_forceplates, 1)
    assert_equal(tr.length, 794)
    assert_equal(tr.samplesperframe, 10.0)
    # 3-fp system
    c3dfile = _trial_path('adult_3fp', 'astrid_080515_02.c3d')
    tr = Trial(c3dfile)
    assert_equal(tr.analograte, 1000.)
    assert_equal(tr.framerate, 200.)
    assert_allclose(tr.subj_params['Bodymass'], 65.59999, rtol=1e-4)
    assert_equal(tr.name, 'Astrid')
    assert_equal(tr.n_forceplates, 3)
    assert_equal(tr.length, 639)
    assert_equal(tr.samplesperframe, 5)
    # 5-fp system
    c3dfile = _trial_path('runner', 'JL brooks 2,8 51.c3d')
    tr = Trial(c3dfile)
    assert_equal(tr.analograte, 1500.)
    assert_equal(tr.framerate, 300.)
    assert_allclose(tr.subj_params['Bodymass'], 74., rtol=1e-4)
    assert_equal(tr.name, 'JL')
    assert_equal(tr.n_forceplates, 5)
    assert_equal(tr.length, 391)
    assert_equal(tr.samplesperframe, 5)

