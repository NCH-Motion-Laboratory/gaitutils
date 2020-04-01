# -*- coding: utf-8 -*-
"""
Create pdf gait report.

@author: Jussi (jnu@iki.fi)
"""
from __future__ import absolute_import

import logging
import io
import os.path as op
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.figure import Figure
from collections import defaultdict

from .. import cfg, sessionutils, normaldata, GaitDataError, trial
from ulstools.num import age_from_hetu
from ..viz.timedist import do_session_average_plot, do_comparison_plot
from ..timedist import _session_analysis_text
from ..viz.plots import plot_sessions, plot_session_average, plot_trial_velocities


logger = logging.getLogger(__name__)

page_size = (11.69, 8.27)  # report page size = landscape A4
pdf_backend = 'matplotlib'


def _add_footer(fig, txt):
    """Add footer text to mpl Figure"""
    # XXX: currently puts text in right bottom corner
    fig.text(1, 0, txt, fontsize=8, color='black', ha='right', va='bottom')


def _add_header(fig, txt):
    """Add header text to mpl Figure"""
    # XXX: currently puts text in left bottom corner
    fig.text(0, 0, txt, fontsize=8, color='black', ha='left', va='bottom')


def _make_text_fig(txt, titlepage=True):
    """Make a Figure from txt"""
    fig = Figure()
    ax = fig.add_subplot(111)
    ax.set_axis_off()
    if titlepage:
        ax.text(0.5, 0.8, txt, ha='center', va='center', weight='bold', fontsize=14)
    else:
        ax.text(0.5, 0.8, txt, ha='center', va='center', fontsize=12)
    return fig


def _savefig(pdf, fig, header=None, footer=None):
    """Add header/footer into page and save as A4"""
    if fig is None:
        return
    elif not isinstance(fig, Figure):
        raise TypeError('fig must be matplotlib Figure, got %s' % fig)
    if header is not None:
        _add_header(fig, header)
    if footer is not None:
        _add_footer(fig, footer)
    fig.set_size_inches(page_size[0], page_size[1])
    pdf.savefig(fig)


