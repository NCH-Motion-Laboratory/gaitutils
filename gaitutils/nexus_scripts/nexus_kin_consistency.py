# -*- coding: utf-8 -*-
"""

Kin* consistency plots. Automatically picks trials based on Eclipse
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


def do_plot(sessions=None, tags=None, show=True, make_pdf=True,
            session_styles=False):
    """ Find trials according to tags in each session and superpose all.
    By default, plots tagged trials in the current Nexus session.
    session_styles uses different linestyles for each session
    """

    if sessions is None:
        sessions = [get_sessionpath()]

    if tags is None:
        tags = cfg.plot.eclipse_tags

    pl = Plotter()
    pl.layout = cfg.layouts.overlay_lb_kin
    linecolors = ['b', 'g', 'r', 'c', 'm', 'y', 'k', 'pink']
    linecolors.reverse()  # reverse for pop()
    linestyles = [':', '--', '-']

    for session in sessions:
        c3ds = find_tagged(tags=tags, sessionpath=session)
        if not c3ds:
            raise GaitDataError('No trials found for session %s' % session)
        session_style = linestyles.pop()
        for c3d in c3ds:
            pl.open_trial(c3d)
            # only plot normaldata for last trial to speed up things
            plot_model_normaldata = (c3d == c3ds[-1] and
                                     session == sessions[-1])
            # select style/color according to either session or trial
            model_tracecolor = linecolors.pop()
            if session_styles:
                model_linestyle = session_style
                linestyles_context = False
            else:
                model_linestyle = None
                linestyles_context = True

            pl.plot_trial(model_tracecolor=model_tracecolor,
                          model_linestyle=model_linestyle,
                          linestyles_context=linestyles_context,
                          toeoff_markers=False, legend_maxlen=30,
                          maintitle='', superpose=True, show=False,
                          plot_model_normaldata=plot_model_normaldata)

    # auto set title
    if len(sessions) > 1:
        maintitle = 'Kinematics comparison '
        maintitle += ' vs. '.join([op.split(s)[-1] for s in sessions])
    else:
        maintitle = ('Kinematics consistency plot, session %s' %
                     op.split(sessions[0])[-1])
    pl.set_title(maintitle)

    if show:
        pl.show()

    # to recreate old behavior...
    if make_pdf and len(sessions) == 1:
        pl.create_pdf(pdf_name=op.join(sessions[0], 'kin_consistency.pdf'))

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
