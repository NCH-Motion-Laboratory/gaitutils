# -*- coding: utf-8 -*-
"""
Created on Tue Mar 17 14:41:31 2015

Stuff related to Python environment

@author: Jussi (jnu@iki.fi)
"""

import sys
import traceback
import subprocess
from ulstools import env
from pkg_resources import resource_filename
import logging
import hashlib
import os
import tempfile
from pathlib import Path
from functools import lru_cache

from .gui._windows import error_exit


logger = logging.getLogger(__name__)


pkg_dir = Path(resource_filename('gaitutils', ''))  # package directory
pkg_parent = pkg_dir.parent
# True if package was imported from a git repository
git_mode = (pkg_parent / '.git').is_dir()


class GaitDataError(Exception):
    """Custom exception class to indicate gait data related errors"""


def _ipython_setup():
    """Performs some IPython magic if we are running in IPython"""
    try:
        __IPYTHON__
    except NameError:
        return
    from IPython import get_ipython

    ip = get_ipython()
    # ip.magic("gui qt5")  # needed for mayavi plots
    # ip.magic("matplotlib qt")  # do mpl plots in separate windows
    ip.magic("reload_ext autoreload")  # these will enable module autoreloading
    ip.magic("autoreload 2")
    # print('warning: setting precision=3 for numpy array printing')
    # np.set_printoptions(precision=3)


def _make_gaitutils_shortcut():
    """Makes a desktop shortcut to gaitmenu gui."""
    env.make_shortcut('gaitutils', 'gui/gaitmenu.py', 'gaitutils menu')


def _git_update():
    """Update the package git repository.

    This works, if the package was installed into user directory by cloning the
    git repository and running 'python setup.py develop'. In this case, updating
    the cloned repository will effectively update the package.

    The normal way to install the package is via pip install. In this case, the
    package must be updated manually by pip.

    Since this update mechanism is a bit fragile, it is not used by default.

    Return True if update was ran, else False.
    """

    if git_mode:
        logger.info('running git update')
        try:
            startupinfo = None
            if os.name == 'nt':
                # hides the console on Windows
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            o = subprocess.check_output(
                ['git', 'pull'],
                cwd=pkg_parent,
                encoding='utf-8',
                startupinfo=startupinfo,
            )
        except subprocess.CalledProcessError:
            status = (False, 'cannot retrieve or merge update')
        if 'lready' in o:
            status = (False, 'package already up to date')
        else:
            status = (True, o)
    else:  # not a git repo
        status = (False, 'cannot update, gaitutils is not installed in git mode')
    return status


def _register_gui_exception_handler(full_traceback=False):
    """Registers an exception handler that reports exceptions via GUI"""
    from .config import cfg

    def _my_excepthook(type_, value, tback):
        """Custom exception handler for fatal (unhandled) exceptions:
        report to user via GUI and terminate."""
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
    """Cache function results, unless the argument file has changed.

    A lru_cache -style decorator for functions that take a file name argument.
    Makes sense for functions that read a file and take a long time to process
    the data (anything that takes significantly longer than the md5 digest).
    Works by computing the md5 digest for the input file and passing that on to
    lru_cache, so the cache is invalidated if file contents have changed.

    Parameters
    ----------
    fun : function
        The function to cache.

    Returns
    -------
    function
        The cached function.
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


def _named_tempfile(suffix=None):
    """Return a name for a temporary file.
    Does not open the file. Cross-platform. Intended to replace
    tempfile.NamedTemporaryFile which behaves strangely on Windows.
    """
    LEN = 12  # length of basename
    if suffix is None:
        suffix = ''
    elif suffix[0] != '.':
        raise ValueError('Invalid suffix, must start with dot')
    basename = os.urandom(LEN)  # get random bytes
    # convert to hex string
    basename = basename.hex()
    return tempfile.gettempdir() / Path(basename).with_suffix(suffix)