def create_report(sessionpath, info=None, pages=None, destdir=None):
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
    if destdir is None:
        destdir = sessionpath
    pdfname = sessiondir + '.pdf'
    pdfpath = op.join(destdir, pdfname)

    tagged_trials = sessionutils._get_tagged_dynamic_c3ds_from_sessions(
        [sessionpath], tags=cfg.eclipse.tags
    )
    # XXX: do we unnecessarily load all trials twice (since plotting calls below don't
    # use the trials loaded here), or is it a non issue due to caching of c3d files?
    trials = (trial.Trial(t) for t in tagged_trials)
    has_kinetics = any(c.on_forceplate for t in trials for c in t.cycles)

    session_t = sessionutils.get_session_date(sessionpath)
    logger.debug('session timestamp: %s', session_t)
    age = age_from_hetu(hetu, session_t) if hetu else None

    model_normaldata = normaldata.read_session_normaldata(sessionpath)

    # make header page
    # timestr = time.strftime('%d.%m.%Y')  # current time, not currently used
    title_txt = 'HUS Liikelaboratorio\n'
    title_txt += u'Kävelyanalyysin tulokset\n'
    title_txt += '\n'
    title_txt += u'Nimi: %s\n' % fullname
    title_txt += u'Henkilötunnus: %s\n' % (hetu if hetu else 'ei tiedossa')
    title_txt += u'Ikä mittaushetkellä: %s\n' % (
        '%d vuotta' % age if age else 'ei tiedossa'
    )
    title_txt += u'Mittaus: %s\n' % sessiondir
    if session_description:
        title_txt += u'Kuvaus: %s\n' % session_description
    title_txt += u'Mittauksen pvm: %s\n' % session_t.strftime('%d.%m.%Y')
    title_txt += u'Liikelaboratorion potilaskoodi: %s\n' % patient_code
    fig_title = _make_text_fig(title_txt)

    header = u'Nimi: %s Henkilötunnus: %s' % (fullname, hetu)
    musclelen_ndata = normaldata.normaldata_age(age)
    footer_musclelen = (
        u' Normaalidata: %s' % musclelen_ndata if musclelen_ndata else u''
    )

    # make the figures
    legend_type = cfg.report.legend_type  # not currently used (legends disabled)
    style_by = cfg.report.style_by
    color_by = cfg.report.color_by

    # trial velocity plot
    fig_vel = None
    if pages['TrialVelocity']:
        logger.debug('creating velocity plot')
        fig_vel = plot_trial_velocities(sessionpath, backend=pdf_backend)

    # time-distance average
    fig_timedist_avg = None
    if pages['TimeDistAverage']:
        logger.debug('creating time-distance plot')
        fig_timedist_avg = do_session_average_plot(sessionpath, backend=pdf_backend)

    # time-dist text
    _timedist_txt = _session_analysis_text(sessionpath)

    # for next 2 plots, disable the legends (there are typically too many cycles)
    # kin consistency
    fig_kinematics_cons = None
    if pages['KinematicsCons']:
        logger.debug('creating kinematics consistency plot')
        fig_kinematics_cons = plot_sessions(
            sessions=[sessionpath],
            layout_name='lb_kinematics',
            model_normaldata=model_normaldata,
            color_by=color_by,
            style_by=style_by,
            backend=pdf_backend,
            figtitle='Kinematics consistency for %s' % sessiondir,
            legend_type=legend_type,
            legend=False,
        )

    # kinetics consistency
    fig_kinetics_cons = None
    if pages['KineticsCons'] and has_kinetics:
        logger.debug('creating kinetics consistency plot')
        fig_kinetics_cons = plot_sessions(
            sessions=[sessionpath],
            layout_name='lb_kinetics',
            model_normaldata=model_normaldata,
            color_by=color_by,
            style_by=style_by,
            backend=pdf_backend,
            figtitle='Kinetics consistency for %s' % sessiondir,
            legend_type=legend_type,
            legend=False,
        )

    # musclelen consistency
    fig_musclelen_cons = None
    if pages['MuscleLenCons']:
        logger.debug('creating muscle length consistency plot')
        fig_musclelen_cons = plot_sessions(
            sessions=[sessionpath],
            layout_name='musclelen',
            color_by=color_by,
            style_by=style_by,
            model_normaldata=model_normaldata,
            backend=pdf_backend,
            figtitle='Muscle length consistency for %s' % sessiondir,
            legend_type=legend_type,
            legend=False,
        )
    # EMG consistency
    fig_emg_cons = None
    if do_emg_consistency:
        logger.debug('creating EMG consistency plot')
        fig_emg_cons = plot_sessions(
            sessions=[sessionpath],
            layout_name='std_emg',
            color_by=color_by,
            style_by=style_by,
            figtitle='EMG consistency for %s' % sessiondir,
            legend_type=legend_type,
            legend=False,
            backend=pdf_backend,
        )
    # average plots, R/L
    fig_kin_avg = None
    if pages['KinAverage']:
        fig_kin_avg = plot_session_average(
            sessionpath, model_normaldata=model_normaldata, backend=pdf_backend,
        )

    # save the pdf file
    logger.debug('creating multipage pdf %s' % pdfpath)
    with PdfPages(pdfpath) as pdf:
        _savefig(pdf, fig_title)
        _savefig(pdf, fig_vel, header)
        _savefig(pdf, fig_timedist_avg, header)
        _savefig(pdf, fig_kinematics_cons, header)
        _savefig(pdf, fig_kinetics_cons, header)
        _savefig(pdf, fig_musclelen_cons, header, footer_musclelen)
        _savefig(pdf, fig_emg_cons, header)
        _savefig(pdf, fig_kin_avg, header)

    # here we sneakily also export the time-distance data in text format
    timedist_txt_file = sessiondir + '_time_distance.txt'
    timedist_txt_path = op.join(destdir, timedist_txt_file)
    with io.open(timedist_txt_path, 'w', encoding='utf8') as f:
        logger.debug('writing timedist text data into %s' % timedist_txt_path)
        f.write(_timedist_txt)

    return 'Created %s' % pdfpath


