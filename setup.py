# -*- coding: utf-8 -*-
"""
@author: Jussi (jnu@iki.fi)
"""

from setuptools import setup, find_packages

# entry points for console scripts
console_entries = [
    'gaitmenu=gaitutils.gui._gaitmenu:main',
    'tardieu=gaitutils.gui._tardieu:main',
    'nexus_autoproc_session=gaitutils.autoprocess:autoproc_session',
    'nexus_autoproc_trial=gaitutils.autoprocess:autoproc_trial',
    'nexus_automark_trial=gaitutils.autoprocess:automark_trial',
    'gaitmenu_make_shortcut=gaitutils.envutils:_make_gaitutils_shortcut',
]

setup(
    name='gaitutils',
    version='0.13.8',
    description='Utilities for processing and plotting gait data',
    author='Jussi Nurminen',
    author_email='jnu@iki.fi',
    license='GPLv3',
    url='https://github.com/NCH-Motion-Laboratory/gaitutils',
    packages=find_packages(),
    entry_points={'console_scripts': console_entries},
    include_package_data=True,
)
