# -*- coding: utf-8 -*-
"""

Utils for unit tests.

@author: jussi (jnu@iki.fi)
"""

import inspect
import sys
import os.path as op
import os
import subprocess
import time
import logging
from ulstools.configdot import parse_config

from gaitutils import nexus, config


# reset the config so that user settings do not affect testing
cfg = parse_config(config.cfg_template_fn)
homedir = op.expanduser('~')
LOCAL_TESTDATA = op.join(homedir, 'gaitutils/tests/gaitutils_testdata')
if op.isdir(LOCAL_TESTDATA):
    testdata_root = LOCAL_TESTDATA  # local version for faster tests
else:
    testdata_root = r'Z:\gaitutils_testdata'  # authoritative version on network drive


def start_nexus():
    if not nexus._nexus_pid():
        # try to start Nexus for tests...
        exe = op.join(nexus._find_nexus_path(), 'Nexus.exe')
        # silence Nexus output
        blackhole = open(os.devnull, 'w')
        subprocess.Popen([exe], stdout=blackhole)
        time.sleep(9)
        if not nexus._nexus_pid():
            raise Exception('Please start Vicon Nexus first')


def _file_path(filename):
    """Path for files/dirs directly under testdata dir"""
    return op.abspath(op.join(testdata_root, filename))


def _trial_path(subject, trial):
    """Return path to subject trial file (in session dir)"""
    return op.abspath(
        op.join(testdata_root, 'test_subjects', subject, 'test_session', trial)
    )


def _c3d_path(filename):
    """Return path to c3d test file"""
    return op.abspath(op.join(testdata_root, 'test_c3ds', filename))


def _nexus_open_trial(subject, trial):
    """Open trial in Nexus"""
    vicon = nexus.viconnexus()
    tpath = op.splitext(_trial_path(subject, trial))[0]  # strip .c3d
    vicon.OpenTrial(tpath, 60)