def create_comparison_report(sessionpaths, info=None, pages=None, destdir=None):
    """Create pdf comparison report"""
    if info is None:
        info = defaultdict(lambda: '')

    if pages is None:
        # if no pages specified, do them all
        pages = defaultdict(lambda: True)
    elif not any(pages.values()):
        raise GaitDataError('No pages to print')

    # check for kinetics
    tagged_trials = sessionutils._get_tagged_dynamic_c3ds_from_sessions(
        sessionpaths, tags=cfg.eclipse.tags
    )
    trials = (trial.Trial(t) for t in tagged_trials)
    any_kinetics = any(c.on_forceplate for t in trials for c in t.cycles)

    # compose a name for the resulting pdf; it will be saved in the first session dir
    sessionpath = sessionpaths[0]
    if destdir is None:
        destdir = sessionpath
    # XXX: filenames can become very long here
    pdfname = ' VS '.join(op.split(sp)[1] for sp in sessionpaths) + '.pdf'
    pdfpath = op.join(destdir, pdfname)

    # read model normaldata according to first session
    # age may be different for different sessions but this is probably good enough
    model_normaldata = normaldata.read_session_normaldata(sessionpath)

    # make header page
    fullname = info['fullname'] or ''
    hetu = info['hetu'] or ''
    title_txt = 'HUS Liikelaboratorio\n'
    title_txt += u'Kävelyanalyysin vertailuraportti\n'
    title_txt += '\n'
    title_txt += info['session_description']
    title_txt += '\n'
    title_txt += u'Nimi: %s\n' % fullname
    title_txt += u'Henkilötunnus: %s\n' % hetu
    fig_title = _make_text_fig(title_txt)

    # make the figures
    legend_type = cfg.report.comparison_legend_type
    style_by = cfg.report.comparison_style_by
    color_by = cfg.report.comparison_color_by
    emg_mode = 'rms' if cfg.report.comparison_emg_rms else None

    fig_timedist = (
        do_comparison_plot(sessionpaths, backend=pdf_backend)
        if pages['TimeDist']
        else None
    )

    fig_kinematics = (
        plot_sessions(
            sessionpaths,
            tags=cfg.eclipse.repr_tags,
            layout_name='lb_kinematics',
            model_normaldata=model_normaldata,
            figtitle='Kinematics comparison',
            style_by=style_by,
            color_by=color_by,
            backend=pdf_backend,
            legend_type=legend_type,
        )
        if pages['Kinematics']
        else None
    )

    fig_kinetics = (
        plot_sessions(
            sessionpaths,
            tags=cfg.eclipse.repr_tags,
            layout_name='lb_kinetics',
            model_normaldata=model_normaldata,
            figtitle='Kinetics comparison',
            style_by=style_by,
            color_by=color_by,
            legend_type=legend_type,
            backend=pdf_backend,
        )
        if pages['Kinetics'] and any_kinetics
        else None
    )

    fig_musclelen = (
        plot_sessions(
            sessionpaths,
            tags=cfg.eclipse.repr_tags,
            layout_name='musclelen',
            model_normaldata=model_normaldata,
            figtitle='Muscle length comparison',
            style_by=style_by,
            color_by=color_by,
            legend_type=legend_type,
            backend=pdf_backend,
        )
        if pages['MuscleLen']
        else None
    )

    fig_emg = (
        plot_sessions(
            sessionpaths,
            tags=cfg.eclipse.repr_tags,
            layout_name='std_emg',
            emg_mode=emg_mode,
            figtitle='EMG comparison',
            style_by=style_by,
            color_by=color_by,
            legend_type=legend_type,
            backend=pdf_backend,
        )
        if pages['MuscleLen']
        else None
    )

    header = u'Nimi: %s Henkilötunnus: %s' % (fullname, hetu)
    logger.debug('creating multipage comparison pdf %s' % pdfpath)
    with PdfPages(pdfpath) as pdf:
        _savefig(pdf, fig_title)
        _savefig(pdf, fig_timedist, header)
        _savefig(pdf, fig_kinematics, header)
        _savefig(pdf, fig_kinetics, header)
        _savefig(pdf, fig_musclelen, header)
        _savefig(pdf, fig_emg, header)

    return 'Created %s\nin %s' % (pdfname, sessionpath)
