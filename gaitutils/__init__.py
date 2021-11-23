import logging
import os
import sys


from . import (
    c3d,
    config,
    eclipse,
    emg,
    envutils,
    gui,
    models,
    nexus,
    normaldata,
    numutils,
    read_data,
    report,
    sessionutils,
    stats,
    timedist,
    trial,
    utils,
    videos,
    viz,
)


# in case we want to print stuff from config.py, it's better to delay
# the import until this point (after the stdout fix above)
from .config import cfg
from .envutils import GaitDataError


# the main purpose of adding the null handler is to disable the
# default stderr logging for levels >= warning, which may be
# annoying in some cases
root_logger = logging.getLogger('gaitutils')
root_logger.addHandler(logging.NullHandler())
# add a file handler for debugging startup problems
# filehandler = logging.FileHandler(r'C:\Temp\gaitutils.log')
# root_logger.addHandler(filehandler)
# root_logger.setLevel(logging.DEBUG)
# root_logger.debug('package init')


def run_from_ipython():
    try:
        __IPYTHON__
        return True
    except NameError:
        return False


# fake stdout and stderr if run under pythonw.exe on Windows;
# this prevents errors on print() calls
# also if no stdout output is desired, the same lines accomplish that
if cfg.general.quiet_stdout or (
    sys.platform.find('win') != -1
    and sys.executable.find('pythonw') != -1
    and not run_from_ipython()
):
    blackhole = open(os.devnull, 'w')
    sys.stdout = sys.stderr = blackhole
