#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""

Script to create the full pdf gait report.
Note: specific to the Helsinki gait lab.


@author: Jussi (jnu@iki.fi)
"""
from __future__ import absolute_import

import logging
import os.path as op
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from collections import defaultdict

from gaitutils import (Plotter, cfg, register_gui_exception_handler, layouts,
                       numutils, normaldata, sessionutils, nexus)

from gaitutils.nexus_scripts import (nexus_kin_consistency,
                                     nexus_emg_consistency,
                                     nexus_musclelen_consistency,
                                     nexus_kin_average,
                                     nexus_trials_velocity,
                                     nexus_time_distance_vars)


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


def do_plot(fullname=None, hetu=None, pages=None, session_description=None):

    if fullname is None:
        fullname = ''
    if hetu is None:
        hetu = ''
    if pages is None:
        # if no pages specified, do everything
        pages = defaultdict(lambda: True)
    else:
        if not any(pages.values()):
            raise Exception('No pages to print')

    tagged_figs = []
    repr_figs = []
    eclipse_tags = dict()
    do_emg_consistency = False

    sessionpath = nexus.get_sessionpath()
    session = op.split(sessionpath)[-1]
    session_root = op.split(sessionpath)[0]
    patient_code = op.split(session_root)[1]
    pdfname = session + '.pdf'
    pdf_all = op.join(sessionpath, pdfname)

    tagged_trials = sessionutils.find_tagged(sessionpath)
    if not tagged_trials:
        raise ValueError('No marked trials found in session directory')
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
    title_txt += u'Mittaus: %s\n' % session
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

        # FIXME: this would choose R when valid for both
        if 'R' in pl.trial.fp_events['valid']:
            side = 'R'
        elif 'L' in pl.trial.fp_events['valid']:
            side = 'L'
        else:
            # raise Exception('No kinetics for %s' % c3d)
            # in some cases, kinetics are not available, but we do not want
            # to die on it
            logger.warning('No kinetics for %s' % c3d)
            side = 'R'

        side_str = 'right' if side == 'R' else 'left'

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
                pl.layout = (cfg.layouts.lb_kinetics_emg_r if side == 'R' else
                             cfg.layouts.lb_kinetics_emg_l)

                maintitle = ('Kinetics-EMG '
                             '(%s) for %s' % (side_str,
                                              pl.title_with_eclipse_info()))
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
    if pages['TrialVelocity']:
        logger.debug('creating velocity plot')
        fig_vel = nexus_trials_velocity.do_plot(show=False, make_pdf=False)
    else:
        fig_vel = None

    # time-distance average
    if pages['TimeDistAverage']:
        logger.debug('creating time-distance plot')
        fig_timedist_avg = (nexus_time_distance_vars.
                            do_session_average_plot(show=False,
                                                    make_pdf=False))
    else:
        fig_timedist_avg = None

    # consistency plots
    if pages['KinCons']:
        logger.debug('creating kin consistency plot')
        fig_kin_cons = nexus_kin_consistency.do_plot(show=False,
                                                     make_pdf=make_separate_pdfs,
                                                     backend='matplotlib')
    else:
        fig_kin_cons = None

    if pages['MuscleLenCons']:
        logger.debug('creating muscle length consistency plot')
        fig_musclelen_cons = nexus_musclelen_consistency.do_plot(show=False,
                                                                 age=age,
                                                                 make_pdf=make_separate_pdfs)
    else:
        fig_musclelen_cons = None

    if do_emg_consistency:
        logger.debug('creating EMG consistency plot')        
        fig_emg_cons = nexus_emg_consistency.do_plot(show=False, make_pdf=make_separate_pdfs)
    else:
        fig_emg_cons = None

    # average plots
    if pages['KinAverage']:
        figs_kin_avg = nexus_kin_average.do_plot(show=False, make_pdf=False)
    else:
        figs_kin_avg = list()

    logger.debug('creating multipage pdf %s' % pdf_all)
    with PdfPages(pdf_all) as pdf:
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


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    logging.getLogger('matplotlib.font_manager').setLevel(logging.WARNING)
    logging.getLogger('gaitutils.utils').setLevel(logging.WARNING)
    register_gui_exception_handler()
    do_plot()
