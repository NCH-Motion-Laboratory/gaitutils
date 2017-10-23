# -*- coding: utf-8 -*-
"""
Created on Thu Sep 03 14:54:34 2015

Script to create / update all kinetics/EMG plots for the marked trials.

@author: Jussi (jnu@iki.fi)
"""

import logging
import os.path as op
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

from gaitutils import Plotter, cfg, register_gui_exception_handler, layouts
from gaitutils.nexus import enf2c3d, get_sessionpath, get_trialname
import nexus_kin_consistency
import nexus_emg_consistency
import nexus_kin_average
import nexus_trials_velocity
from gaitutils.nexus_scripts.nexus_kin_consistency import find_tagged

logger = logging.getLogger(__name__)

# collect Figure instances for creation of multipage PDF
figs = []


def _coverpage():

    session = get_sessionpath()
    


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
            figs.append(pl.plot_trial(maintitle=maintitle, show=False))
            pdf_name = 'Kinetics_EMG_%s_%s.pdf' % (pl.trial.trialname,
                                                   side_str)
            pl.create_pdf(pdf_name=pdf_name)

            # EMG
            pdf_prefix = 'EMG_'
            maintitle = pl.title_with_eclipse_info('EMG plot for')
            layout = cfg.layouts.std_emg
            pl.layout = layouts.rm_dead_channels(c3d, pl.trial.emg, layout)
            figs.append(pl.plot_trial(maintitle=maintitle, show=False))
            pl.create_pdf(pdf_prefix=pdf_prefix)

    fig_vel = nexus_trials_velocity.do_plot(show=False)

    # consistency plots
    # these will automatically create pdfs
    fig_cons = nexus_kin_consistency.do_plot(show=False)
    if emg_active:
        fig_emg_cons = nexus_emg_consistency.do_plot(show=False)
    else:
        fig_emg_cons = None

    figs_averages = nexus_kin_average.do_plot(show=False)

    sessionpath = get_sessionpath()
    pdfname = 'ALL_'+op.split(sessionpath)[-1]+'.pdf'

    pdf_all = op.join(sessionpath, pdfname)

    logger.debug('creating multipage pdf %s' % pdf_all)
    with PdfPages(pdf_all) as pdf:
        pdf.savefig(fig_vel)
        pdf.savefig(fig_cons)
        if fig_emg_cons is not None:
            pdf.savefig(fig_emg_cons)
        for fig in figs_averages:
            pdf.savefig(fig)
        for fig in figs:
            pdf.savefig(fig)

    # close all created figures, otherwise they'll pop up on next show() call
    plt.close('all')


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    register_gui_exception_handler()
    do_plot()
