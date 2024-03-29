# -*- coding: utf-8 -*-
"""

Unit tests for utils.py misc functions.

@author: jussi (jnu@iki.fi)
"""

import numpy as np
import logging
import pytest
from numpy.testing import assert_allclose

from gaitutils.utils import (
    is_plugingait_set,
    _point_in_poly,
    _pig_markerset,
    _check_markers_flipped,
    marker_gaps,
)
from utils import _file_path


logger = logging.getLogger(__name__)

trial_enf = _file_path('anon.Trial.enf')
trial_enf_write = _file_path('writetest.enf')


def test_marker_gaps():
    """Test marker_gaps"""
    mdata = np.random.randn(1000, 3)
    assert not marker_gaps(mdata)
    mdata[100:200, :] = 0
    gaps = marker_gaps(mdata)
    assert_allclose(gaps, np.arange(100, 200))
    mdata[0, :] = 0
    gaps = marker_gaps(mdata)
    assert 0 not in gaps
    gaps = marker_gaps(mdata, ignore_edge_gaps=False)
    assert 0 in gaps


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
    assert not list(_check_markers_flipped(mkrdata))
    # flip heel and toe markers
    mkrdata['LHEE'] = np.atleast_2d([0, 1.5, 0])
    mkrdata['LTOE'] = np.atleast_2d([0, 1, 0])
    assert list(_check_markers_flipped(mkrdata))


def test_point_in_poly():
    poly = np.array([[1, 1, 0], [1, 0, 0], [0, 0, 0], [0, 1, 0]])
    pt = np.array([1.0001, 1.0001, 0])
    assert not _point_in_poly(poly, pt)
    pt = np.array([0.5, 0.5, 0])
    assert _point_in_poly(poly, pt)
