# -*- coding: utf-8 -*-
"""
Created on Mon Nov 14 15:50:55 2016

@author: jussi
"""

from setuptools import setup, find_packages


setup(name='gaitutils',
      version='0.10',
      description='Utilities for processing and plotting gait data',
      author='Jussi Nurminen',
      author_email='jnu@iki.fi',
      license='MIT',
      url='https://github.com/jjnurminen/gaitutils',
      packages=find_packages(),
      scripts=['nexus_scripts/nexus_emgplot.py',
               'nexus_scripts/nexus_kinallplot.py',
               'nexus_scripts/nexus_kinetics_emgplot.py',
               'nexus_scripts/nexus_kinematics_emgplot.py',
               'nexus_scripts/nexus_kin_consistency.py',
               'nexus_scripts/nexus_emg_consistency.py',
               'nexus_scripts/nexus_autoplot.py',
               'nexus_scripts/nexus_automark_trial.py',
               'nexus_scripts/nexus_autoprocess_current.py',
               'nexus_scripts/nexus_autoprocess_trials.py',
               'nexus_scripts/nexus_menu.py',
               'nexus_scripts/nexus_tardieu.py'],
      include_package_data=True,
      )
