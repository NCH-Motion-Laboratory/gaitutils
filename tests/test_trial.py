# -*- coding: utf-8 -*-
"""

Test trial related functionality

@author: jussi (jnu@iki.fi)
"""

import numpy as np
from numpy.testing import assert_allclose, assert_equal
import logging

from gaitutils import models
from gaitutils.trial import Trial
from gaitutils.utils import _pig_markerset
from utils import _trial_path


logger = logging.getLogger(__name__)


def test_trial_metadata():
    """Test metadata reading from c3d"""
    # 1-forceplate system
    c3dfile = _trial_path('girl6v', '2015_10_22_girl6v_IN02.c3d')
    tr = Trial(c3dfile)
    # default tolerance of assert_allclose is 1e-7
    # could also use pytest.approx()
    assert_allclose(tr.analograte, 1000.0)
    assert_equal(tr.framerate, 100.0)
    assert_allclose(tr.subj_params['Bodymass'], 24.0)
    assert_equal(tr.name, 'Iiris')
    assert_equal(tr.trialname, c3dfile.stem)
    assert_equal(tr.sessionpath, c3dfile.parent)
    assert_equal(tr.n_forceplates, 1)
    assert_equal(tr.length, 794)
    assert_equal(tr.samplesperframe, 10.0)
    # 3-fp system
    c3dfile = _trial_path('adult_3fp', 'astrid_080515_02.c3d')
    tr = Trial(c3dfile)
    assert_equal(tr.analograte, 1000.0)
    assert_equal(tr.framerate, 200.0)
    assert_allclose(tr.subj_params['Bodymass'], 65.59999, rtol=1e-4)
    assert_equal(tr.name, 'Astrid')
    assert_equal(tr.n_forceplates, 3)
    assert_equal(tr.length, 639)
    assert_equal(tr.samplesperframe, 5)
    # 5-fp system
    c3dfile = _trial_path('runner', 'JL brooks 2,8 51.c3d')
    tr = Trial(c3dfile)
    assert_equal(tr.analograte, 1500.0)
    assert_equal(tr.framerate, 300.0)
    assert_allclose(tr.subj_params['Bodymass'], 74.0, rtol=1e-4)
    assert_equal(tr.name, 'JL')
    assert_equal(tr.n_forceplates, 5)
    assert_equal(tr.length, 391)
    assert_equal(tr.samplesperframe, 5)


def test_get_cycles():
    """Test cycle getter"""
    c3dfile = _trial_path('girl6v', '2015_10_22_girl6v_IN02.c3d')
    tr = Trial(c3dfile)
    cycs = tr.get_cycles('forceplate')
    assert len(cycs) == 1
    assert cycs[0].on_forceplate
    cycs = tr.get_cycles('all')
    assert len(cycs) == 4
    cycs = tr.get_cycles('all', max_cycles_per_context=1)
    assert len(cycs) == 2


def test_trial_data_read():
    """Test data read from normalized/unnormalized cycles"""
    c3dfile = _trial_path('girl6v', '2015_10_22_girl6v_IN02.c3d')
    tr = Trial(c3dfile)
    # read marker data
    pig = _pig_markerset(fullbody=True, sacr=True)
    for var in pig:
        t, data = tr.get_marker_data(var)  # unnormalized
        assert t.shape == (794,)
        assert data.shape == (794, 3)
        t, data = tr.get_marker_data(var, 0)  # 1st cycle
        assert t.shape == (101,)
        assert data.shape == (101, 3)
        # some known values for this cycle
        if var == 'SACR':
            data_truth = np.array(
                [
                    [225.61265564, -1224.5526123, 693.34594727],
                    [223.94009735, -1216.89548584, 692.26601624],
                    [222.29524506, -1209.13790283, 691.30033325],
                ]
            )
            assert_allclose(data[:3, :], data_truth)
    # read model data
    for var in list(models.pig_lowerbody.varnames) + list(
        models.pig_upperbody.varnames
    ):
        t, data = tr.get_model_data(var)  # unnormalized
        assert t.shape == (794,)
        assert data.shape == (794,)
        t, data = tr.get_model_data(var, 0)
        assert t.shape == (101,)
        assert data.shape == (101,)
        # some known values for this cycle
        if var == 'RHipAnglesX':
            data_truth = np.array(
                [
                    5.12708759,
                    4.58470859,
                    4.0733108,
                    3.60522768,
                    3.1999483,
                    2.87095979,
                    2.62458159,
                    2.47358855,
                    2.44552759,
                    2.53485509,
                    2.75183632,
                    3.12467247,
                    3.65770569,
                    4.35132931,
                    5.21909947,
                ]
            )
            assert_allclose(data[:15], data_truth)
    # read EMG data
