# -*- coding: utf-8 -*-
"""
Created on Thu Sep 03 14:54:34 2015

Script to create / update all kinetics/EMG plots for the marked trials.

@author: Jussi (jnu@iki.fi)
"""

import logging
import matplotlib.pyplot as plt

from gaitutils import Plotter, cfg, register_gui_exception_handler, layouts
from gaitutils.nexus import enf2c3d
import nexus_kin_consistency
import nexus_emg_consistency
import nexus_kin_average
from gaitutils.nexus_scripts.nexus_kin_consistency import find_tagged

logger = logging.getLogger(__name__)


def do_plot():

    tagged_trials = find_tagged()

    pl = Plotter()

    for trial in tagged_trials:

        c3d = enf2c3d(trial)
        pl.open_trial(c3d)

        side = pl.trial.fp_events['valid']
        if side not in ['L', 'R']:
            raise Exception('Need one kinetics cycle per trial')

        side_str = 'right' if side == 'R' else 'left'

        # try to figure out whether we have any valid EMG signals
        emg_active = any([pl.trial.emg.status_ok(ch) for ch in
                          cfg.emg.channel_labels])

        if emg_active:
            # kinetics-EMG
            pl.layout = (cfg.layouts.lb_kinetics_emg_r if side == 'R' else
                         cfg.layouts.lb_kinetics_emg_l)

            maintitle = 'Kinetics-EMG (%s) for %s' % (side_str,
                                                      pl.title_with_eclipse_info())
            pl.plot_trial(maintitle=maintitle, show=False)
            pdf_name = 'Kinetics_EMG_%s_%s.pdf' % (pl.trial.trialname,
                                                   side_str)
            pl.create_pdf(pdf_name=pdf_name)

            # EMG
            pdf_prefix = 'EMG_'
            maintitle = pl.title_with_eclipse_info('EMG plot for')
            layout = cfg.layouts.std_emg
            pl.layout = layouts.rm_dead_channels(c3d, pl.trial.emg, layout)
            pl.plot_trial(maintitle=maintitle, show=False)
            pl.create_pdf(pdf_prefix=pdf_prefix)

    # consistency plots
    # these will automatically create pdfs
    nexus_kin_consistency.do_plot(show=False)
    if emg_active:
        nexus_emg_consistency.do_plot(show=False)

    nexus_kin_average.do_plot(show=False)

    # close all created figures, otherwise they'll pop up on next show() call
    plt.close('all')


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    register_gui_exception_handler()
    do_plot()
