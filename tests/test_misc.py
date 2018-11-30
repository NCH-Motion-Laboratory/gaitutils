# -*- coding: utf-8 -*-
"""

Misc unit tests.

@author: jussi (jnu@iki.fi)
"""

import pytest
import numpy as np
from numpy.testing import assert_allclose
from shutil import copyfile
import logging

from gaitutils.config import cfg
from gaitutils.numutils import segment_angles, best_match
from gaitutils import eclipse
from gaitutils.utils import (is_plugingait_set, check_plugingait_set,
                             _point_in_poly, _pig_markerset)
from utils import run_tests_if_main, _file_path


# load default cfg so that user settings will not affect testing
cfg.load_default()
logger = logging.getLogger(__name__)

trial_enf = _file_path('anon.Trial.enf')
trial_enf_write = _file_path('writetest.enf')


def test_is_plugingait_set():
    pig = _pig_markerset()
    assert is_plugingait_set(pig)
    pig = _pig_markerset(fullbody=False, sacr=True)
    assert is_plugingait_set(pig)
    pig = _pig_markerset(fullbody=True, sacr=False)
    assert is_plugingait_set(pig)
    pig = _pig_markerset(fullbody=False, sacr=False)
    assert is_plugingait_set(pig)
    pig = _pig_markerset(fullbody=False, sacr=False)
    # delete 1 marker at a time from lowerbody set
    for mkr in pig:
        pig_ = {k: v for k, v in pig.items() if k != mkr}
        assert not is_plugingait_set(pig_)


def test_check_plugingait_set():
    mkrdata = _pig_markerset()
    # fake some marker data
    # pelvis and feet aligned
    mkrdata['SACR'] = np.atleast_2d([1, 0, 5])
    mkrdata['LASI'] = np.atleast_2d([0, 1, 5])
    mkrdata['RASI'] = np.atleast_2d([2, 1, 5])
    mkrdata['RHEE'] = np.atleast_2d([2, 1, 0])
    mkrdata['RTOE'] = np.atleast_2d([2, 1.5, 0])
    mkrdata['LHEE'] = np.atleast_2d([0, 1, 0])
    mkrdata['LTOE'] = np.atleast_2d([0, 1.5, 0])
    assert check_plugingait_set(mkrdata)
    # flip heel and toe markers
    mkrdata['LHEE'] = np.atleast_2d([0, 1.5, 0])
    mkrdata['LTOE'] = np.atleast_2d([0, 1, 0])
    assert not check_plugingait_set(mkrdata)


def test_point_in_poly():
    poly = np.array([[1, 1, 0], [1, 0, 0], [0, 0, 0], [0, 1, 0]])
    pt = np.array([1.0001, 1.0001, 0])
    assert not _point_in_poly(poly, pt)
    pt = np.array([.5, .5, 0])
    assert _point_in_poly(poly, pt)


def test_segment_angles():
    P = np.random.randn(1000, 4)  # invalid dims
    with pytest.raises(ValueError):
        segment_angles(P)
    P = np.random.randn(1000, 5, 3)
    a = segment_angles(P)
    assert a.shape == (1000, 3)
    # singular (identical successive points)
    P = np.array([0, 0, 0, 0, 0, 0, 1, 1, 0, 1, 3, 0]).reshape(4, 3)
    ang = np.array([np.nan, 135.])
    assert_allclose(ang, segment_angles(P)/np.pi * 180)


def test_best_match():
    v = [1, 2, 3, 2]
    b = [1, 2.1, 3.1]
    r = [1, 2.1, 3.1, 2.1]
    assert_allclose(best_match(v, b), r)
    b = []
    assert_allclose(best_match(v, b), v)


def test_enf_reader():
    edi = eclipse.get_eclipse_keys(trial_enf)
    assert 'STAGES' not in edi  # empty
    assert len(edi) == 7
    desc = edi['DESCRIPTION']
    assert desc == u'ok, no contact, forward'
    edi_full = eclipse.get_eclipse_keys(trial_enf, return_empty=True)
    assert len(edi_full) == 16
    assert 'STAGES' in edi_full  # empty but should be read now
    uni_ok = all([type(val) == unicode for val in edi_full.values()])
    assert uni_ok
    with pytest.raises(IOError):
        eclipse.get_eclipse_keys('no.enf')


def test_enf_writer():
    copyfile(trial_enf, trial_enf_write)  # make a fresh copy
    edi_set = {'DESCRIPTION': 'testing', 'NEWKEY': 'value'}
    eclipse.set_eclipse_keys(trial_enf_write, edi_set, update_existing=False)
    edi = eclipse.get_eclipse_keys(trial_enf_write)
    assert edi['DESCRIPTION'] == 'ok, no contact, forward'
    assert edi['NEWKEY'] == 'value'
    eclipse.set_eclipse_keys(trial_enf_write, edi_set, update_existing=True)
    edi = eclipse.get_eclipse_keys(trial_enf_write)
    assert edi['DESCRIPTION'] == 'testing'
    with pytest.raises(IOError):
        eclipse.set_eclipse_keys('no.enf', {})


run_tests_if_main()
