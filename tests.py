# -*- coding: utf-8 -*-
"""

unit tests for gaitutils
automatically run by 'nose2'

@author: jussi (jnu@iki.fi)
"""

from gaitutils.numutils import segment_angles, best_match
from gaitutils import eclipse
import numpy as np
from nose.tools import (assert_set_equal, assert_in, assert_equal,
                        assert_raises)
from numpy.testing import assert_allclose
from shutil import copyfile

trial_enf = 'testdata/anon.Trial.enf'
trial_enf_write = 'testdata/writetest.enf'


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


def test_best_match():
    v = [1, 2, 3, 2]
    b = [1, 2.1, 3.1]
    r = [1, 2.1, 3.1, 2.1]
    assert_allclose(best_match(v, b), r)
    b = []
    assert_allclose(best_match(v, b), v)


def test_enf_reader():
    edi = eclipse.get_eclipse_keys(trial_enf)
    assert('STAGES' not in edi)  # empty
    assert_equal(len(edi), 7)
    desc = edi['DESCRIPTION']
    assert_equal(desc, u'ok, no contact, forward')
    edi_full = eclipse.get_eclipse_keys(trial_enf, return_empty=True)
    assert_equal(len(edi_full), 16)
    assert('STAGES' in edi_full)  # empty but should be read now
    uni_ok = all([type(val) == unicode for val in edi_full.values()])
    assert(uni_ok)
    assert_raises(IOError, eclipse.get_eclipse_keys, 'no.enf')


def test_enf_writer():
    copyfile(trial_enf, trial_enf_write)  # make a fresh copy
    edi_set = {'DESCRIPTION': 'testing', 'NEWKEY': 'value'}
    eclipse.set_eclipse_keys(trial_enf_write, edi_set, update_existing=False)
    edi = eclipse.get_eclipse_keys(trial_enf_write)
    assert_equal(edi['DESCRIPTION'], 'ok, no contact, forward')  # no update
    assert_equal(edi['NEWKEY'], 'value')
    eclipse.set_eclipse_keys(trial_enf_write, edi_set, update_existing=True)
    edi = eclipse.get_eclipse_keys(trial_enf_write)
    assert_equal(edi['DESCRIPTION'], 'testing')
    assert_raises(IOError, eclipse.set_eclipse_keys, 'no.enf', {})
