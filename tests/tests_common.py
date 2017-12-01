# -*- coding: utf-8 -*-
"""

plotting unit tests
automatically run by 'nose2'

@author: jussi (jnu@iki.fi)
"""

import inspect
import sys
import warnings
import numpy as np
from nose.tools import (assert_set_equal, assert_in, assert_equal,
                        assert_raises, assert_less_equal)
from numpy.testing import (assert_allclose, assert_array_equal,
                           assert_array_almost_equal)
import os.path as op
import os
import subprocess
import time

import gaitutils
from gaitutils import nexus, utils, models
from gaitutils.config import cfg
from gaitutils import Trial
from gaitutils.utils import detect_forceplate_events


def _trial_path(subject, trial):
    """Return path to subject trial file"""
    return op.abspath(op.join('testdata', 'test_subjects', subject,
                              'test_session', trial))


def _nexus_open_trial(subject, trial):
    """Open trial in Nexus"""
    vicon = nexus.viconnexus()
    tpath = op.splitext(_trial_path(subject, trial))[0]  # strip .c3d
    vicon.OpenTrial(tpath, 60)


def nottest(f):
    """Decorator to mark a function as not a test"""
    f.__test__ = False
    return f


def _memory_usage(*args, **kwargs):
    if isinstance(args[0], tuple):
        args[0][0](*args[0][1], **args[0][2])
    elif not isinstance(args[0], int):  # can be -1 for current use
        args[0]()
    return [-1]


try:
    from memory_profiler import memory_usage
except ImportError:
    memory_usage = _memory_usage


@nottest
def run_tests_if_main(measure_mem=False):
    """Run tests in a given file if it is run as a script"""
    local_vars = inspect.currentframe().f_back.f_locals
    if not local_vars.get('__name__', '') == '__main__':
        return
    # we are in a "__main__"
    try:
        import faulthandler
        faulthandler.enable()
    except Exception:
        pass
    with warnings.catch_warnings(record=True):  # memory_usage internal dep.
        mem = int(round(max(memory_usage(-1)))) if measure_mem else -1
    if mem >= 0:
        print('Memory consumption after import: %s' % mem)
    t0 = time.time()
    peak_mem, peak_name = mem, 'import'
    max_elapsed, elapsed_name = 0, 'N/A'
    count = 0
    for name in sorted(list(local_vars.keys()), key=lambda x: x.lower()):
        val = local_vars[name]
        if name.startswith('_'):
            continue
        elif callable(val) and name.startswith('test'):
            count += 1
            doc = val.__doc__.strip() if val.__doc__ else name
            sys.stdout.write('%s ... ' % doc)
            sys.stdout.flush()
            try:
                t1 = time.time()
                if measure_mem:
                    with warnings.catch_warnings(record=True):  # dep warn
                        mem = int(round(max(memory_usage((val, (), {})))))
                else:
                    val()
                    mem = -1
                if mem >= peak_mem:
                    peak_mem, peak_name = mem, name
                mem = (', mem: %s MB' % mem) if mem >= 0 else ''
                elapsed = int(round(time.time() - t1))
                if elapsed >= max_elapsed:
                    max_elapsed, elapsed_name = elapsed, name
                sys.stdout.write('time: %s sec%s\n' % (elapsed, mem))
                sys.stdout.flush()
            except Exception as err:
                if 'skiptest' in err.__class__.__name__.lower():
                    sys.stdout.write('SKIP (%s)\n' % str(err))
                    sys.stdout.flush()
                else:
                    raise
    elapsed = int(round(time.time() - t0))
    sys.stdout.write('Total: %s tests\n• %s sec (%s sec for %s)\n• Peak memory'
                     ' %s MB (%s)\n' % (count, elapsed, max_elapsed,
                                        elapsed_name, peak_mem, peak_name))
