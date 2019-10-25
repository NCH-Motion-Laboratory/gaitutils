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

from gaitutils import eclipse
from utils import _file_path, cfg


logger = logging.getLogger(__name__)

trial_enf = _file_path('anon.Trial.enf')
trial_enf_write = _file_path('writetest.enf')


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
