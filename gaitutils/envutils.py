# -*- coding: utf-8 -*-
"""
Created on Tue Mar 17 14:41:31 2015

Stuff related to Python environment

@author: Jussi (jnu@iki.fi)
"""

import sys
import traceback
import subprocess
import os.path as op
from pkg_resources import resource_filename

from .guiutils import error_exit


class GaitDataError(Exception):
    pass


def _git_autoupdate():
    """Hacky way to update repo to latest master, if running under git.
    Return True if update was ran, else False"""
    mod_dir = resource_filename('gaitutils', '')
    repo_dir = op.abspath(op.join(mod_dir, op.pardir))
    if op.isdir(op.join(repo_dir, '.git')):
        print('running git autoupdate')
        o = subprocess.check_output(['git', 'pull'], cwd=repo_dir)
        updated = 'Updating' in o  # XXX: fragile as hell
        if updated:
            print('Autoupdate status: %s' % o)
            return True
        else:
            print('Package already up to date')
            return False
    else:  # not a git repo
        print('%s not look like a git repo, not running autoupdate' % repo_dir)
        return False


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
