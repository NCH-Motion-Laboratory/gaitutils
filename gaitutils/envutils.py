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
from ulstools import env
from pkg_resources import resource_filename
import logging
import hashlib

from .gui._windows import error_exit

# import backported lru_cache for 2.7
if sys.version_info.major == 2:
    from functools32 import lru_cache
else:
    from functools import lru_cache

logger = logging.getLogger(__name__)


class GaitDataError(Exception):
    pass


def _ipython_setup():
    """Performs some IPython magic if we are running in IPython"""
    try:
        __IPYTHON__
    except NameError:
        return
    from IPython import get_ipython

    ip = get_ipython()
    #ip.magic("gui qt5")  # needed for mayavi plots
    #ip.magic("matplotlib qt")  # do mpl plots in separate windows
    ip.magic("reload_ext autoreload")  # these will enable module autoreloading
    ip.magic("autoreload 2")
    # print('warning: setting precision=3 for numpy array printing')
    # np.set_printoptions(precision=3)


def make_gaitutils_shortcut():
    """Makes a desktop shortcut to gaitmenu gui."""
    env.make_shortcut('gaitutils', 'gui/gaitmenu.py', 'gaitutils menu')


def _git_autoupdate():
    """Hacky way to update repo to latest master, if running under git.
    Return True if update was ran, else False"""
    mod_dir = resource_filename('gaitutils', '')
    repo_dir = op.abspath(op.join(mod_dir, op.pardir))
    if op.isdir(op.join(repo_dir, '.git')):
        logger.debug('running git autoupdate')
        o = subprocess.check_output(['git', 'pull'], cwd=repo_dir)
        updated = 'pdating' in o  # XXX: fragile as hell
        if updated:
            logger.debug('autoupdate status: %s' % o)
            return True
        else:
            logger.debug('package already up to date')
            return False
    else:  # not a git repo
        logger.debug('%s is a git repo, not running autoupdate' % repo_dir)
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


def lru_cache_checkfile(fun):
    """Caches function results, unless the argument file has changed.

    A lru_cache type decorator for functions that take a file name argument.
    Makes sense for functions that read a file and take a long time to process
    the data (anything that takes significantly longer than the md5 digest).
    Works by computing the md5 digest for the input file and passing that on to
    lru_cache, so the cache is invalidated if file contents have changed.
    """

    @lru_cache()
    def cached_fun(filename, md5sum):
        return fun(filename)

    def wrapper(filename):
        with open(filename, 'rb') as f:
            data = f.read()
        md5sum = hashlib.md5(data).hexdigest()
        return cached_fun(filename, md5sum)

    return wrapper
