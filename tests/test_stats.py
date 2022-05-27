# -*- coding: utf-8 -*-
"""

Tests for trial stats

@author: jussi (jnu@iki.fi)
"""

import numpy as np
import logging

from gaitutils import sessionutils, stats, models
from utils import _file_path, cfg


logger = logging.getLogger(__name__)


sessiondir_ = 'test_subjects/D0063_RR/2018_12_17_preOp_RR'
sessiondir_abs = _file_path(sessiondir_)


def test_collect_trial_data():
    """Test collection of trial data"""
    c3ds = sessionutils.get_c3ds(sessiondir_abs, trial_type='dynamic')
    data_all, cycles_all = stats.collect_trial_data(c3ds)
    data_model = data_all['model']
    collected_vars = set(data_model.keys())
    # test whether data was collected for all vars
    # except CGM2 forefoot (which are not in the c3d data)
    desired_vars = set.union(
        set(models.pig_lowerbody.varnames),
        set(models.pig_lowerbody_kinetics.varnames),
        set(models.musclelen.varnames),
    ) - set([var for var in models.pig_lowerbody.varnames if 'ForeFoot' in var])
    assert collected_vars == desired_vars
    # check that the correct number of cycles was collected
    assert len(cycles_all['model']['LHipMomentX']) == 17
    assert data_model['LHipMomentX'].shape[0] == 17
    assert data_model['RAnkleMomentX'].shape[0] == 19
    assert len(cycles_all['model']['RKneeAnglesX']) == 46
    assert data_model['RKneeAnglesX'].shape[0] == 46
    assert data_model['fubar'] is None
    # forceplate cycles only
    data_all, cycles_all = stats.collect_trial_data(c3ds, fp_cycles_only=True)
    data_model = data_all['model']
    assert data_model['RKneeAnglesX'].shape[0] == 19
    assert data_model['RAnkleMomentX'].shape[0] == 19
    assert data_model['RKneeAnglesX'].shape[1] == 101
    assert len(cycles_all['model']['RKneeAnglesX']) == 19
    # EMG data collection
    data_all, cycles_all = stats.collect_trial_data(
        c3ds, collect_types=['emg'], analog_len=501
    )
    assert 'model' not in data_all
    data_emg = data_all['emg']
    emg_chs = ['LGas', 'LGlut', 'LHam', 'LPer', 'LRec', 'LSol', 'LTibA',
               'LVas', 'RGas', 'RGlut', 'RHam', 'RPer', 'RRec', 'RSol',
               'RTibA', 'RVas']
    assert set(data_emg.keys()) == set(emg_chs)
    assert all(data.shape[0] == 46 for ch, data in data_emg.items() if ch[0] == 'R')
    assert all(data.shape[0] == 42 for ch, data in data_emg.items() if ch[0] == 'L')
    assert all(data.shape[1] == 501 for data in data_emg.values())


def test_average_model_data():
    """Test averaging of model data"""
    c3ds = sessionutils.get_c3ds(sessiondir_abs, trial_type='dynamic')
    data_all, cycles_all = stats.collect_trial_data(c3ds, collect_types=['model'])
    data_model = data_all['model']
    avgdata, stddata, ncycles_ok = stats.average_model_data(
        data_model, reject_outliers=None
    )
    # test whether data was averaged for all vars
    # except CGM2 forefoot (which are not in the c3d data)
    desired_vars = set.union(
        set(models.pig_lowerbody.varnames),
        set(models.pig_lowerbody_kinetics.varnames),
        set(models.musclelen.varnames),
    ) - set([var for var in models.pig_lowerbody.varnames if 'ForeFoot' in var])
    for var in desired_vars:
        assert avgdata[var] is not None and avgdata[var].shape == (101,)
        assert stddata[var] is not None and stddata[var].shape == (101,)
    # test with median stats
    avgdata, stddata, ncycles_ok = stats.average_model_data(
        data_model, reject_outliers=None, use_medians=True
    )
    for var in desired_vars:
        assert avgdata[var] is not None and avgdata[var].shape == (101,)
        assert stddata[var] is not None and stddata[var].shape == (101,)
    # test outlier rejection
    avgdata, stddata, ncycles_ok_reject = stats.average_model_data(
        data_model, reject_outliers=1e-3
    )
    for var in desired_vars:
        assert avgdata[var] is not None and avgdata[var].shape == (101,)
        assert stddata[var] is not None and stddata[var].shape == (101,)
    assert any(ncycles_ok_reject[var] < ncycles_ok[var] for var in ncycles_ok)


