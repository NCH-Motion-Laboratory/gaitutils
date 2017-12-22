# -*- coding: utf-8 -*-
"""
__init__.py

@author: Jussi (jnu@iki.fi)
"""

from .config import cfg
from . import models
from . import nexus
from . import eclipse
from . import read_data
from . import trial
from . import guiutils
from . import utils
from . import stats
from .emg import EMG
from .envutils import register_gui_exception_handler, GaitDataError
from .numutils import rising_zerocross, falling_zerocross
from .guiutils import messagebox
from .plot import Plotter
from .trial import Trial

from nexus_scripts import nexus_emgplot
from nexus_scripts import nexus_kinetics_emgplot
from nexus_scripts import nexus_emg_consistency
from nexus_scripts import nexus_kin_consistency
from nexus_scripts import nexus_autoprocess_trial
from nexus_scripts import nexus_autoprocess_session
from nexus_scripts import nexus_kinallplot
from nexus_scripts import nexus_tardieu
from nexus_scripts import nexus_copy_trial_videos
from nexus_scripts import nexus_trials_velocity
from nexus_scripts import nexus_make_all_plots
from nexus_scripts import nexus_kin_average
from nexus_scripts import nexus_automark_trial
from nexus_scripts import nexus_time_distance_vars

