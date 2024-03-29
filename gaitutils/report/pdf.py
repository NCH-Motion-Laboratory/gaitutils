# -*- coding: utf-8 -*-
"""
Create gait reports in pdf format.

@author: Jussi (jnu@iki.fi)
"""


import itertools

import logging
import io
from pathlib import Path
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.figure import Figure
from collections import defaultdict

from .. import sessionutils, normaldata, trial, models, stats
from ..envutils import GaitDataError
from ..config import cfg
from ..viz import timedist
from ulstools.num import age_from_hetu
from ..viz.plots import _plot_sessions, _plot_session_average, plot_trial_velocities
from ..viz.plot_matplotlib import _plot_extracted_table_plotly
from .text import _curve_extracted_text, _session_analysis_text
from .translations import translate


logger = logging.getLogger(__name__)

page_size = (11.69, 8.27)  # report page size = landscape A4
pdf_backend = 'matplotlib'


def _add_footer(fig, txt):
    """Add footer text to matplotlib Figure"""
    # XXX: currently puts text in right bottom corner
    fig.text(1, 0, txt, fontsize=8, color='black', ha='right', va='bottom')


def _add_header(fig, txt):
    """Add header text to matplotlib Figure"""
    # XXX: currently puts text in left bottom corner
    fig.text(0, 0, txt, fontsize=8, color='black', ha='left', va='bottom')


def _make_text_fig(txt, titlepage=True):
    """Make a Figure from given text.

    If titlepage is True, use larger font in bold.
    """
    fig = Figure()
    ax = fig.add_subplot(111)
    ax.set_axis_off()
    if titlepage:
        ax.text(0.5, 0.8, txt, ha='center', va='center', weight='bold', fontsize=14)
    else:
        ax.text(0.5, 0.8, txt, ha='center', va='center', fontsize=12)
    return fig


def _savefig(pdf, fig, header=None, footer=None):
    """Save figure fig into the given pdf object.

    Adds header/footer into page and saves as A4.
    """
    if fig is None:
        return
    elif not isinstance(fig, Figure):
        raise TypeError(f'fig must be matplotlib Figure, got {fig}')
    if header is not None:
        _add_header(fig, header)
    if footer is not None:
        _add_footer(fig, footer)
    fig.set_size_inches(page_size[0], page_size[1])
    pdf.savefig(fig)


