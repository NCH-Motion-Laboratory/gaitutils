#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Various time-distance statistics plots
Currently matplotlib only

@author: Jussi (jnu@iki.fi)
"""

import logging
import os.path as op
import numpy as np
from collections import OrderedDict

from .. import analysis, GaitDataError, sessionutils, cfg
from .plot_misc import get_backend

logger = logging.getLogger(__name__)


# XXX: hardcoded time-distance variables, to set a certain order
_timedist_vars = ['Walking Speed', 'Cadence', 'Foot Off', 'Opposite Foot Off',
                  'Opposite Foot Contact', 'Double Support', 'Single Support',
                  'Stride Time', 'Stride Length', 'Step Width', 'Step Length']


def _print_analysis_table(trials):
    """Print analysis vars as text table"""
    res_avg_all, res_std_all = _multitrial_analysis(trials)
    hdr = '%-25s%-9s%-9s\n' % ('Variable', 'Right', 'Left')
    yield hdr
    for cond, cond_data in res_avg_all.items():
        for var, val in cond_data.items():
            li = '%-25s%-9.2f%-9.2f%s' % (var, val['Right'], val['Left'], val['unit'])
            yield li


def _print_analysis_text(trials, main_label=None):
    """Print analysis vars as text"""
    res_avg_all, res_std_all = _multitrial_analysis(trials)
    hdr = 'Time-distance variables (R/L)'
    hdr += ' for %s:\n' % main_label if main_label else ':\n'
    yield hdr
    for cond, cond_data in res_avg_all.items():
        for var, val in cond_data.items():
            li = u'%s: %.2f/%.2f %s' % (var, val['Right'], val['Left'], val['unit'])
            yield li
    yield ''


def _print_analysis_text_finnish(trials, vars_=None, main_label=None):
    """Print analysis vars_ as Finnish text"""
    if vars_ is None:
        vars_ = _timedist_vars
    res_avg_all, res_std_all = _multitrial_analysis(trials)
    hdr = 'Matka-aikamuuttujat (O/V)'
    hdr += ' (%s):\n' % main_label if main_label else ':\n'
    yield hdr
    translations = {'Single Support': u'Yksöistukivaihe',
                    'Double Support': u'Kaksoistukivaihe',
                    'Opposite Foot Contact': u'Vastakkaisen jalan kontakti',
                    'Opposite Foot Off': u'Vastakkainen jalka irti',
                    'Limp Index': u'Limp-indeksi',
                    'Step Length': u'Askelpituus',
                    'Foot Off': u'Tukivaiheen kesto',
                    'Walking Speed': u'Kävelynopeus',
                    'Stride Length': u'Askelsyklin pituus',
                    'Step Width': u'Askelleveys',
                    'Step Time': u'Askeleen kesto',
                    'Cadence': u'Kadenssi',
                    'Stride Time': u'Askelsyklin kesto'}
    unit_translations = {'steps/min': u'askelta/min'}

    for cond, cond_data in res_avg_all.items():
        for var in vars_:
            val = cond_data[var]
            val_std = res_std_all[cond][var]
            var_ = translations[var] if var in translations else var
            unit = val['unit']
            unit_ = unit_translations[unit] if unit in unit_translations else unit
            li = u'%s: %.2f ±%.2f / %.2f ±%.2f %s' % (var_, val['Right'], val_std['Right'],
                                                        val['Left'], val_std['Left'], unit_)
            yield li
    yield ''


def session_analysis_text(sessionpath):
    """Return session time-distance vars as text"""
    sessiondir = op.split(sessionpath)[-1]
    tagged_trials = sessionutils.get_c3ds(sessionpath, tags=cfg.eclipse.tags,
                                          trial_type='dynamic')
    return '\n'.join(_print_analysis_text_finnish({sessiondir: tagged_trials},
                                                  main_label=sessiondir))


def do_session_average_plot(session, tags=None):
    """Find tagged trials from current session dir and plot average"""
    if tags is None:
        tags = cfg.eclipse.tags
    trials = sessionutils.get_c3ds(session, tags=tags,
                                   trial_type='dynamic')
    if not trials:
        raise GaitDataError('No tagged trials found for session %s'
                            % session)
    session_ = op.split(session)[-1]
    fig = _plot_trials({session_: trials}, title='Time-distance average, session %s' % session_)
    return fig


def do_single_trial_plot(c3dfile):
    """Plot a single trial time-distance."""
    c3dpath, c3dfile_ = op.split(c3dfile)
    fig = _plot_trials({c3dfile: [c3dfile]}, title='Time-distance variables, %s' % c3dfile_)
    return fig


def do_multitrial_plot(c3dfiles, show=True):
    """Plot multiple trial comparison time-distance"""
    trials = {op.split(c3d)[-1]: [c3d] for c3d in c3dfiles}
    return _plot_trials(trials)


def do_comparison_plot(sessions, tags=None):
    """Time-dist comparison of multiple sessions. Tagged trials from each
    session will be picked."""
    if tags is None:
        tags = cfg.eclipse.tags
    trials = OrderedDict()

    for session in sessions:
        c3ds = sessionutils.get_c3ds(session, tags=tags, trial_type='dynamic')
        if not c3ds:
            raise ValueError('No tagged trials found in session %s' % session)
        cond_label = op.split(session)[-1]
        trials[cond_label] = c3ds

    return  _plot_trials(trials)


def _multitrial_analysis(trials):
    """Multitrial analysis from given trials (.c3d files).
    trials: dict of lists keyed by condition name
    If there are multiple trials per condition, they will be averaged.
    """
    res_avg_all = OrderedDict()  # preserve condition ordering
    res_std_all = OrderedDict()  # for plots etc.
    for cond_label, cond_files in trials.items():
        ans = [analysis.get_analysis(c3dfile, condition=cond_label)
               for c3dfile in cond_files]
        if len(ans) > 1:  # do average for this condition
            res_avg = analysis.group_analysis(ans)
            res_std = analysis.group_analysis(ans, fun=np.std)
        else:  # do single-trial plot for this condition
            res_avg = ans[0]
            res_std = {cond_label: None}
        res_avg_all.update(res_avg)
        res_std_all.update(res_std)
 
    return res_avg_all, res_std_all


def _plot_trials(trials, plotvars=None, title=None, interactive=True, backend=None):
    """Make a time-distance variable barchart from given trials (.c3d files).
    trials: dict of lists keyed by condition name
    If there are multiple trials per condition, they will be averaged.
    plotvars: variables to plot and their order
    """
    if plotvars is None:
        plotvars = _timedist_vars
    res_avg_all, res_std_all = _multitrial_analysis(trials)
    backend_lib = get_backend(backend)
    return backend_lib.time_dist_barchart(res_avg_all, stddev=res_std_all,
                                          stddev_bars=False, plotvars=plotvars,
                                          title=title)

