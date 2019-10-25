# -*- coding: utf-8 -*-
"""

Tests for trial stats

@author: jussi (jnu@iki.fi)
"""

import numpy as np
from numpy.testing import assert_allclose, assert_equal
import pytest
import logging

from gaitutils import sessionutils, stats, models
from utils import _trial_path, _c3d_path, _file_path, cfg


logger = logging.getLogger(__name__)


sessiondir_ = 'test_subjects/D0063_RR/2018_12_17_preOp_RR'
sessiondir_abs = _file_path(sessiondir_)


def test_collect_model_data():
    """Test collection of model data"""
    c3ds = sessionutils.get_c3ds(sessiondir_abs, trial_type='dynamic')
    data_all, nc = stats.collect_model_data(c3ds)
    collected_vars = set(data_all.keys())
    # test whether data was collected for all vars
    # except CGM2 forefoot (which are not in the c3d data)
    desired_vars = set(
        models.pig_lowerbody.varnames
        + models.pig_lowerbody_kinetics.varnames
        + models.musclelen.varnames
    ) - set([var for var in models.pig_lowerbody.varnames if 'ForeFoot' in var])
    assert collected_vars == desired_vars
    # check that correct number of cycles was collected
    assert nc == {'R_fp': 19, 'R': 54, 'L': 53, 'L_fp': 17}
    assert data_all['RKneeAnglesX'].shape[0] == nc['R']
    assert data_all['RAnkleMomentX'].shape[0] == nc['R_fp']
    assert data_all['RKneeAnglesX'].shape[1] == 101
    assert data_all['fubar'] is None
    # forceplate cycles only
    data_all, nc = stats.collect_model_data(c3ds, fp_cycles_only=True)
    assert nc == {'R_fp': 19, 'R': 19, 'L': 17, 'L_fp': 17}
    assert data_all['RKneeAnglesX'].shape[0] == nc['R']
    assert data_all['RAnkleMomentX'].shape[0] == nc['R_fp']
    assert data_all['RKneeAnglesX'].shape[1] == 101


def test_average_model_data():
    """Test averaging of model data"""
    c3ds = sessionutils.get_c3ds(sessiondir_abs, trial_type='dynamic')
    avgdata, stddata, ncycles_ok, ncycles = stats.average_trials(
        c3ds, reject_outliers=None
    )
    # test whether data was averaged for all vars
    # except CGM2 forefoot (which are not in the c3d data)
    desired_vars = set(
        models.pig_lowerbody.varnames
        + models.pig_lowerbody_kinetics.varnames
        + models.musclelen.varnames
    ) - set([var for var in models.pig_lowerbody.varnames if 'ForeFoot' in var])
    for var in desired_vars:
        assert avgdata[var] is not None and avgdata[var].shape == (101,)
        assert stddata[var] is not None and stddata[var].shape == (101,)
    # test with median stats
    avgdata, stddata, ncycles_ok, ncycles = stats.average_trials(c3ds, use_medians=True)
    for var in desired_vars:
        assert avgdata[var] is not None and avgdata[var].shape == (101,)
        assert stddata[var] is not None and stddata[var].shape == (101,)
    # test outlier rejection; currently test is a bit lame
    avgdata_, stddata_, ncycles_ok_, ncycles_ = stats.average_trials(
        c3ds, reject_outliers=1e-3
    )
    assert not all(ncycles_ok[var] == ncycles_ok_[var] for var in ncycles_ok)
    avgdata_, stddata_, ncycles_ok_, ncycles_ = stats.average_trials(
        c3ds, reject_outliers=1e-30
    )
    assert all(ncycles_ok[var] == ncycles_ok_[var] for var in ncycles_ok)


def test_avgtrial():
    """Test the AvgTrial class"""
    c3ds = sessionutils.get_c3ds(sessiondir_abs, trial_type='dynamic')
    atrial = stats.AvgTrial(c3ds, sessionpath=sessiondir_abs, reject_outliers=1e-3)
    assert atrial.sessionpath == sessiondir_abs
    assert atrial.trialname
    assert atrial.t.shape == (101,)
    assert len(atrial.cycles) == atrial.ncycles == 2
    assert atrial.cycles[0].trial == atrial
    with pytest.raises(ValueError):
        atrial.set_norm_cycle(None)
    adata, t = atrial.get_model_data('RKneeAnglesX')
    assert adata.shape == (101,)
    cycs = atrial.get_cycles('all')
    assert len(cycs) == 2
    cycs = atrial.get_cycles('forceplate')
    assert len(cycs) == 2
