# -*- coding: utf-8 -*-
"""

Unit tests for envutils.py misc functions.

@author: jussi (jnu@iki.fi)
"""

from gaitutils import envutils

import logging


logger = logging.getLogger(__name__)


def test_git_mode():
    """Assumes that tests are always run from a git repo"""
    assert envutils.git_mode


def test_named_tempfile():
    """Test _named_tempfile()"""
    tmp = envutils._named_tempfile(suffix='.tmp')
    assert tmp.suffix == '.tmp'
    assert tmp.parent.is_dir()
    
