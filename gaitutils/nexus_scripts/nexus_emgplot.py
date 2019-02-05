#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Created on Tue Apr 28 11:25:38 2015

EMG plot from Nexus.

@author: Jussi (jnu@iki.fi)
"""

import logging

from gaitutils import (Plotter, layouts, register_gui_exception_handler, trial,
                       plot_plotly)
from gaitutils.config import cfg


def do_plot():

    layout_ = cfg.layouts.std_emg
    tr = trial.nexus_trial()
    layout = layouts.rm_dead_channels(tr.emg, layout_)

    if cfg.plot.backend == 'matplotlib':
        pl = Plotter()
        pl.trial = tr
        pl.layout = layout
        maintitle = pl.title_with_eclipse_info('EMG plot for')
        pl.plot_trial(maintitle=maintitle)
        pdf_prefix = 'EMG_'
        pl.create_pdf(pdf_prefix=pdf_prefix)

    elif cfg.plot.backend == 'plotly':
        plot_plotly.plot_trials_browser([tr], layout,
                                        legend_type='short_name_with_cyclename')


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    register_gui_exception_handler()
    do_plot()
