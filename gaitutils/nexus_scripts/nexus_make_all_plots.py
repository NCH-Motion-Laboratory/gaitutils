# -*- coding: utf-8 -*-
"""
Created on Thu Sep 03 14:54:34 2015

Script to create / update all plots for the tagged trials.

This is specific to the Helsinki gait lab.



@author: Jussi (jnu@iki.fi)
"""

import time
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

sort_field = 'NOTES'  # sort trials by the given Eclipse key


def do_plot():

    # collect Figure instances for creation of multipage PDF
    figs = []
    eclipse_tags = dict()

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
            fig = pl.plot_trial(maintitle=maintitle, show=False)
            figs.append(fig)
            eclipse_tags[fig] = (pl.trial.eclipse_data[sort_field])

            # do not create individual pdfs
            # pdf_name = 'Kinetics_EMG_%s_%s.pdf' % (pl.trial.trialname,
            #                                       side_str)
            # pl.create_pdf(pdf_name=pdf_name)

            # EMG
            maintitle = pl.title_with_eclipse_info('EMG plot for')
            layout = cfg.layouts.std_emg
            pl.layout = layouts.rm_dead_channels(c3d, pl.trial.emg, layout)
            fig = pl.plot_trial(maintitle=maintitle, show=False)
            figs.append(fig)
            eclipse_tags[fig] = (pl.trial.eclipse_data[sort_field])
            # do not create individual pdfs
            # pdf_prefix = 'EMG_'
            # pl.create_pdf(pdf_prefix=pdf_prefix)

    figs.sort(key=lambda fig: eclipse_tags[fig])

    # trial velocity plot
    fig_vel = nexus_trials_velocity.do_plot(show=False, make_pdf=False)

    # consistency plots
    fig_cons = nexus_kin_consistency.do_plot(show=False, make_pdf=False)
    if emg_active:
        fig_emg_cons = nexus_emg_consistency.do_plot(show=False,
                                                     make_pdf=False)
    else:
        fig_emg_cons = None

    # average plots
    figs_averages = nexus_kin_average.do_plot(show=False, make_pdf=False)

    sessionpath = get_sessionpath()
    session = op.split(sessionpath)[-1]
    session_root = op.split(sessionpath)[0]
    patient_code = op.split(session_root)[1]
    pdfname = session + '.pdf'
    pdf_all = op.join(sessionpath, pdfname)

    # make header page
    fig_hdr = plt.figure()
    ax = plt.subplot(111)
    plt.axis('off')
    txt = 'HUS Liikelaboratorio\n'
    txt += u'Kävelyanalyysin tulokset\n'
    txt += '\n'
    txt += 'Mittaus: %s\n' % session
    txt += 'Raportti laadittu: %s\n' % time.strftime("%d.%m.%Y")
    txt += 'Liikelaboratorion potilaskoodi: %s\n' % patient_code
    ax.text(.5, .8, txt, ha='center', va='center', weight='bold', fontsize=14)

    logger.debug('creating multipage pdf %s' % pdf_all)
    with PdfPages(pdf_all) as pdf:
        pdf.savefig(fig_hdr)
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
