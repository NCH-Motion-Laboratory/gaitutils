# -*- coding: utf-8 -*-
"""

Unit test for plotting.

@author: jussi (jnu@iki.fi)
"""


from nose.tools import (assert_set_equal, assert_in, assert_equal,
                        assert_raises, assert_less_equal)
from numpy.testing import (assert_allclose, assert_array_equal,
                           assert_array_almost_equal)
import os.path as op
import time

import gaitutils
from gaitutils import nexus, utils, models
from gaitutils.config import cfg
from gaitutils import Trial
from utils import (_trial_path, _nexus_open_trial, run_tests_if_main,
                   start_nexus)


cfg.load_default()  # so that user settings will not affect testing

start_nexus()

vicon = nexus.viconnexus()


def test_nexus_plot():
    """Test basic plot from Nexus"""
    trialname = '2015_10_22_girl6v_IN03'
    _nexus_open_trial('girl6v', trialname)
    pl = gaitutils.Plotter(interactive=False)
    pl.open_nexus_trial()
    pl.layout = [['HipMomentX']]
    pl.plot_trial()


run_tests_if_main()
