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

from gaitutils import nexus, cfg


def start_nexus():
    if not nexus.pid():
        # try to start Nexus for tests...
        exe = op.join(cfg.general.nexus_path, 'Nexus.exe')
        # silence Nexus output
        blackhole = file(os.devnull, 'w')
        subprocess.Popen([exe], stdout=blackhole)
        time.sleep(9)
        if not nexus.pid():
            raise Exception('Please start Vicon Nexus first')


def _subj_path(subject, trial):
    """Return path to subject trial file"""
    return op.join('testdata', 'test_subjects', subject, 'test_session',
                   trial)


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


@nottest
def run_tests_if_main():
    """Run tests in a given file if it is run as a script. Adapted from
    mne-python"""
    logging.basicConfig(level='DEBUG')
    local_vars = inspect.currentframe().f_back.f_locals
    if not local_vars.get('__name__', '') == '__main__':
        return
    # we are in a "__main__"
    t0 = time.time()
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
                val()
                elapsed = int(round(time.time() - t1))
                if elapsed >= max_elapsed:
                    max_elapsed, elapsed_name = elapsed, name
                sys.stdout.write('time: %s sec\n' % elapsed)
                sys.stdout.flush()
            except Exception as err:
                if 'skiptest' in err.__class__.__name__.lower():
                    sys.stdout.write('SKIP (%s)\n' % str(err))
                    sys.stdout.flush()
                else:
                    raise
    elapsed = int(round(time.time() - t0))
    sys.stdout.write('Total: %s tests\n• %s sec (%s sec for %s)\n'
                     % (count, elapsed, max_elapsed, elapsed_name))
