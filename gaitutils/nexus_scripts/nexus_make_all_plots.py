# -*- coding: utf-8 -*-
"""
Created on Thu Sep 03 14:54:34 2015

Script to create / update all plots for the tagged trials.

This is specific to the Helsinki gait lab.



@author: Jussi (jnu@iki.fi)
"""

import time
import datetime
import logging
import os.path as op
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from collections import defaultdict

from gaitutils import (Plotter, cfg, register_gui_exception_handler, layouts,
                       numutils, normaldata)
from gaitutils.nexus import enf2c3d, get_sessionpath, get_trialname
import nexus_kin_consistency
import nexus_emg_consistency
import nexus_musclelen_consistency
import nexus_kin_average
import nexus_trials_velocity
from gaitutils.nexus_scripts.nexus_kin_consistency import find_tagged

logger = logging.getLogger(__name__)

sort_field = 'NOTES'  # sort trials by the given Eclipse key


def _add_footer(fig, txt):
    fig.text(0, 0, txt, fontsize=8, color='black', ha='left', va='bottom')


def _add_header(fig, txt):
    fig.text(0, 1, txt, fontsize=8, color='black', ha='left', va='top')


def do_plot(fullname=None, hetu=None, pages=None):

    if fullname is None:
        fullname = ''
    if hetu is None:
        hetu = ''
    if pages is None:
        pages = defaultdict(lambda: True)
    else:
        if not any(pages.values()):
            raise Exception('No pages to print')

    # collect Figure instances for creation of multipage PDF
    trial_figs = []
    eclipse_tags = dict()

    tagged_trials = find_tagged()

    # use creation date of 1st tagged trial as session timestamp
    session_t = datetime.datetime.fromtimestamp(op.getctime(tagged_trials[0]))
    logger.debug('session timestamp: %s', session_t)
    # compute subject age at time of session
    if hetu is None:
        age = None
    else:
        age = numutils.age_from_hetu(hetu, session_t)

    do_emg_consistency = False

    pl = Plotter()

    for trial in tagged_trials:

        c3d = enf2c3d(trial)
        pl.open_trial(c3d)

        # FIXME: this would choose R when valid for both
        if 'R' in pl.trial.fp_events['valid']:
            side = 'R'
        elif 'L' in pl.trial.fp_events['valid']:
            side = 'L'
        else:
            raise Exception('No kinetics for trial %s' % trial)

        side_str = 'right' if side == 'R' else 'left'

        # try to figure out whether we have any valid EMG signals
        # FIXME: refactor into EMG class
        emg_active = any([pl.trial.emg.status_ok(ch) for ch in
                          cfg.emg.channel_labels])

        if emg_active:

            if pages['EMGCons']:
                do_emg_consistency = True

            if pages['KinEMGMarked']:
                # kinetics-EMG
                pl.layout = (cfg.layouts.lb_kinetics_emg_r if side == 'R' else
                             cfg.layouts.lb_kinetics_emg_l)

                maintitle = 'Kinetics-EMG (%s) for %s' % (side_str,
                                                          pl.title_with_eclipse_info())
                fig = pl.plot_trial(maintitle=maintitle, show=False)
                trial_figs.append(fig)
                eclipse_tags[fig] = (pl.trial.eclipse_data[sort_field])

                # save individual pdfs for R1/L1
                if pl.trial.eclipse_data[sort_field].upper() in ['R1', 'L1']:
                    pdf_name = 'Kinetics_EMG_%s_%s.pdf' % (pl.trial.trialname,
                                                           side_str)
                    logger.debug('creating %s' % pdf_name)
                    pl.create_pdf(pdf_name=pdf_name)

            if pages['EMGMarked']:
                # EMG
                maintitle = pl.title_with_eclipse_info('EMG plot for')
                layout = cfg.layouts.std_emg
                pl.layout = layouts.rm_dead_channels(c3d, pl.trial.emg, layout)
                fig = pl.plot_trial(maintitle=maintitle, show=False)
                trial_figs.append(fig)
                eclipse_tags[fig] = (pl.trial.eclipse_data[sort_field])

                # save individual pdfs for R1/L1
                if pl.trial.eclipse_data[sort_field].upper() in ['R1', 'L1']:
                    pdf_prefix = 'EMG_'
                    pl.create_pdf(pdf_prefix=pdf_prefix)

    trial_figs.sort(key=lambda fig: eclipse_tags[fig])

    # trial velocity plot
    if pages['TrialVelocity']:
        fig_vel = nexus_trials_velocity.do_plot(show=False, make_pdf=False)
    else:
        fig_vel = None

    # consistency plots
    # write these out separately for inclusion in Polygon report
    if pages['KinCons']:
        fig_kin_cons = nexus_kin_consistency.do_plot(show=False, make_pdf=True)
    else:
        fig_kin_cons = None

    if pages['MuscleLenCons']:
        fig_musclelen_cons = nexus_musclelen_consistency.do_plot(show=False,
                                                                 age=age,
                                                                 make_pdf=True)
    else:
        fig_musclelen_cons = None

    if do_emg_consistency:
        fig_emg_cons = nexus_emg_consistency.do_plot(show=False, make_pdf=True)
    else:
        fig_emg_cons = None

    # average plots
    if pages['KinAverage']:
        figs_averages = nexus_kin_average.do_plot(show=False, make_pdf=False)
    else:
        figs_averages = list()

    sessionpath = get_sessionpath()
    session = op.split(sessionpath)[-1]
    session_root = op.split(sessionpath)[0]
    patient_code = op.split(session_root)[1]
    pdfname = session + '.pdf'
    pdf_all = op.join(sessionpath, pdfname)

    # make header page
    timestr = time.strftime('%d.%m.%Y')
    fig_hdr = plt.figure()
    ax = plt.subplot(111)
    plt.axis('off')
    txt = 'HUS Liikelaboratorio\n'
    txt += u'Kävelyanalyysin tulokset\n'
    txt += '\n'
    txt += u'Nimi: %s\n' % fullname
    txt += u'Henkilötunnus: %s\n' % hetu
    txt += u'Mittaus: %s\n' % session
    txt += u'Mittauksen pvm: %s\n' % session_t.strftime('%d.%m.%Y')
    txt += u'Raportin pvm: %s\n' % timestr
    txt += u'Liikelaboratorion potilaskoodi: %s\n' % patient_code
    ax.text(.5, .8, txt, ha='center', va='center', weight='bold', fontsize=14)

    header = u'Nimi: %s Henkilötunnus: %s' % (fullname, hetu)
    musclelen_ndata = normaldata.normaldata_age(age)
    footer_musclelen = (u' Normaalidata: %s' % musclelen_ndata if
                        musclelen_ndata else u'')

    logger.debug('creating multipage pdf %s' % pdf_all)
    with PdfPages(pdf_all) as pdf:
        pdf.savefig(fig_hdr)
        if fig_vel is not None:
            _add_header(fig_vel, header)
            pdf.savefig(fig_vel)
        if fig_kin_cons is not None:
            _add_header(fig_kin_cons, header)
            pdf.savefig(fig_kin_cons)
        if fig_musclelen_cons is not None:
            _add_header(fig_musclelen_cons, header)
            _add_footer(fig_musclelen_cons, footer_musclelen)
            pdf.savefig(fig_musclelen_cons)
        if fig_emg_cons is not None:
            _add_header(fig_emg_cons, header)
            pdf.savefig(fig_emg_cons)
        for fig in figs_averages:
            _add_header(fig, header)
            pdf.savefig(fig)
        for fig in trial_figs:
            _add_header(fig, header)
            pdf.savefig(fig)

    # close all created figures, otherwise they'll pop up on next show() call
    plt.close('all')


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    register_gui_exception_handler()
    do_plot()
