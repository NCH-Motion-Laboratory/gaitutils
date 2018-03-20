# -*- coding: utf-8 -*-
"""
Plot time-distance vars from single trial or as average of tagged trials

@author: Jussi (jnu@iki.fi)
"""

import logging
import argparse
import os.path as op
import matplotlib.pyplot as plt
import numpy as np

from gaitutils import c3d, nexus, register_gui_exception_handler, trial
from gaitutils.nexus import enf2c3d
from gaitutils.plot import time_dist_barchart, save_pdf
from gaitutils.nexus_scripts.nexus_kin_consistency import find_tagged

logger = logging.getLogger(__name__)


def do_plot(search=None, show=True, make_pdf=True):
    """Find tagged trials and plot"""

    enffiles = find_tagged(search)
    trials = [enf2c3d(fn) for fn in enffiles]
    return _plot_trials(trials, show=show, make_pdf=make_pdf)


def _plot_trials(trials, show=True, make_pdf=True):
    """Plot given trials (.c3d files)"""

    if not isinstance(trials, list):
        trials = [trials]

    sessionpath = nexus.get_sessionpath()
    sessiondir = op.split(sessionpath)[-1]
    ans = list()

    for c3dfile in trials:
        an = c3d.get_analysis(c3dfile, condition='average')
        # compute and inject the step width
        tr = trial.Trial(c3dfile)
        sw = trial._step_width(tr)
        an['average']['Step Width'] = dict()
        # uses avg of all cycles from trial
        an['average']['Step Width']['Right'] = np.array(sw['R']).mean()
        an['average']['Step Width']['Left'] = np.array(sw['L']).mean()
        an['average']['Step Width']['unit'] = 'mm'
        ans.append(an)

    if len(ans) > 1:  # average of multiple trials
        an_avg = c3d.group_analysis(ans)
        an_std = c3d.group_analysis(ans, fun=np.std)
        fig = time_dist_barchart(an_avg, an_std, stddev_bars=False)
        fig.suptitle('Time-distance variables, session %s'
                     ' (average of %d trials)' % (sessiondir, len(trials)))
    else:  # single trial
        fig = time_dist_barchart(ans[0])
        edi = tr.eclipse_data
        notes = edi['NOTES']
        fn_ = op.split(c3dfile)[-1]
        fig.suptitle('Time-distance variables, %s (%s)' % (fn_, notes))

    if show:
        plt.show()

    if make_pdf:
        save_pdf(op.join(sessionpath, 'time_dist.pdf'), fig)

    return fig


if __name__ == '__main__':

    parser = argparse.ArgumentParser()
    parser.add_argument('--search', metavar='p', type=str, nargs='+',
                        help='strings that must appear in trial '
                        'description or notes')
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG)
    register_gui_exception_handler()
    do_plot(search=args.search)
