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

    tr = trial.nexus_trial()
    layout = cfg.layouts.lb_kinematics if tr.is_static else cfg.layouts.lb_kin
    cycles = 'unnormalized' if tr.is_static else cfg.plot.default_model_cycles

    if cfg.plot.backend == 'matplotlib':
        maintitleprefix = 'Kinetics/kinematics plot for '
        pl = Plotter()
        pl.layout = layout
        pl.trial = tr

        if cfg.plot.show_videos:
            for vidfile in pl.trial._get_videos_by_id():
                pl.external_play_video(vidfile)

        pl.plot_trial(maintitleprefix=maintitleprefix,  model_cycles=cycles,
                      show=False)
        pl.move_plot_window(10, 30)
        pl.show()

    elif cfg.plot.backend == 'plotly':
        plot_plotly.plot_trials_browser([tr], layout, model_cycles=cycles,
                                        legend_type='short_name_with_cyclename')

    else:
        raise ValueError('Invalid plotting backend %s' % cfg.plot.backend)


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    register_gui_exception_handler()
    do_plot()
