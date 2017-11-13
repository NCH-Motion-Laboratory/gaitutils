# -*- coding: utf-8 -*-
"""

c3d unit tests for gaitutils
automatically run by 'nose2'

@author: jussi (jnu@iki.fi)
"""

import os.path as op
import numpy as np
import sys
from nose.tools import (assert_set_equal, assert_in, assert_equal,
                        assert_raises, assert_true)
from numpy.testing import assert_allclose
from shutil import copyfile
from PyQt5 import uic, QtGui, QtWidgets
import logging

from gaitutils.config import cfg
from gaitutils.numutils import segment_angles, best_match
from gaitutils import eclipse, Trial
from gaitutils.utils import detect_forceplate_events
from gaitutils.nexus_scripts import nexus_menu

# load default cfg so that user settings will not affect testing
cfg.load_default()
logger = logging.getLogger(__name__)


def _subj_path(subject, trial):
    """Return path to subject trial file"""
    return op.join('testdata', 'test_subjects', subject, 'test_session',
                   trial)


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
    c3dfile = _subj_path('adult_3fp', 'astrid_080515_02.c3d')
    valid = detect_forceplate_events(c3dfile)['valid']
    assert_equal(valid, 'LR')
    c3dfile = _subj_path('runner', 'JL brooks 2,8 51.c3d')
    valid = detect_forceplate_events(c3dfile)['valid']
    assert_equal(valid, 'LR')
    c3dfile = _subj_path('girl6v', '2015_10_22_girl6v_IN02.c3d')
    valid = detect_forceplate_events(c3dfile)['valid']
    assert_equal(valid, 'R')
    # detect slight overstep (toeoff not on plate)
    c3d1 = 'testdata/test_c3ds/slight_overstep.c3d'
    valid = detect_forceplate_events(c3d1)['valid']
    assert_equal(valid, '')
    # detect double contact (both feet on plate)
    c3d2 = 'testdata/test_c3ds/double_contact.c3d'
    valid = detect_forceplate_events(c3d2)['valid']
    assert_equal(valid, '')
    # almost overstepped but should be flagged as ok
    c3d3 = 'testdata/test_c3ds/barely_ok.c3d'
    valid = detect_forceplate_events(c3d3)['valid']
    assert_equal(valid, 'R')
    # inside but on the edge
    c3d4 = 'testdata/test_c3ds/side_edge.c3d'
    valid = detect_forceplate_events(c3d4)['valid']
    assert_equal(valid, 'L')

