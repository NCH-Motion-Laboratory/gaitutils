# -*- coding: utf-8 -*-
"""

Normaldata unit tests

@author: jussi (jnu@iki.fi)
"""

import pytest
import numpy as np
from numpy.testing import assert_allclose
from shutil import copyfile
import logging

from gaitutils import normaldata, models
from utils import _file_path


logger = logging.getLogger(__name__)

fn_xlsx = _file_path('normaldata.xlsx')


def test_read_xlsx_normaldata():
    """Test read of default xlsx normaldata"""
    ndata = normaldata._read_xlsx(fn_xlsx)
    normaldata._check_normaldata(ndata)
    ndata_vars = ndata.keys()
    pigvars = models.pig_lowerbody.varlabels_noside.keys()
    # no normaldata for following vars
    not_in_normal = {'AnkleAnglesY', 'ForeFootAnglesX',
                     'ForeFootAnglesY', 'ForeFootAnglesZ'}
    assert set(pigvars) - set(ndata_vars) == not_in_normal


def test_write_normaldata():
    """Test read/write cycle for default normaldata"""
    outfn = 'test.xlsx'
    ndata = normaldata._read_xlsx(fn_xlsx)
    normaldata._write_xlsx(ndata, outfn)
    ndata2 = normaldata._read_xlsx(outfn)
    for var in ndata:
        assert_allclose(ndata[var], ndata2[var])
    normaldata._check_normaldata(ndata2)
    ndata_vars = ndata2.keys()
    pigvars = models.pig_lowerbody.varlabels_noside.keys()
    # no normaldata for following vars
    not_in_normal = {'AnkleAnglesY', 'ForeFootAnglesX',
                     'ForeFootAnglesY', 'ForeFootAnglesZ'}
    assert set(pigvars) - set(ndata_vars) == not_in_normal














