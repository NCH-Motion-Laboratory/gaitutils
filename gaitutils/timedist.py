#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Time-distance computations

@author: Jussi (jnu@iki.fi)
"""

import logging
import os.path as op
import numpy as np
from collections import OrderedDict

from . import analysis, sessionutils, cfg, GaitDataError, c3d

logger = logging.getLogger(__name__)


# XXX: hardcoded time-distance variables, to set a certain order
_timedist_vars = [
    'Walking Speed',
    'Cadence',
    'Foot Off',
    'Opposite Foot Off',
    'Opposite Foot Contact',
    'Double Support',
    'Single Support',
    'Stride Time',
    'Stride Length',
    'Step Width',
    'Step Length',
]


def _print_analysis_table(trials):
    """Print analysis vars as text table"""
    res_avg_all, _ = _multitrial_analysis(trials)
    hdr = '%-25s%-9s%-9s\n' % ('Variable', 'Right', 'Left')
    yield hdr
    for _, cond_data in res_avg_all.items():
        for var, val in cond_data.items():
            li = '%-25s%-9.2f%-9.2f%s' % (var, val['Right'], val['Left'], val['unit'])
            yield li


def _print_analysis_text(trials, main_label=None):
    """Print analysis vars as text"""
    res_avg_all, _ = _multitrial_analysis(trials)
    hdr = 'Time-distance variables (R/L)'
    hdr += ' for %s:\n' % main_label if main_label else ':\n'
    yield hdr
    for _, cond_data in res_avg_all.items():
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
    translations = {
        'Single Support': u'Yksöistukivaihe',
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
        'Stride Time': u'Askelsyklin kesto',
    }
    unit_translations = {'steps/min': u'askelta/min'}

    for cond, cond_data in res_avg_all.items():
        for var in vars_:
            val = cond_data[var]
            val_std = res_std_all[cond][var]
            var_ = translations[var] if var in translations else var
            unit = val['unit']
            unit_ = unit_translations[unit] if unit in unit_translations else unit
            li = u'%s: %.2f ±%.2f / %.2f ±%.2f %s' % (
                var_,
                val['Right'],
                val_std['Right'],
                val['Left'],
                val_std['Left'],
                unit_,
            )
            yield li
    yield ''


def _session_analysis_text(sessionpath):
    """Return session time-distance vars as text"""
    sessiondir = op.split(sessionpath)[-1]
    tagged_trials = sessionutils.get_c3ds(
        sessionpath, tags=cfg.eclipse.tags, trial_type='dynamic'
    )
    return '\n'.join(
        _print_analysis_text_finnish({sessiondir: tagged_trials}, main_label=sessiondir)
    )


def _multitrial_analysis(trials):
    """Multitrial analysis from given trials (.c3d files).
    trials: dict of lists keyed by condition name
    If there are multiple trials per condition, they will be averaged.
    """
    res_avg_all = OrderedDict()  # preserve condition ordering
    res_std_all = OrderedDict()  # for plots etc.
    for cond_label, cond_files in trials.items():
        ans = list()
        for c3dfile in cond_files:
            try:
                an = c3d.get_analysis(c3dfile, condition=cond_label)
                ans.append(an)
            except GaitDataError:
                logger.warning('no analysis values found in %s' % c3dfile)
        if ans:
            res_avg = analysis.group_analysis(ans)
            res_std = analysis.group_analysis(ans, fun=np.std)
            res_avg_all.update(res_avg)
            res_std_all.update(res_std)
    return res_avg_all, res_std_all


def _pick_common_vars(values, vars_wanted=None):
    """Helper to pick analysis vars data that exist for
    all conditions. Returns vars and corresponding units"""
    conds = list(values.keys())
    vals_1 = values[conds[0]]
    varsets = [set(values[cond].keys()) for cond in conds]
    # vars common to all conditions
    vars_common = set.intersection(*varsets)
    if vars_wanted is not None:
        # pick specified vars that appear in all of the conditions
        vars_wanted_set = set(vars_wanted)
        vars_ok = set.intersection(vars_wanted_set, vars_common)
        if vars_wanted_set - vars_ok:
            logger.warning(
                'some conditions are missing variables: %s'
                % (vars_wanted_set - vars_ok)
            )
        # preserve original var order
        vars = [var for var in vars_wanted if var in vars_ok]
    else:
        vars = vars_common
    units = [vals_1[var]['unit'] for var in vars]
    return conds, vars, units
