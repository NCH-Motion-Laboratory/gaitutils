# -*- coding: utf-8 -*-
"""

Utils for unit tests.

@author: jussi (jnu@iki.fi)
"""

import os.path as op
import os
import subprocess
import time

from gaitutils import nexus, config, cfg


# reset the config so that user settings do not affect testing
# works by mutating the singleton cfg object
# note that the reset occurs whenever this file is imported, so be
# careful about importing it
cfg_default = config.parse_config(config.cfg_template_fn)
config.update_config(cfg, cfg_default)
config._handle_cfg_defaults(cfg)

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
            raise Exception('Failed to start Nexus, please start it manually')
    return nexus.viconnexus()


def _file_path(filename):
    """Path for files/dirs directly under testdata dir"""
    return op.abspath(op.join(testdata_root, filename))


def _trial_path(subject, trial, session=None):
    """Return path to subject trial file (in session dir)"""
    # default name for test data session
    if session is None:
        session = 'test_session'
    return op.abspath(op.join(testdata_root, 'test_subjects', subject, session, trial))


def _c3d_path(filename):
    """Return path to c3d test file"""
    return op.abspath(op.join(testdata_root, 'test_c3ds', filename))
