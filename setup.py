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
      include_package_data=True,
      )
