# -*- coding: utf-8 -*-
"""
Created on Tue Mar 17 14:41:31 2015

Stuff related to Python environment

@author: Jussi (jnu@iki.fi)
"""


from guiutils import error_exit
import sys


def register_gui_exception_handler():
    """ Registers an exception handler that reports uncaught exceptions
    via GUI"""

    def _my_excepthook(type, value, tback):
        """ Custom exception handler for fatal (unhandled) exceptions:
        report to user via GUI and terminate. """
        # full traceback
        # tb_full = ''.join(traceback.format_exception(type, value, tback))
        # just the message (e.g. ValueError: "blah" -> "blah")
        error_exit(value)
        sys.__excepthook__(type, value, tback)
        sys.exit()

    sys.excepthook = _my_excepthook


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
