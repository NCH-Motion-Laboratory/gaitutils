# -*- coding: utf-8 -*-
"""
Created on Tue Mar 17 14:41:31 2015

Stuff related to Python environment

@author: Jussi (jnu@iki.fi)
"""


from __future__ import print_function


def run_from_ipython():
    try:
        __IPYTHON__
        return True
    except NameError:
        return False

""" Print debug messages only if running under IPython. Debug may prevent
scripts from working in Nexus (??) """
if run_from_ipython():
    DEBUG = True
else:
    DEBUG = False


def debug_print(*args):
    if DEBUG:
        print(*args)
