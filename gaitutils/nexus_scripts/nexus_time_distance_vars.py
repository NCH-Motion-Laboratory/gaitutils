# -*- coding: utf-8 -*-
"""
Plot time-distance vars from single trial or as average of tagged trials

@author: Jussi (jnu@iki.fi)
"""

import logging
import argparse
import os.path as op
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
import numpy as np

from gaitutils import c3d, nexus, register_gui_exception_handler, trial
from gaitutils.nexus import enf2c3d
from gaitutils.plot import time_dist_barchart, save_pdf
from gaitutils.nexus_scripts.nexus_kin_consistency import find_tagged

logger = logging.getLogger(__name__)


def do_session_average_plot(search=None, show=True, make_pdf=True):
    """Find tagged trials and plot"""

    sessionpath = nexus.get_sessionpath()
    enffiles = find_tagged(search)
    trials = [enf2c3d(fn) for fn in enffiles]
    fig = _plot_trials(trials)

    if make_pdf:
        pdf_name = op.join(sessionpath, 'time_distance_average.pdf')
        with PdfPages(pdf_name) as pdf:
            pdf.savefig(fig)

    if show:
        plt.show()

    return fig


def do_single_trial_plot(c3dfile, show=True, make_pdf=True):
    """Find tagged trials and plot"""

    sessionpath = nexus.get_sessionpath()
    enffiles = find_tagged(search)
    trials = [enf2c3d(fn) for fn in enffiles]
    fig = _plot_trials(trials)

    if make_pdf:
        pdf_name = op.join(sessionpath, 'time_distance_average.pdf')
        with PdfPages(pdf_name) as pdf:
            pdf.savefig(fig)

    if show:
        plt.show()

    return fig


def _plot_trials(trials, cond_labels):
    """Plot given trials (.c3d files).
    trials: list of lists, where inner lists represent conditions
    and list elements represent trials.
    If multiple trials per condition, they will be averaged.
    Conditions is a matching list of condition labels.
    """

    # loop thru conditions and average if needed
    res_avg_all = dict()
    res_std_all = dict()
    for cond_files, cond_label in zip(trials, cond_labels):
        ans = list()
        for c3dfile in cond_files:
            an = c3d.get_analysis(c3dfile, condition=cond_label)
            ans.append(an)
        if len(ans) > 1:  # do average
            res_avg = c3d.group_analysis(ans)
            res_std = c3d.group_analysis(ans, fun=np.std)
        else:
            res_avg = ans[0]
            res_std = dict()
            res_std[cond_label] = None
        res_avg_all.update(res_avg)
        res_std_all.update(res_std)

    return time_dist_barchart(res_avg_all, res_std_all, stddev_bars=False)


if __name__ == '__main__':

    parser = argparse.ArgumentParser()
    parser.add_argument('--search', metavar='p', type=str, nargs='+',
                        help='strings that must appear in trial '
                        'description or notes')
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG)
    register_gui_exception_handler()
    do_session_average_plot(search=args.search)
