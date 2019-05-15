# -*- coding: utf-8 -*-
"""

Test the config interface

@author: jussi (jnu@iki.fi)
"""

import pytest
import numpy as np
from numpy.testing import assert_allclose
from shutil import copyfile
import logging
import pytest

from gaitutils.parse_config import parse_config, update_config, dump_config
from utils import run_tests_if_main, _file_path


logger = logging.getLogger(__name__)


def test_config():
    """Test reading of valid config"""
    fn = _file_path('valid.cfg')
    cfg_ = parse_config(fn)
    assert 'section1' in cfg_


def test_config_update():
    fn = _file_path('valid.cfg')
    cfg_ = parse_config(fn)
    fn = _file_path('updates.cfg')
    cfg_ = update_config(cfg_, fn)


def test_orphaned_def():
    """Test cfg with def outside section"""
    fn = _file_path('orphan.cfg')
    with pytest.raises(ValueError):
        parse_config(fn)


def test_invalid_def():
    """Test cfg with invalid def"""
    fn = _file_path('invalid.cfg')
    with pytest.raises(ValueError):
        parse_config(fn)


def test_dump_config():
    fn = _file_path('valid.cfg')
    cfg_ = parse_config(fn)
    txt = dump_config(cfg_)
    assert txt


run_tests_if_main()
