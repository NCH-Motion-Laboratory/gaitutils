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
from utils import _file_path, cfg


logger = logging.getLogger(__name__)

trial_enf = _file_path('anon.Trial.enf')
trial_enf_write = _file_path('writetest.enf')


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

