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
from gaitutils.utils import (is_plugingait_set, check_plugingait_set)
from utils import run_tests_if_main, _file_path


# load default cfg so that user settings will not affect testing
cfg.load_default()
logger = logging.getLogger(__name__)

trial_enf = _file_path('anon.Trial.enf')
trial_enf_write = _file_path('writetest.enf')


def pig_mkrdata():
    """ Fullbody PiG marker data (empty values) """
    _pig = ['LFHD', 'RFHD', 'LBHD', 'RBHD', 'C7', 'T10', 'CLAV', 'STRN',
            'RBAK', 'LSHO', 'LELB', 'LWRA', 'LWRB', 'LFIN', 'RSHO', 'RELB',
            'RWRA', 'RWRB', 'RFIN', 'LASI', 'RASI', 'SACR', 'LTHI', 'LKNE',
            'LTIB', 'LANK', 'LHEE', 'LTOE', 'RTHI', 'RKNE', 'RTIB', 'RANK',
            'RHEE', 'RTOE']
    return {mkr: None for mkr in _pig}


def test_is_plugingait_set():
    pig = pig_mkrdata()
    assert is_plugingait_set(pig)
    pig.pop('SACR')  # ok
    assert not is_plugingait_set(pig)
    pig['RPSI'] = None
    pig['LPSI'] = None
    assert is_plugingait_set(pig)
    pig.pop('RHEE')  # not ok
    assert not is_plugingait_set(pig)


def test_check_plugingait_set():
    mkrdata = pig_mkrdata()
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
