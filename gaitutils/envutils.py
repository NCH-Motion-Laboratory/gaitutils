# -*- coding: utf-8 -*-
"""
Created on Tue Mar 17 14:41:31 2015

Stuff related to Python environment

@author: Jussi (jnu@iki.fi)
"""

import sys
import traceback

from .guiutils import error_exit


class GaitDataError(Exception):
    """ Exception specific to erroneous or unexpected gait data """
    def __init__(self, arg):
        super(self.__class__, self).__init__(self, arg)
        self.gaiterror = arg


def register_gui_exception_handler(full_traceback=False):
    """ Registers an exception handler that reports uncaught exceptions
    via GUI"""
    from .config import cfg

    def _my_excepthook(type_, value, tback):
        """ Custom exception handler for fatal (unhandled) exceptions:
        report to user via GUI and terminate. """
        # exception and message, but no traceback
        tbackstr = tback if full_traceback else ''
        msg = ''.join(traceback.format_exception(type_, value, tbackstr))
        error_exit(msg)
        # just the message (e.g. ValueError: "blah" -> "blah")
        # may sometimes be confusing, since type of exception is not printed
        # error_exit(value)
        #
        sys.__excepthook__(type_, value, tback)
        sys.exit()

    if cfg.general.gui_exceptions:
        sys.excepthook = _my_excepthook


def run_from_ipython():
    try:
        __IPYTHON__
        return True
    except NameError:
        return False
