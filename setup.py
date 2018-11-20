# -*- coding: utf-8 -*-
"""
Created on Mon Nov 14 15:50:55 2016

@author: Jussi (jnu@iki.fi)
"""

from setuptools import setup, find_packages


setup(name='gaitutils',
      version='0.11.3',
      description='Utilities for processing and plotting gait data',
      author='Jussi Nurminen',
      author_email='jnu@iki.fi',
      license='GPLv3',
      url='https://github.com/jjnurminen/gaitutils',
      packages=find_packages(),
      scripts=['gaitutils/nexus_scripts/nexus_emgplot.py',
               'gaitutils/nexus_scripts/nexus_kinallplot.py',
               'gaitutils/nexus_scripts/nexus_kinetics_emgplot.py',
               'gaitutils/nexus_scripts/nexus_kinematics_emgplot.py',
               'gaitutils/nexus_scripts/nexus_musclelen_plot.py',
               'gaitutils/nexus_scripts/nexus_kin_consistency.py',
               'gaitutils/nexus_scripts/nexus_emg_consistency.py',
               'gaitutils/nexus_scripts/nexus_musclelen_consistency.py',
               'gaitutils/nexus_scripts/nexus_automark_trial.py',
               'gaitutils/nexus_scripts/nexus_autoprocess_session.py',
               'gaitutils/nexus_scripts/nexus_autoprocess_trial.py',
               'gaitutils/nexus_scripts/nexus_menu.py',
               'gaitutils/nexus_scripts/nexus_tardieu.py',
               'gaitutils/nexus_scripts/nexus_copy_trial_videos.py',
               'gaitutils/nexus_scripts/nexus_trials_velocity.py',
               'gaitutils/nexus_scripts/nexus_make_pdf_report.py',
               'gaitutils/nexus_scripts/nexus_make_comparison_report.py',
               'gaitutils/nexus_scripts/nexus_kin_average.py',
               'gaitutils/nexus_scripts/nexus_time_distance_vars.py',
               'gaitutils/nexus_scripts/plotter_gui.py'],
      include_package_data=True,
      )
