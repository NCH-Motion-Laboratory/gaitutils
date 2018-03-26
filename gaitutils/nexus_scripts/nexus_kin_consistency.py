# -*- coding: utf-8 -*-
"""

Kin* consistency plot from Nexus. Automatically picks trials based on Eclipse
description and defined search strings.

@author: Jussi (jnu@iki.fi)
"""

import logging
import argparse
import os.path as op

from gaitutils import (Plotter, cfg, register_gui_exception_handler,
                       GaitDataError)
from gaitutils.nexus import find_tagged, get_sessionpath

logger = logging.getLogger(__name__)


def do_plot(sessions, tags, show=True, make_pdf=True):
    """ Find trials according to tags in each session and superpose all """

    pl = Plotter()
    pl.layout = cfg.layouts.overlay_lb_kin
    linecolors = ['b', 'g', 'r', 'c', 'm', 'y', 'k', 'pink']
    linecolors.reverse()  # FIXME: for pop()

    for session in sessions:
        c3ds = find_tagged(tags=tags, sessionpath=session)
        if not c3ds:
            raise GaitDataError('No trials found for session %s' % session)
        for c3d in c3ds:
            pl.open_trial(c3d)
            # only plot normaldata for last trial to speed up things
            plot_model_normaldata = (c3d == c3ds[-1] and
                                     session == sessions[-1])
            pl.plot_trial(model_tracecolor=linecolors.pop(),
                          linestyles_context=True,
                          toeoff_markers=False, legend_maxlen=30,
                          maintitle='', superpose=True, show=False,
                          plot_model_normaldata=plot_model_normaldata)
    maintitle = 'Kinematics comparison '
    maintitle += ' vs. '.join([op.split(s)[-1] for s in sessions])
    pl.set_title(maintitle)

    if show:
        pl.show()

    if make_pdf:
        pass
        #pl.create_pdf(pdf_name=')

    return pl.fig


if __name__ == '__main__':

    parser = argparse.ArgumentParser()
    parser.add_argument('--tags', metavar='p', type=str, nargs='+',
                        help='strings that must appear in trial '
                        'description or notes')
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG)
    register_gui_exception_handler()
    do_plot(sessions=[get_sessionpath()], tags=args.tags)
