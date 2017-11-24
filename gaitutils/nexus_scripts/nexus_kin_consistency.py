# -*- coding: utf-8 -*-
"""
Created on Thu Sep 03 14:54:34 2015

Kin* consistency plot from Nexus. Automatically picks trials based on Eclipse
description and defined search strings.

@author: Jussi (jnu@iki.fi)
"""

import logging
import argparse

from gaitutils import Plotter, cfg, register_gui_exception_handler
from gaitutils.nexus import enf2c3d, find_trials

logger = logging.getLogger(__name__)


def find_tagged(search=None):
    """ Find tagged Eclipse trials """

    MAX_TRIALS = 8

    if search is None:
        search = cfg.plot.eclipse_tags

    eclkeys = ['DESCRIPTION', 'NOTES']
    tagged_trials = list(find_trials(eclkeys, search))

    if not tagged_trials:
        raise Exception('Did not find any trials matching the Eclipse search '
                        'strings %s in the current session directory'
                        % str(search))

    if len(tagged_trials) > MAX_TRIALS:
        raise Exception('Too many tagged trials found!')

    return tagged_trials


def do_plot(search=None, show=True, make_pdf=True):

    tagged_trials = find_tagged(search=search)

    pl = Plotter()
    pl.open_trial(enf2c3d(tagged_trials[0]))
    pl.layout = cfg.layouts.overlay_lb_kin

    linecolors = ['b', 'g', 'r', 'c', 'm', 'y', 'k', 'pink']

    for i, trialpath in enumerate(tagged_trials):
        logger.debug('plotting %s' % tagged_trials[i])
        pl.open_trial(enf2c3d(tagged_trials[i]))
        maintitle = ('Kinematics/kinetics consistency plot, '
                     'session %s' % pl.trial.sessiondir)
        # only plot normaldata for last trial to speed up things
        plot_model_normaldata = (trialpath == tagged_trials[-1])
        pl.plot_trial(model_tracecolor=linecolors[i], linestyles_context=True,
                      toeoff_markers=False,
                      maintitle=maintitle, superpose=True, show=False,
                      plot_model_normaldata=plot_model_normaldata)
    if show:
        pl.show()

    if make_pdf:
        pl.create_pdf('kin_consistency.pdf')

    return pl.fig


if __name__ == '__main__':

    parser = argparse.ArgumentParser()
    parser.add_argument('--search', metavar='p', type=str, nargs='+',
                        help='strings that must appear in trial '
                        'description or notes')
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG)
    register_gui_exception_handler()
    do_plot(search=args.search)
