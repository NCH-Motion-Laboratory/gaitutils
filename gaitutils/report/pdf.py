#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""

Create single session pdf gait report.
Note: specific to the Helsinki gait lab.


@author: Jussi (jnu@iki.fi)
"""
from __future__ import absolute_import

import logging
import os.path as op
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from collections import defaultdict

from .. import (cfg, layouts, numutils, normaldata, sessionutils,
                GaitDataError)
from ..viz.plot_matplotlib import plot_trials

logger = logging.getLogger(__name__)

sort_field = 'NOTES'  # sort trials by the given Eclipse key
page_size = (11.69, 8.27)  # report page size
# create some separate PDFs for inclusion in Polygon report etc.
make_separate_pdfs = False


def _add_footer(fig, txt):
    fig.text(0, 0, txt, fontsize=8, color='black', ha='left', va='bottom')


def _add_header(fig, txt):
    fig.text(0, 1, txt, fontsize=8, color='black', ha='left', va='top')


def _savefig(pdf, fig, header=None, footer=None):
    """add header/footer into page and save as A4"""
    if fig is None:
        return
    if header is not None:
        _add_header(fig, header)
    if footer is not None:
        _add_footer(fig, footer)
    fig.set_size_inches(page_size[0], page_size[1])
    pdf.savefig(fig)


def create_report(sessionpath, info=None, pages=None):
    """Create the pdf report and save in session directory"""

    if info is None:
        info = defaultdict(lambda: '')
    fullname = info['fullname'] or ''
    hetu = info['hetu'] or ''
    session_description = info['session_description'] or ''
    if pages is None:
        pages = defaultdict(lambda: True)  # default: do all plots
    elif not any(pages.values()):
        raise ValueError('No pages to print')

    tagged_figs = list()
    repr_figs = list()
    eclipse_tags = dict()
    do_emg_consistency = False

    session_root, sessiondir = op.split(sessionpath)
    patient_code = op.split(session_root)[1]
    pdfname = sessiondir + '.pdf'
    pdfpath = op.join(sessionpath, pdfname)

    tagged_trials = sessionutils.get_c3ds(sessionpath, tags=cfg.eclipse.tags,
                                          trial_type='dynamic')
    if not tagged_trials:
        raise GaitDataError('No tagged trials found in %s' % sessiondir)
    session_t = sessionutils.get_session_date(sessionpath)
    logger.debug('session timestamp: %s', session_t)
    age = numutils.age_from_hetu(hetu, session_t) if hetu else None

    # make header page
    # timestr = time.strftime('%d.%m.%Y')  # current time, not currently used
    fig_hdr = plt.figure()
    ax = plt.subplot(111)
    plt.axis('off')
    title_txt = 'HUS Liikelaboratorio\n'
    title_txt += u'Kävelyanalyysin tulokset\n'
    title_txt += '\n'
    title_txt += u'Nimi: %s\n' % fullname
    title_txt += u'Henkilötunnus: %s\n' % (hetu if hetu else 'ei tiedossa')
    title_txt += u'Ikä mittaushetkellä: %s\n' % ('%d vuotta' % age if age
                                                   else 'ei tiedossa')
    title_txt += u'Mittaus: %s\n' % sessiondir
    if session_description:
        title_txt += u'Kuvaus: %s\n' % session_description
    title_txt += u'Mittauksen pvm: %s\n' % session_t.strftime('%d.%m.%Y')
    title_txt += u'Liikelaboratorion potilaskoodi: %s\n' % patient_code
    ax.text(.5, .8, title_txt, ha='center', va='center', weight='bold',
            fontsize=14)

    header = u'Nimi: %s Henkilötunnus: %s' % (fullname, hetu)
    musclelen_ndata = normaldata.normaldata_age(age)
    footer_musclelen = (u' Normaalidata: %s' % musclelen_ndata if
                        musclelen_ndata else u'')

    pl = Plotter()

    for c3d in tagged_trials:

        pl.open_trial(c3d)
        representative = pl.trial.eclipse_tag in cfg.eclipse.repr_tags

        # representative single trial plots
        if representative:
            if pages['TimeDistRepresentative']:
                fig = nexus_time_distance_vars.do_single_trial_plot(c3d,
                                                                    show=False)
                repr_figs.append(fig)

        # try to figure out whether we have any valid EMG signals
        emg_active = any([pl.trial.emg.status_ok(ch) for ch in
                          cfg.emg.channel_labels])

        if emg_active:

            if pages['EMGCons']:
                do_emg_consistency = True

            if pages['KinEMGMarked']:
                logger.debug('creating representative kin-EMG plots')
                # FIXME: the plotter logic is a bit weird here - it works
                # but old axes get recreated
                for side in pl.trial.fp_events['valid']:
                    side_str = {'R': 'right', 'L': 'left'}[side]
                    pl.layout = (cfg.layouts.lb_kinetics_emg_r if side == 'R'
                                 else cfg.layouts.lb_kinetics_emg_l)

                    maintitle = ('Kinetics-EMG (%s) for %s' % (side_str, pl.title_with_eclipse_info()))
                    fig = pl.plot_trial(maintitle=maintitle, show=False)
                    tagged_figs.append(fig)
                    eclipse_tags[fig] = (pl.trial.eclipse_data[sort_field])

                    # save individual pdf
                    if representative and make_separate_pdfs:
                        pdf_name = 'kinetics_EMG_%s_%s.pdf' % (pl.trial.trialname,
                                                               side_str)
                        logger.debug('creating %s' % pdf_name)
                        pl.create_pdf(pdf_name=pdf_name)

            if pages['EMGMarked']:
                logger.debug('creating representative EMG plots')
                maintitle = pl.title_with_eclipse_info('EMG plot for')
                layout = cfg.layouts.std_emg
                pl.layout = layouts.rm_dead_channels(pl.trial.emg, layout)
                fig = pl.plot_trial(maintitle=maintitle, show=False)
                tagged_figs.append(fig)
                eclipse_tags[fig] = (pl.trial.eclipse_data[sort_field])

                #  save individual pdf
                if representative and make_separate_pdfs:
                    pdf_prefix = 'EMG_'
                    pl.create_pdf(pdf_prefix=pdf_prefix)

    tagged_figs.sort(key=lambda fig: eclipse_tags[fig])

    # trial velocity plot
    fig_vel = None
    if pages['TrialVelocity']:
        logger.debug('creating velocity plot')
        fig_vel = nexus_trials_velocity.do_plot(sessionpath, show=False,
                                                make_pdf=False)

    # time-distance average
    fig_timedist_avg = None
    if pages['TimeDistAverage']:
        logger.debug('creating time-distance plot')
        fig_timedist_avg = (nexus_time_distance_vars.
                            do_session_average_plot(sessionpath=sessionpath,
                                                    show=False,
                                                    make_pdf=False))
    # consistency plots
    fig_kin_cons = None
    if pages['KinCons']:
        logger.debug('creating kin consistency plot')
        fig_kin_cons = nexus_kin_consistency.do_plot(sessions=[sessionpath],
                                                     show=False,
                                                     make_pdf=make_separate_pdfs,
                                                     backend='matplotlib')
    fig_musclelen_cons = None
    if pages['MuscleLenCons']:
        logger.debug('creating muscle length consistency plot')
        fig_musclelen_cons = nexus_musclelen_consistency.do_plot(sessionpath=sessionpath,
                                                                 show=False,
                                                                 age=age,
                                                                 make_pdf=make_separate_pdfs)
    fig_emg_cons = None
    if do_emg_consistency:
        logger.debug('creating EMG consistency plot')        
        fig_emg_cons = nexus_emg_consistency.do_plot(sessionpath=sessionpath,
                                                     show=False,
                                                     make_pdf=make_separate_pdfs,
                                                     backend='matplotlib')

    # average plots
    figs_kin_avg = list()
    if pages['KinAverage']:
        figs_kin_avg = nexus_kin_average.do_plot(sessionpath=sessionpath,
                                                 show=False, make_pdf=False)

    logger.debug('creating multipage pdf %s' % pdfpath)
    with PdfPages(pdfpath) as pdf:
        _savefig(pdf, fig_hdr)
        _savefig(pdf, fig_vel, header)
        _savefig(pdf, fig_timedist_avg, header)
        _savefig(pdf, fig_kin_cons, header)
        _savefig(pdf, fig_musclelen_cons, header, footer_musclelen)
        _savefig(pdf, fig_emg_cons, header)
        for fig in figs_kin_avg:
            _savefig(pdf, fig, header)
        for fig in repr_figs:
            _savefig(pdf, fig, header)
        for fig in tagged_figs:
            _savefig(pdf, fig, header)

    # close all created figures, otherwise they'll pop up on next show() call
    plt.close('all')


def create_comparison_report(sessions, pdfpath=None, pages=None):
    """ Do a quick comparison report between sessions """

    if pages is None:
        # if no pages specified, do them all
        pages = defaultdict(lambda: True)
    else:
        if not any(pages.values()):
            raise Exception('No pages to print')

    sessions_str = u' vs. '.join([op.split(s)[-1] for s in sessions])

    # make header page
    fig_hdr = plt.figure()
    ax = plt.subplot(111)
    plt.axis('off')
    title_txt = 'HUS Liikelaboratorio\n'
    title_txt += u'Kävelyanalyysin vertailuraportti\n'
    title_txt += '\n'
    title_txt += sessions_str
    ax.text(.5, .8, title_txt, ha='center', va='center', weight='bold',
            fontsize=14)

    fig_timedist_cmp = (nexus_time_distance_vars.
                        do_comparison_plot(sessions, tags=repr_tags,
                                           show=False))

    fig_kin_cmp = nexus_kin_consistency.do_plot(sessions, tags=repr_tags,
                                                session_styles=True,
                                                show=False)

    if pdfpath is None:
        pdfpath = QtWidgets.QFileDialog.getSaveFileName(None,
                                                        'Save PDF',
                                                        sessions[0],
                                                        '*.pdf')[0]
    if pdfpath:

        header = u'Comparison %s' % sessions_str
        logger.debug('creating multipage comparison pdf %s' % pdfpath)
        with PdfPages(pdfpath) as pdf:
            _savefig(pdf, fig_hdr)
            _savefig(pdf, fig_timedist_cmp, header)
            _savefig(pdf, fig_kin_cmp, header)

    # close all created figures, otherwise they'll pop up on next show() call
    plt.close('all')

