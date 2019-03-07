# -*- coding: utf-8 -*-
"""
@author: Jussi (jnu@iki.fi)
"""

from setuptools import setup, find_packages

# entry points for console scripts
c_entries = ['gaitmenu=gaitutils.gui._gaitmenu:main',
             'tardieu=gaitutils.gui._tardieu:main',
             'plotter_gui=gaitutils.gui._plotter_gui:main',
             'nexus_autoproc_session=gaitutils.autoprocess:autoproc_session',
             'nexus_autoproc_trial=gaitutils.autoprocess:autoproc_trial',
             'nexus_automark_trial=gaitutils.autoprocess:automark_trial',
             'nexus_plot_trial=gaitutils.viz.console:plot_nexus_trial',
             'nexus_plot_session=gaitutils.viz.console:plot_nexus_session']

# FIXME: add launch_menu
scripts = ['gaitutils/scripts/launch_menu.bat']

setup(name='gaitutils',
      version='0.11.32',
      description='Utilities for processing and plotting gait data',
      author='Jussi Nurminen',
      author_email='jnu@iki.fi',
      license='GPLv3',
      url='https://github.com/jjnurminen/gaitutils',
      packages=find_packages(),
      entry_points={'console_scripts': c_entries},
      scripts=scripts,
      include_package_data=True,
      )
