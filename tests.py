# -*- coding: utf-8 -*-
"""

unit tests for gaitutils
automatically run by 'nose2'

@author: jussi (jnu@iki.fi)
"""

from gaitutils.numutils import segment_angles
import numpy as np
from nose.tools import (assert_set_equal, assert_in, assert_equal,
                        assert_raises)
from numpy.testing import assert_allclose


def test_segment_angles():
    P = np.random.randn(1000, 4)  # invalid dims
    assert_raises(ValueError, segment_angles, P)
    P = np.random.randn(1000, 5, 3)
    a = segment_angles(P)
    assert_equal(a.shape, (1000, 3))
    # singular (identical successive points)
    P = np.array([0, 0, 0, 0, 0, 0, 1, 1, 0, 1, 3, 0]).reshape(4, 3)
    ang = np.array([np.nan, 135.])
    assert_allclose(ang, segment_angles(P)/np.pi * 180)