def test_avgtrial():
    """Test the AvgTrial class"""
    # create from trials
    c3ds = sessionutils.get_c3ds(sessiondir_abs, trial_type='dynamic')
    atrial = stats.AvgTrial.from_trials(
        c3ds,
        sessionpath=sessiondir_abs,
        reject_outliers=1e-3,
    )
    assert atrial.sessionpath == sessiondir_abs
    assert atrial.trialname
    assert atrial.t.shape == (101,)
    assert len(atrial.cycles) == atrial.ncycles == 2
    assert atrial.cycles[0].trial == atrial
    adata, t = atrial.get_model_data('RKneeAnglesX')
    assert adata.shape == (101,)
    cycs = atrial.get_cycles('all')
    assert len(cycs) == 2
    cycs = atrial.get_cycles('forceplate')
    assert len(cycs) == 2
    # create from already averaged data
    data_all, cycles_all = stats.collect_trial_data(c3ds)
    data_model = data_all['model']
    avgdata_model, stddata_model, ncycles_ok = stats.average_model_data(
        data_model, reject_outliers=None
    )
    data_emg = data_all['emg']
    avgdata_emg, stddata_emg, ncycles_ok = stats.average_analog_data(
        data_emg, reject_outliers=None
    )
    atrial = stats.AvgTrial(
        avgdata_model=avgdata_model,
        stddata_model=stddata_model,
        avgdata_emg=avgdata_emg,
        stddata_emg=stddata_emg,
        sessionpath=sessiondir_abs,
        nfiles=len(c3ds),
    )
    assert atrial.sessionpath == sessiondir_abs
    assert atrial.trialname
    assert atrial.t.shape == (101,)
    assert len(atrial.cycles) == atrial.ncycles == 2
    assert atrial.cycles[0].trial == atrial
    adata, t = atrial.get_model_data('RKneeAnglesX')
    assert adata.shape == (101,)
    cycs = atrial.get_cycles('all')
    assert len(cycs) == 2
    cycs = atrial.get_cycles('forceplate')
    assert len(cycs) == 2


def test_curve_extract_values():
    """Test extraction of curve values"""
    # make a fake gait curve
    npts = 100  # usually 101, but this will give us nice round values to test
    t = np.arange(npts)
    curve = np.sin(2 * np.pi * 5 * t / npts - np.pi / 2) + t / npts
    toeoff = 60
    res = stats.curve_extract_values(np.array([curve]), np.array([toeoff]))
    # this comparison may be fragile due to floating point inaccuracy
    # it would be wiser to dive into the dicts and use assert_allclose
    assert res == {
        'contact': [-1.0],
        'toeoff': [-0.4],
        'extrema': {
            'overall': {'min': [-1.0], 'argmin': [0], 'max': [1.9], 'argmax': [90]},
            'stance': {'min': [-1.0], 'argmin': [0], 'max': [1.5], 'argmax': [50]},
            'swing': {'min': [-0.4], 'argmin': [60], 'max': [1.9], 'argmax': [90]},
        },
        'peaks': {
            'overall': {'argmin': [20], 'min': [-0.8], 'argmax': [90], 'max': [1.9]},
            'stance': {'argmin': [20], 'min': [-0.8], 'argmax': [50], 'max': [1.5]},
            'swing': {
                'argmin': [80],
                'min': [-0.19999999999999996],
                'argmax': [90],
                'max': [1.9],
            },
        },
    }


def test_trials_extract_values():
    """Test curve value extraction from trials"""
    c3ds = sessionutils.get_c3ds(sessiondir_abs, trial_type='dynamic')
    extr_vals = stats._trials_extract_values(c3ds, from_models=[models.pig_lowerbody])
    # forefoot vars are not present in our test data
    forefoot = models._list_with_context(
        ['ForeFootAnglesX', 'ForeFootAnglesY', 'ForeFootAnglesZ']
    )
    assert set(extr_vals.keys()) == (set(models.pig_lowerbody.varnames) - set(forefoot))