def create_report(
    sessionpath,
    info=None,
    pages=None,
    destdir=None,
    write_timedist=False,
    write_extracted=False,
):
    """Create a single-session pdf report.

    Parameters
    ----------
    sessionpath : str | Path
        Path to session.
    info : dict, optional
        Patient info dict.
    pages : dict, optional
        Which pages to include to include in report. Set value to True for
        desired pages. If None, do all pages. Currently supported keys:
        'TrialVelocity'
        'TimeDistAverage'
        'KinematicsCons'
        'TorsoKinematicsCons'
        'KineticsCons'
        'MuscleLenCons'
        'KinAverage'
    destdir : str, optional
        Destination directory for the pdf report. If None, write into sessionpath.
    write_timedist : bool
        If True, also write a text report of time-distance parameters into the
        same directory as the pdf.
    write_extracted : bool
        If True, also write a text report of curve extracted values into the
        same directory as the pdf.

    Returns
    -------
    str
        A status message.
    """
    sessionpath = Path(sessionpath)
    if info is None:
        info = defaultdict(lambda: '')
    fullname = info['fullname'] or ''
    hetu = info['hetu'] or ''
    session_description = info['session_description'] or ''
    if pages is None:
        pages = defaultdict(lambda: True)  # default: do all plots
    elif not any(pages.values()):
        pages = defaultdict(lambda: False)

    do_emg_consistency = True

    session_root, sessiondir = sessionpath.parent, sessionpath.name
    patient_code = session_root.name
    if destdir is None:
        destdir = sessionpath
    pdfname = sessiondir + '.pdf'
    pdfpath = destdir / pdfname

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

    model_normaldata = normaldata._read_session_normaldata(sessionpath)

    # make header page
    # timestr = time.strftime('%d.%m.%Y')  # current time, not currently used
    title_txt = f'{cfg.report.laboratory_name}\n'
    title_txt += f"{translate('Results of gait analysis')}\n"
    title_txt += '\n'
    title_txt += f"{translate('Name')}: {fullname}\n"
    title_txt += '%s: %s\n' % (
        translate('Social security number'),
        hetu if hetu else translate('unknown'),
    )
    age_str = '%d %s' % (age, translate('years')) if age else translate('unknown')
    title_txt += f"{translate('Age at time of measurement')}: {age_str}\n"
    title_txt += f"{translate('Session')}: {sessiondir}\n"
    if session_description:
        title_txt += f"{translate('Description')}: {session_description}\n"
    title_txt += '%s: %s\n' % (
        translate('Session date'),
        session_t.strftime('%d.%m.%Y'),
    )
    title_txt += f"{translate('Patient code')}: {patient_code}\n"
    fig_title = _make_text_fig(title_txt)

    header = '%s: %s %s: %s' % (
        translate('Name'),
        fullname,
        translate('Social security number'),
        hetu,
    )
    musclelen_ndata = normaldata._find_normaldata_for_age(age)
    footer_musclelen = (
        f" {translate('Normal data')}: {musclelen_ndata}" if musclelen_ndata else ''
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
        fig_timedist_avg = timedist.plot_session_average(
            sessionpath, backend=pdf_backend
        )

    # for next few plots, disable the legends (there are typically too many cycles)
    # kin consistency
    fig_kinematics_cons = None
    if pages['KinematicsCons']:
        logger.debug('creating kinematics consistency plot')
        fig_kinematics_cons = _plot_sessions(
            sessions=[sessionpath],
            layout='lb_kinematics',
            model_normaldata=model_normaldata,
            color_by=color_by,
            style_by=style_by,
            backend=pdf_backend,
            figtitle=f'Kinematics consistency for {sessiondir}',
            legend_type=legend_type,
            legend=False,
        )

    # kinetics consistency
    fig_kinetics_cons = None
    if pages['KineticsCons'] and has_kinetics:
        logger.debug('creating kinetics consistency plot')
        fig_kinetics_cons = _plot_sessions(
            sessions=[sessionpath],
            layout='lb_kinetics_web',
            model_normaldata=model_normaldata,
            color_by=color_by,
            style_by=style_by,
            backend=pdf_backend,
            figtitle=f'Kinetics consistency for {sessiondir}',
            legend_type=legend_type,
            legend=False,
        )

    # torso consistency
    fig_torso_kinematics_cons = None
    if pages['TorsoKinematicsCons']:
        logger.debug('creating torso kinematics consistency plot')
        fig_torso_kinematics_cons = _plot_sessions(
            sessions=[sessionpath],
            layout='torso',
            model_normaldata=model_normaldata,
            color_by=color_by,
            style_by=style_by,
            backend=pdf_backend,
            figtitle=f'Torso kinematics consistency for {sessiondir}',
            legend_type=legend_type,
            legend=False,
        )

    # musclelen consistency
    fig_musclelen_cons = None
    if pages['MuscleLenCons']:
        logger.debug('creating muscle length consistency plot')
        fig_musclelen_cons = _plot_sessions(
            sessions=[sessionpath],
            layout='musclelen',
            color_by=color_by,
            style_by=style_by,
            model_normaldata=model_normaldata,
            backend=pdf_backend,
            figtitle=f'Muscle length consistency for {sessiondir}',
            legend_type=legend_type,
            legend=False,
        )
    # EMG consistency
    fig_emg_cons = None
    if do_emg_consistency:
        logger.debug('creating EMG consistency plot')
        fig_emg_cons = _plot_sessions(
            sessions=[sessionpath],
            layout='std_emg',
            color_by=color_by,
            style_by=style_by,
            figtitle=f'EMG consistency for {sessiondir}',
            legend_type=legend_type,
            legend=False,
            backend=pdf_backend,
        )
    # EMG consistency, back muscles
    fig_back_emg_cons = None
    if pages['BackEMGCons']:
        logger.debug('creating EMG consistency plot')
        fig_back_emg_cons = _plot_sessions(
            sessions=[sessionpath],
            layout='back_emg',
            color_by=color_by,
            style_by=style_by,
            figtitle=f'EMG back muscles consistency for {sessiondir}',
            legend_type=legend_type,
            legend=False,
            backend=pdf_backend,
        )

    # average plots, R/L
    fig_kin_avg = None
    if pages['KinAverage']:
        fig_kin_avg = _plot_session_average(
            sessionpath,
            model_normaldata=model_normaldata,
            backend=pdf_backend,
        )

    # prep for extracted values if needed
    if pages['Extracted'] or write_extracted:
        vardefs_dict = dict(cfg.report.vardefs)
        allvars = [vardef[0] for vardefs in vardefs_dict.values() for vardef in vardefs]
        from_models = set(models.model_from_var(var) for var in allvars)
        curve_vals = {
            sessionpath.name: stats._trials_extract_values(
                tagged_trials, from_models=from_models
            )
        }

    # tables of curve extracted values
    figs_extracted = list()
    if pages['Extracted']:
        logger.debug('plotting curve extracted values')
        for title, vardefs in vardefs_dict.items():
            fig = _plot_extracted_table_plotly(curve_vals, vardefs)
            fig.tight_layout()
            fig.set_dpi(300)
            fig.suptitle(f'Curve extracted values: {title}')
            figs_extracted.append(fig)

    # save the pdf file
    logger.debug(f'creating multipage pdf {pdfpath}')
    with PdfPages(pdfpath) as pdf:
        _savefig(pdf, fig_title)
        _savefig(pdf, fig_vel, header)
        _savefig(pdf, fig_timedist_avg, header)
        _savefig(pdf, fig_kinematics_cons, header)
        _savefig(pdf, fig_torso_kinematics_cons, header)
        _savefig(pdf, fig_kinetics_cons, header)
        _savefig(pdf, fig_musclelen_cons, header, footer_musclelen)
        _savefig(pdf, fig_emg_cons, header)
        _savefig(pdf, fig_back_emg_cons, header)        
        _savefig(pdf, fig_kin_avg, header)
        for fig in figs_extracted:
            _savefig(pdf, fig, header)

    # save the time-distance parameters into a text file
    if write_timedist:
        _timedist_txt = _session_analysis_text(sessionpath)
        timedist_txt_file = sessiondir + '_time_distance.txt'
        timedist_txt_path = destdir / timedist_txt_file
        with io.open(timedist_txt_path, 'w', encoding='utf8') as f:
            logger.debug(f'writing timedist text data into {timedist_txt_path}')
            f.write(_timedist_txt)

    # save the curve extraced values into a text file
    if write_extracted:
        extracted_txt = '\n'.join(_curve_extracted_text(curve_vals, vardefs_dict))
        extracted_txt_file = sessiondir + '_curve_values.txt'
        extracted_txt_path = destdir / extracted_txt_file
        with io.open(extracted_txt_path, 'w', encoding='utf8') as f:
            logger.debug(f'writing extracted text data into {extracted_txt_path}')
            f.write(extracted_txt)

    return f'Created {pdfpath}'


def create_comparison_report(
    sessionpaths, info=None, pages=None, destdir=None, write_extracted=False
):
    """Create a comparison pdf report.

    Parameters
    ----------
    sessionpaths : list
        List of paths to sessions.
    info : dict, optional
        Patient info dict.
    pages : dict, optional
        Which pages to include to include in report. Set value to True for
        desired pages. Currently supported keys:
        'TimeDist'
        'Kinematics'
        'Kinetics'
        'MuscleLen'
        'Extracted'
    destdir : str, optional
        Destination directory for the pdf report. If None, write into first
        session path.

    Returns
    -------
    str
        A status message.
    """

    if len(sessionpaths) <= 1:
        raise GaitDataError('need at least two sessions')

    if info is None:
        info = defaultdict(lambda: '')

    if pages is None:
        # if no pages specified, do them all
        pages = defaultdict(lambda: True)
    elif not any(pages.values()):
        pages = defaultdict(lambda: False)

    # gather trials and check for kinetics
    trials_dict = dict()
    for session in sessionpaths:
        trials_dict[session] = sessionutils._get_tagged_dynamic_c3ds_from_sessions(
            session, tags=cfg.eclipse.tags
        )
    alltrials = (
        trial.Trial(t) for t in itertools.chain.from_iterable(trials_dict.values())
    )
    any_kinetics = any(c.on_forceplate for t in alltrials for c in t.cycles)

    # compose a name for the resulting pdf; it will be saved in the first session dir
    sessionpath = sessionpaths[0]
    if destdir is None:
        destdir = sessionpath
    # XXX: filenames can become very long here
    pdfname = ' VS '.join(sp.name for sp in sessionpaths) + '.pdf'
    pdfpath = destdir / pdfname

    # read model normaldata according to first session
    # age may be different for different sessions but this is probably good enough
    model_normaldata = normaldata._read_session_normaldata(sessionpath)

    # make header page
    fullname = info['fullname'] or ''
    hetu = info['hetu'] or ''
    title_txt = f'{cfg.report.laboratory_name}\n'
    title_txt += f"{translate('Comparison report')}\n"
    title_txt += '\n'
    title_txt += info['session_description']
    title_txt += '\n'
    title_txt += f"{translate('Name')}: {fullname}\n"
    title_txt += f"{translate('Social security number')}: {hetu}\n"
    fig_title = _make_text_fig(title_txt)

    # make the figures
    legend_type = cfg.report.comparison_legend_type
    style_by = cfg.report.comparison_style_by
    color_by = cfg.report.comparison_color_by
    emg_mode = 'envelope' if cfg.report.comparison_emg_as_envelope else None

    fig_timedist = (
        timedist.plot_comparison(sessionpaths, backend=pdf_backend)
        if pages['TimeDist']
        else None
    )

    fig_kinematics = (
        _plot_sessions(
            sessionpaths,
            tags=cfg.eclipse.repr_tags,
            layout='lb_kinematics',
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
        _plot_sessions(
            sessionpaths,
            tags=cfg.eclipse.repr_tags,
            layout='lb_kinetics_web',
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
        _plot_sessions(
            sessionpaths,
            tags=cfg.eclipse.repr_tags,
            layout='musclelen',
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
        _plot_sessions(
            sessionpaths,
            tags=cfg.eclipse.repr_tags,
            layout='std_emg',
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

    # prep for extracted values if needed
    if pages['Extracted'] or write_extracted:
        vardefs_dict = dict(cfg.report.vardefs)
        allvars = [vardef[0] for vardefs in vardefs_dict.values() for vardef in vardefs]
        from_models = set(models.model_from_var(var) for var in allvars)
        curve_vals = {
            session.name: stats._trials_extract_values(trials, from_models=from_models)
            for session, trials in trials_dict.items()
        }

    # tables of curve extracted values
    figs_extracted = list()
    if pages['Extracted']:
        logger.debug('plotting curve extracted values')
        for title, vardefs in vardefs_dict.items():
            fig = _plot_extracted_table_plotly(curve_vals, vardefs)
            fig.tight_layout()
            fig.set_dpi(300)
            fig.suptitle(f'Curve extracted values: {title}')
            figs_extracted.append(fig)

    header = '%s: %s %s: %s' % (
        translate('Name'),
        fullname,
        translate('Social security number'),
        hetu,
    )
    logger.debug(f'creating multipage comparison pdf {pdfpath}')
    with PdfPages(pdfpath) as pdf:
        _savefig(pdf, fig_title)
        _savefig(pdf, fig_timedist, header)
        _savefig(pdf, fig_kinematics, header)
        _savefig(pdf, fig_kinetics, header)
        _savefig(pdf, fig_musclelen, header)
        _savefig(pdf, fig_emg, header)
        for fig in figs_extracted:
            _savefig(pdf, fig, header)

    # save the curve extraced values into a text file
    if write_extracted:
        extracted_txt = '\n'.join(_curve_extracted_text(curve_vals, vardefs_dict))
        extracted_txt_file = ' VS '.join(sp.name for sp in sessionpaths)
        extracted_txt_file += '_curve_values.txt'
        extracted_txt_path = destdir / extracted_txt_file
        with io.open(extracted_txt_path, 'w', encoding='utf8') as f:
            logger.debug(f'writing extracted text data into {extracted_txt_path}')
            f.write(extracted_txt)

    return f'Created {pdfname}\nin {sessionpath}'
