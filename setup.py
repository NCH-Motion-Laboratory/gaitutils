# -*- coding: utf-8 -*-
"""
@author: Jussi (jnu@iki.fi)
"""

from setuptools import setup, find_packages


setup(name='gaitutils',
      version='0.11.26',
      description='Utilities for processing and plotting gait data',
      author='Jussi Nurminen',
      author_email='jnu@iki.fi',
      license='GPLv3',
      url='https://github.com/jjnurminen/gaitutils',
      packages=find_packages(),
      scripts=['gaitutils/scripts/gaitmenu.py',
               'gaitutils/scripts/tardieu.py',
               'gaitutils/scripts/plotter_gui.py',
               'gaitutils/scripts/nexus_plot.py',
               'gaitutils/scripts/nexus_kin_consistency.py',
               'gaitutils/scripts/nexus_emg_consistency.py',
               'gaitutils/scripts/nexus_musclelen_consistency.py',
               'gaitutils/scripts/nexus_automark_trial.py',
               'gaitutils/scripts/nexus_autoprocess_session.py',
               'gaitutils/scripts/nexus_autoprocess_trial.py',
               'gaitutils/scripts/nexus_copy_trial_videos.py',
               'gaitutils/scripts/nexus_trials_velocity.py',
               'gaitutils/scripts/nexus_make_pdf_report.py',
               'gaitutils/scripts/nexus_make_comparison_report.py',
               'gaitutils/scripts/nexus_kin_average.py',
               'gaitutils/scripts/nexus_time_distance_vars.py'],
      include_package_data=True,
      )
