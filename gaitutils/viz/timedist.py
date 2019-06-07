#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Various time-distance statistics plots
Currently matplotlib only

@author: Jussi (jnu@iki.fi)
"""

from builtins import zip
from builtins import range
import logging
import os.path as op
import numpy as np
from collections import OrderedDict

from .. import analysis, GaitDataError, sessionutils, cfg
from .plot_matplotlib import time_dist_barchart

logger = logging.getLogger(__name__)


# XXX: hardcoded time-distance variables, to set a certain order
_timedist_vars = ['Walking Speed', 'Cadence', 'Foot Off', 'Opposite Foot Off',
                  'Opposite Foot Contact', 'Double Support', 'Single Support',
                  'Stride Time', 'Stride Length', 'Step Width', 'Step Length']


def _print_analysis_table(trials, cond_labels=None):
    """Print analysis vars as text table"""
    res_avg_all, res_std_all = _multitrial_analysis(trials,
                                                    cond_labels=cond_labels)
    hdr = '%-25s%-9s%-9s\n' % ('Variable', 'Right', 'Left')
    yield hdr
    for cond, cond_data in res_avg_all.items():
        for var, val in cond_data.items():
            li = '%-25s%-9.2f%-9.2f%s' % (var, val['Right'], val['Left'], val['unit'])
            yield li


def _print_analysis_text(trials, cond_labels=None, main_label=None):
    """Print analysis vars as text"""
    res_avg_all, res_std_all = _multitrial_analysis(trials, cond_labels=cond_labels)
    hdr = 'Time-distance variables (R/L)'
    hdr += ' for %s:\n' % main_label if main_label else ':\n'
    yield hdr
    for cond, cond_data in res_avg_all.items():
        for var, val in cond_data.items():
            li = u'%s: %.2f/%.2f %s' % (var, val['Right'], val['Left'], val['unit'])
            yield li
    yield ''


def _print_analysis_text_finnish(trials, cond_labels=None, vars=None,
                                 main_label=None):
    """Print analysis vars as Finnish text"""
    if vars is None:
        vars = _timedist_vars
    res_avg_all, res_std_all = _multitrial_analysis(trials, cond_labels=cond_labels)
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
        for var in vars:
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
    return '\n'.join(_print_analysis_text_finnish([tagged_trials],
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
    fig = _plot_trials([trials])
    session = op.split(session)[-1]
    fig.suptitle('Time-distance average, session %s' % session)
    return fig


def do_single_trial_plot(c3dfile):
    """Plot a single trial time-distance."""
    fig = _plot_trials([[c3dfile]])
    c3dpath, c3dfile_ = op.split(c3dfile)
    fig.suptitle('Time-distance variables, %s' % c3dfile_)
    return fig


def do_multitrial_plot(c3dfiles, show=True):
    """Plot multiple trial comparison time-distance.
    PDF goes into Nexus session dir"""
    cond_labels = [op.split(c3d)[-1] for c3d in c3dfiles]
    return _plot_trials([[c3d] for c3d in c3dfiles], cond_labels)


def do_comparison_plot(sessions, tags=None):
    """Time-dist comparison of multiple sessions. Tagged trials from each
    session will be picked."""
    if tags is None:
        tags = cfg.eclipse.tags
    trials = list()

    for session in sessions:
        c3ds = sessionutils.get_c3ds(session, tags=tags, trial_type='dynamic')
        if not c3ds:
            raise ValueError('No tagged trials found in session %s' % session)
        trials.append(c3ds)

    cond_labels = [op.split(session)[-1] for session in sessions]
    return  _plot_trials(trials, cond_labels)


def _multitrial_analysis(trials, cond_labels=None):
    """Multitrial analysis from given trials (.c3d files).
    trials: list of lists, where inner lists represent conditions
    and list elements represent trials.
    cond_labels: a matching list of condition labels. If not given,
    defaults to 'Condition n' (n=1,2,3...)
    If there are multiple trials per condition, they will be averaged.
    """
    if cond_labels is None:
        cond_labels = ['Condition %d' % k for k in range(len(trials))]
    res_avg_all = OrderedDict()
    res_std_all = OrderedDict()
    for cond_files, cond_label in zip(trials, cond_labels):
        ans = list()
        for c3dfile in cond_files:
            an = analysis.get_analysis(c3dfile, condition=cond_label)
            ans.append(an)
        if len(ans) > 1:  # do average for this condition
            res_avg = analysis.group_analysis(ans)
            res_std = analysis.group_analysis(ans, fun=np.std)
        else:  # do single-trial plot for this condition
            res_avg = ans[0]
            res_std = OrderedDict()
            res_std[cond_label] = None
        res_avg_all.update(res_avg)
        res_std_all.update(res_std)

    return res_avg_all, res_std_all


def _plot_trials(trials, cond_labels=None, plotvars=None, interactive=True):
    """Make a time-distance variable barchart from given trials (.c3d files).
    trials: list of lists, where inner lists represent conditions
    and list elements represent trials.
    If there are multiple trials per condition, they will be averaged.
    cond_labels: a matching list of condition labels
    plotvars: variables to plot and their order
    """
    if plotvars is None:
        plotvars = _timedist_vars
    res_avg_all, res_std_all = _multitrial_analysis(trials,
                                                    cond_labels=cond_labels)
    return time_dist_barchart(res_avg_all, stddev=res_std_all,
                              stddev_bars=False, plotvars=plotvars)

