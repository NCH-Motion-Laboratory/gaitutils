#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Create pdf gait report.
Note: specific to the Helsinki gait lab!

@author: Jussi (jnu@iki.fi)
"""
from __future__ import absolute_import

import logging
import os.path as op
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.figure import Figure
from collections import defaultdict

from .. import (cfg, numutils, normaldata, sessionutils,
                GaitDataError)
from ..viz.plot_matplotlib import plot_trial_velocities
from ..viz.timedist import do_session_average_plot
from ..viz.plots import plot_sessions, plot_session_average


logger = logging.getLogger(__name__)

page_size = (11.69, 8.27)  # report page size = landscape A4


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

    do_emg_consistency = True

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
    fig_hdr = Figure()
    ax = fig_hdr.add_subplot(111)
    ax.set_axis_off()
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

    # trial velocity plot
    fig_vel = None
    if pages['TrialVelocity']:
        logger.debug('creating velocity plot')
        fig_vel = plot_trial_velocities(sessionpath)

    # time-distance average
    fig_timedist_avg = None
    if pages['TimeDistAverage']:
        logger.debug('creating time-distance plot')
        fig_timedist_avg = do_session_average_plot(sessionpath=sessionpath)

    # kin consistency
    fig_kin_cons = None
    if pages['KinCons']:
        logger.debug('creating kin consistency plot')
        fig_kin_cons = plot_sessions(sessions=[sessionpath], style_by='context',
                                     backend='matplotlib')

    # musclelen consistency
    fig_musclelen_cons = None
    if pages['MuscleLenCons']:
        logger.debug('creating muscle length consistency plot')
        fig_musclelen_cons = plot_sessions(sessions=[sessionpath], layout_name='musclelen',
                                           style_by='context',
                                           backend='matplotlib')
    
    # EMG consistency
    fig_emg_cons = None
    if do_emg_consistency:
        logger.debug('creating EMG consistency plot')        
        fig_emg_cons = plot_sessions(sessions=[sessionpath],
                                     layout_name='std_emg',
                                     backend='matplotlib')

    # average plots, R/L
    figs_kin_avg = list()
    if pages['KinAverage']:
        figs_kin_avg = plot_session_average(sessionpath, backend='matplotlib')

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
    fig_hdr = Figure()
    ax = fig_hdr.add_subplot(111)
    ax.set_axis('off')
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


