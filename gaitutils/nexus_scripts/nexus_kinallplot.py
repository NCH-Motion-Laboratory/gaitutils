#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Created on Tue Apr 28 11:37:51 2015

Plot Plug-in Gait outputs (online) from Nexus.

@author: Jussi (jnu@iki.fi)
"""

import logging

from gaitutils import (Plotter, cfg, register_gui_exception_handler,
                       trial, plot_plotly)


def do_plot():

    layout = cfg.layouts.lb_kin

    if cfg.plot.backend == 'matplotlib':
        maintitleprefix = 'Kinetics/kinematics plot for '
        pl = Plotter()
        pl.layout = layout
        pl.open_nexus_trial()

        if cfg.plot.show_videos:
            for vidfile in pl.trial._get_videos_by_id():
                pl.external_play_video(vidfile)

        pl.plot_trial(maintitleprefix=maintitleprefix, show=False)
        pl.move_plot_window(10, 30)
        pl.show()

    elif cfg.plot.backend == 'plotly':
        trials = [trial.nexus_trial()]
        plot_plotly.plot_trials_browser(trials, layout,
                                        legend_type='short_name_with_cyclename')

    else:
        raise ValueError('Invalid plotting backend %s' % cfg.plot.backend)


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    register_gui_exception_handler()
    do_plot()
