# -*- coding: utf-8 -*-
"""

Misc unit tests.

@author: jussi (jnu@iki.fi)
"""

import pytest
import numpy as np
from numpy.testing import assert_allclose
import logging

from gaitutils.numutils import segment_angles, best_match, rms
#from utils import _file_path, cfg


logger = logging.getLogger(__name__)


def test_segment_angles():
    P = np.random.randn(1000, 4)  # invalid dims
    with pytest.raises(ValueError):
        segment_angles(P)
    P = np.random.randn(1000, 5, 3)
    a = segment_angles(P)
    assert a.shape == (1000, 3)
    # singular (identical successive points)
    P = np.array([0, 0, 0, 0, 0, 0, 1, 1, 0, 1, 3, 0]).reshape(4, 3)
    ang = np.array([np.nan, 135.0])
    assert_allclose(ang, segment_angles(P) / np.pi * 180)


def test_best_match():
    v = [1, 2, 3, 2]
    b = [1, 2.1, 3.1]
    r = [1, 2.1, 3.1, 2.1]
    assert_allclose(best_match(v, b), r)
    b = []
    assert_allclose(best_match(v, b), v)


def test_rms():
    """Test RMS computation"""
    x = np.ones(10)
    assert_allclose(rms(x, 5), x)
    with pytest.raises(ValueError):
        rms(x, 11)
    # edge vals are repeated due to 'reflect' padding
    arms = np.array([2.1602469, 1.29099445, 2.1602469, 3.10912635, 4.0824829,
                    5.06622805, 6.05530071, 7.04745817, 8.04155872, 7.04745817])
    assert_allclose(rms(np.arange(10), win=3), arms)


