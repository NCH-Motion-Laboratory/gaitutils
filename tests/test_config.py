# -*- coding: utf-8 -*-
"""

Test the config interface

@author: jussi (jnu@iki.fi)
"""

import pytest
import logging
import re

from gaitutils.configdot import (parse_config, update_config, dump_config,
                                 RE_COMMENT, RE_SECTION_HEADER, RE_VAR_DEF)
from utils import run_tests_if_main, _file_path


logger = logging.getLogger(__name__)


def test_re_comment():
    """Test comment regex on various comments"""
    cmt_string = 'this is a comment'
    for leading in ['', ' ', ' '*5]:
        for comment_sign in '#;':
            for ws1 in ['', ' ']:
                for trailing in [' '*5, ' '*3, '']:
                    cmt = (leading + comment_sign + ws1 + cmt_string +
                           trailing)
                    assert re.match(RE_COMMENT, cmt)
                    # the regex group will include trailing whitespace
                    # so test group extraction without whitespace
                    cmt = (leading + comment_sign + ws1 + cmt_string)
                    m = re.match(RE_COMMENT, cmt)
                    assert m.group(1) == cmt_string


def test_re_var_def():
    """Test item definition regex"""
    dli = list()
    # various whitespace
    dli = ['a=1', 'a = 1', ' a = 1 ']
    for d in dli:
        m = re.match(RE_VAR_DEF, d)
        assert m.group(1) == 'a'
        assert m.group(2) == '1'
    # definition of string with equals
    d = 'a = "b=1"'
    m = re.match(RE_VAR_DEF, d)
    assert m.group(1) == 'a'
    assert m.group(2) == '"b=1"'
    # no equals
    d = 'abc foo'
    assert not re.match(RE_VAR_DEF, d)
    # no identifier
    d = '==x'
    assert not re.match(RE_VAR_DEF, d)


def test_re_section_header():
    sli = ['[foo]', ' [foo] ']
    for s in sli:
        assert re.match(RE_SECTION_HEADER, s)
    s = '[ foo]'
    assert not re.match(RE_SECTION_HEADER, s)
    s = '[some/invalid/chars]'
    assert not re.match(RE_SECTION_HEADER, s)
    s = '[nice_chars_only]'
    assert re.match(RE_SECTION_HEADER, s)
    s = '[nice-chars-only]'
    assert re.match(RE_SECTION_HEADER, s)


def test_config():
    """Test reading of valid config"""
    fn = _file_path('valid.cfg')
    cfg_ = parse_config(fn)
    assert 'section1' in cfg_
    assert 'section2' in cfg_
    secs = sorted(secname for (secname, sec) in cfg_)
    assert secs == ['section1', 'section2']
    assert cfg_.section1.var1 == 1
    assert 'list' in cfg_.section1.var2
    assert cfg_.section1['var1']._comment == '# this is var1'


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


def _test_def_last_line():
    """Test cfg with multiline def terminating on last line"""
    fn = _file_path('def_last_line.cfg')
    cfg = parse_config(fn)
    assert 'foo' in cfg.section2


def test_dump_config():
    fn = _file_path('valid.cfg')
    cfg_ = parse_config(fn)
    txt = dump_config(cfg_)
    assert txt


run_tests_if_main()
