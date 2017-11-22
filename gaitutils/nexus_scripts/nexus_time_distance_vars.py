# -*- coding: utf-8 -*-
"""
Plot time-distance vars as average of tagged trials

@author: Jussi (jnu@iki.fi)
"""

import logging
import argparse
import os.path as op
import matplotlib.pyplot as plt
import numpy as np

from gaitutils import c3d, nexus, register_gui_exception_handler
from gaitutils.nexus import enf2c3d
from gaitutils.plot import time_dist_barchart, save_pdf
from gaitutils.nexus_scripts.nexus_kin_consistency import find_tagged

logger = logging.getLogger(__name__)


def do_plot(search=None, show=True, make_pdf=True):

    sessionpath = nexus.get_sessionpath()
    sessiondir = op.split(sessionpath)[-1]

    scales = {'Cadence': (0, 200),
              'Walking Speed': (0, 1.5)}

    tagged_trials = find_tagged(search)
    an = list()
    for trial in tagged_trials:
        an.append(c3d.get_analysis(enf2c3d(trial), condition='average'))

    if len(an) > 1:
        an_avg = c3d.group_analysis(an)
        an_std = c3d.group_analysis(an, fun=np.std)
        title = '%d trial average from ' % len(an)
    else:
        an_avg = an[0]
        an_std = None
        title = '1 trial from '

    fig = time_dist_barchart(an_avg, an_std, scales)
    title += 'session %s' % sessiondir
    fig.suptitle(title)

    if show:
        plt.show()

    if make_pdf:
        save_pdf(op.join(sessionpath, 'time_dist.pdf'), fig)


if __name__ == '__main__':

    parser = argparse.ArgumentParser()
    parser.add_argument('--search', metavar='p', type=str, nargs='+',
                        help='strings that must appear in trial '
                        'description or notes')
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG)
    register_gui_exception_handler()
    do_plot(search=args.search)
