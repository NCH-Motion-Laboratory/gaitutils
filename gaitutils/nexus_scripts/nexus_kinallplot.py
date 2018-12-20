#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Created on Tue Apr 28 11:37:51 2015

Plot Plug-in Gait outputs (online) from Nexus.

@author: Jussi (jnu@iki.fi)
"""

import logging

from gaitutils import (trial, Plotter, cfg, register_gui_exception_handler,
                       plot_plotly, normaldata)
import plotly


def do_plot():

    layout = cfg.layouts.lb_kin
    if cfg.plot.backend == 'matplotlib':
        pl = Plotter()
        pl.open_nexus_trial()
        pl.layout = layout
        maintitleprefix = 'Kinetics/kinematics plot for '

        if cfg.plot.show_videos:
            for vidfile in pl.trial.video_files():
                pl.external_play_video(vidfile)

        pl.plot_trial(maintitleprefix=maintitleprefix, show=False)
        pl.move_plot_window(10, 30)
        pl.show()

    elif cfg.plot.backend == 'plotly':
        model_normaldata = normaldata.read_all_normaldata()
        fig = plot_plotly.plot_trials([trial.nexus_trial()], layout,
                                      model_normaldata)
        plotly.offline.plot(fig)

    else:
        raise ValueError('Invalid plotting backend: %s' % cfg.plot.backend)


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    register_gui_exception_handler()
    do_plot()
