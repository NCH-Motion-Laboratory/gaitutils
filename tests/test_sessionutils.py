# -*- coding: utf-8 -*-
"""

Test session utils.

@author: Jussi (jnu@iki.fi)
"""

import pytest
import logging
import tempfile
import os.path as op

from gaitutils import sessionutils, GaitDataError
from utils import _file_path

logger = logging.getLogger(__name__)


# test session
sessiondir_ = 'test_subjects/D0063_RR/2018_12_17_preOp_RR'
sessiondir_abs = _file_path(sessiondir_)
sessiondir2_ = 'test_subjects/D0063_RR/2018_12_17_preOp_tuet_RR'
sessiondir2_abs = _file_path(sessiondir2_)
sessiondir__ = op.split(sessiondir_)[-1]
sessions = [sessiondir_abs, sessiondir2_abs]
tmpdir = tempfile.gettempdir()


def test_get_c3ds():
    """Test c3ds getter"""
    # should get all
    c3ds = sessionutils.get_c3ds(sessiondir_abs)
    assert len(c3ds) == 22
    c3ds = sessionutils.get_c3ds(sessiondir_abs, trial_type='dynamic')
    assert len(c3ds) == 21
    c3ds = sessionutils.get_c3ds(sessiondir_abs, trial_type='static')
    assert len(c3ds) == 1
    c3ds = sessionutils.get_c3ds(sessiondir_abs, tags=['E1'])
    assert len(c3ds) == 1
    c3ds = sessionutils.get_c3ds(sessiondir_abs, tags=['foo'])
    assert len(c3ds) == 0


def test_get_enfs():
    """Test enfs getter"""
    # should get all
    enfs = sessionutils.get_enfs(sessiondir2_abs)
    assert len(enfs) == 13
    enfs = sessionutils.get_enfs(sessiondir2_abs, trial_type='dynamic')
    assert len(enfs) == 12
    enfs = sessionutils.get_enfs(sessiondir2_abs, trial_type='static')
    assert len(enfs) == 1
    enfs = sessionutils.get_enfs(sessiondir2_abs, tags=['E1'])
    assert len(enfs) == 1
    enfs = sessionutils.get_enfs(sessiondir2_abs, tags=['foo'])
    assert len(enfs) == 0


def test_get_tagged_dynamic_c3ds_from_sessions():
    """Test multisession c3ds getter"""
    c3ds = sessionutils._get_tagged_dynamic_c3ds_from_sessions(sessions)
    assert len(c3ds) == 33
    c3ds = sessionutils._get_tagged_dynamic_c3ds_from_sessions(
        sessions, tags=['E1', 'T1']
    )
    assert len(c3ds) == 4


def test_get_session_date():
    """Test date getter"""
    with pytest.raises(GaitDataError):
        date = sessionutils.get_session_date(tmpdir)
    date = sessionutils.get_session_date(sessiondir_abs)
    assert date.month == 12
    assert date.day == 17


def test_enf_to_trialfile():
    """Test trialname converter"""
    fn = sessionutils.enf_to_trialfile('foo.Trial.enf', 'c3d')
    assert fn == 'foo.c3d'
    fn = sessionutils.enf_to_trialfile('foo1.Trial01.enf', '.c3d')
    assert fn == 'foo1.c3d'
    with pytest.raises(GaitDataError):
        fn = sessionutils.enf_to_trialfile('foo1.trial01.enf', '.c3d')


def test_load_quirks():
    """Test quirks"""
    quirks = sessionutils.load_quirks(sessiondir_abs)
    assert 'emg_chs_disabled' in quirks
    assert 'LPer' in quirks['emg_chs_disabled']


def test_load_info():
    """Test info"""
    info = sessionutils.load_info(sessiondir_abs)
    for key in ['hetu', 'fullname', 'session_description']:
        assert key in info
        assert info[key]
        