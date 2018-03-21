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


def _plot_trials(trials, cond_labels, show=True, make_pdf=True, pdf_path=None):
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

    fig = time_dist_barchart(res_avg_all, res_std_all, stddev_bars=False)

    if show:
        plt.show()

    if make_pdf:
        pass
        #save_pdf(op.join(pdf_path, 'time_dist.pdf'), fig)

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
