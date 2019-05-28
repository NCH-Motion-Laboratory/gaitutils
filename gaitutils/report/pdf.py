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

from .. import (cfg, numutils, normaldata, sessionutils, normaldata,
                GaitDataError)
from ..viz.timedist import do_session_average_plot, do_comparison_plot, session_analysis_text
from ..viz.plots import plot_sessions, plot_session_average, plot_trial_velocities


logger = logging.getLogger(__name__)

page_size = (11.69, 8.27)  # report page size = landscape A4


def _add_footer(fig, txt):
    """Add footer text to mpl Figure"""
    #XXX: currently puts text in right bottom corner    
    fig.text(1, 0, txt, fontsize=8, color='black', ha='right', va='bottom')


def _add_header(fig, txt):
    """Add header text to mpl Figure"""
    #XXX: currently puts text in left bottom corner
    fig.text(0, 0, txt, fontsize=8, color='black', ha='left', va='bottom')


def _make_text_fig(txt, titlepage=True):
    """Make a Figure from txt"""
    fig = Figure()
    ax = fig.add_subplot(111)
    ax.set_axis_off()
    if titlepage:
        ax.text(.5, .8, txt, ha='center', va='center', weight='bold',
                fontsize=14)
    else:
        ax.text(.5, .8, txt, ha='center', va='center',
                fontsize=12)
    return fig


def _savefig(pdf, fig, header=None, footer=None):
    """add header/footer into page and save as A4"""
    if fig is None:
        return
    elif not isinstance(fig, Figure):
        raise ValueError('fig must be matplotlib Figure, got %s' % fig)
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

    model_normaldata = normaldata.read_session_normaldata(sessionpath)

    # make header page
    # timestr = time.strftime('%d.%m.%Y')  # current time, not currently used
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
    fig_title = _make_text_fig(title_txt)

    header = u'Nimi: %s Henkilötunnus: %s' % (fullname, hetu)
    musclelen_ndata = normaldata.normaldata_age(age)
    footer_musclelen = (u' Normaalidata: %s' % musclelen_ndata if
                        musclelen_ndata else u'')

    color_by = {'model': 'context', 'emg': 'trial'}
    style_by = {'model': None}

    # trial velocity plot
    fig_vel = None
    if pages['TrialVelocity']:
        logger.debug('creating velocity plot')
        fig_vel = plot_trial_velocities(sessionpath, backend='matplotlib')

    # time-distance average
    fig_timedist_avg = None
    if pages['TimeDistAverage']:
        logger.debug('creating time-distance plot')
        fig_timedist_avg = do_session_average_plot(sessionpath)

    # time-dist text
    _timedist_txt = session_analysis_text(sessionpath)
    fig_timedist_txt = _make_text_fig(_timedist_txt, titlepage=False)

    # for next 2 plots, disable the legends (too many cycles)
    # kin consistency
    fig_kinematics_cons = None
    if pages['KinematicsCons']:
        logger.debug('creating kinematics consistency plot')
        fig_kinematics_cons = plot_sessions(sessions=[sessionpath],
                                            layout_name='lb_kinematics',
                                            model_normaldata=model_normaldata,
                                            color_by=color_by,
                                            style_by=style_by,
                                            backend='matplotlib',
                                            figtitle='Kinematics consistency for %s' % sessiondir,
                                            legend=False)

    # kinetics consistency
    fig_kinetics_cons = None
    if pages['KineticsCons']:
        logger.debug('creating kinetics consistency plot')
        fig_kinetics_cons = plot_sessions(sessions=[sessionpath],
                                          layout_name='lb_kinetics',
                                          model_normaldata=model_normaldata,
                                          color_by=color_by,
                                          style_by=style_by,
                                          backend='matplotlib',
                                          figtitle='Kinetics consistency for %s' % sessiondir,
                                          legend=False)

    # musclelen consistency
    fig_musclelen_cons = None
    if pages['MuscleLenCons']:
        logger.debug('creating muscle length consistency plot')
        fig_musclelen_cons = plot_sessions(sessions=[sessionpath],
                                           layout_name='musclelen',
                                           color_by=color_by,
                                           style_by=style_by,
                                           model_normaldata=model_normaldata,
                                           backend='matplotlib',
                                           figtitle='Muscle length consistency for %s' % sessiondir,
                                           legend=False)
    # EMG consistency
    fig_emg_cons = None
    if do_emg_consistency:
        logger.debug('creating EMG consistency plot')        
        fig_emg_cons = plot_sessions(sessions=[sessionpath],
                                     layout_name='std_emg',
                                     color_by=color_by,
                                     style_by=style_by,
                                     figtitle='EMG consistency for %s' % sessiondir,
                                     legend=False,
                                     backend='matplotlib')
    # average plots, R/L
    fig_kin_avg = None
    if pages['KinAverage']:
        fig_kin_avg = plot_session_average(sessionpath,
                                           model_normaldata=model_normaldata,
                                           backend='matplotlib')

    logger.debug('creating multipage pdf %s' % pdfpath)
    with PdfPages(pdfpath) as pdf:
        _savefig(pdf, fig_title)
        _savefig(pdf, fig_vel, header)
        _savefig(pdf, fig_timedist_avg, header)
        _savefig(pdf, fig_timedist_txt)
        _savefig(pdf, fig_kinematics_cons, header)
        _savefig(pdf, fig_kinetics_cons, header)        
        _savefig(pdf, fig_musclelen_cons, header, footer_musclelen)
        _savefig(pdf, fig_emg_cons, header)
        _savefig(pdf, fig_kin_avg, header)


def create_comparison_report(sessions, pdfpath, pages=None):
    """Do a simple comparison report between sessions"""

    if pages is None:
        # if no pages specified, do them all
        pages = defaultdict(lambda: True)
    elif not any(pages.values()):
        raise GaitDataError('No pages to print')

    sessions_str = u' vs. '.join([op.split(s)[-1] for s in sessions])

    # XXX: read model normaldata according to 1st session in list
    # age may be different for different sessions
    model_normaldata = normaldata.read_session_normaldata(sessions[0])

    # make header page
    title_txt = 'HUS Liikelaboratorio\n'
    title_txt += u'Kävelyanalyysin vertailuraportti\n'
    title_txt += '\n'
    title_txt += sessions_str
    fig_title = _make_text_fig(title_txt)

    fig_timedist_cmp = None
    if pages['TimeDistCmp']:
        fig_timedist_cmp = do_comparison_plot(sessions)

    fig_kin_cmp = None
    if pages['KinCmp']:
        fig_kin_cmp = plot_sessions(sessions, tags=cfg.eclipse.repr_tags,
                                    model_normaldata=model_normaldata,
                                    style_by='session', color_by='context',
                                    backend='matplotlib')

    header = u'Comparison %s' % sessions_str
    logger.debug('creating multipage comparison pdf %s' % pdfpath)
    with PdfPages(pdfpath) as pdf:
        _savefig(pdf, fig_title)
        _savefig(pdf, fig_timedist_cmp, header)
        _savefig(pdf, fig_kin_cmp, header)

