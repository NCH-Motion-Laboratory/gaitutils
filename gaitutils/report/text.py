# -*- coding: utf-8 -*-
"""
Reporting in text format.

@author: Jussi (jnu@iki.fi)
"""

from __future__ import absolute_import

import logging
import numpy as np
import os.path as op

from .. import utils, sessionutils
from ..viz.plot_common import _compose_varname, _nested_get, _var_unit
from ..timedist import _group_analysis_trials

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


def _curve_extracted_text(curve_vals, vardefs_dict):
    """Write out curve extracted values as textual tables.

    Works for single and multiple sessions.
    Yields table rows. Use '\n'.join(_curve_extracted_text(curve_vals, vardefs_dict))
    to create the table.
    """
    # we use right/left for textual data (consistency with patient system)
    contexts = utils.get_contexts(right_first=True)
    # write out main title
    is_comparison = len(curve_vals) > 1
    sessions_str = ' vs. '.join(curve_vals.keys())
    yield '\nCurve extracted values for %s' % sessions_str
    # write the pages
    for title, vardefs in vardefs_dict.items():
        COL_WIDTH = 20  # width of the columns containing the data
        # the page title
        yield '\n\n%s' % title
        yield '-' * len(title)
        rowtitle_len = max(len(_compose_varname(vardef)) for vardef in vardefs) + 5
        for session, session_vals in curve_vals.items():
            # session header (only for multiple sessions)
            if is_comparison:
                yield '\n%s:' % session
            # context header
            hdr = ' ' * rowtitle_len
            hdr += ''.join(ctxt_name.ljust(COL_WIDTH) for _, ctxt_name in contexts)
            yield hdr
            for vardef in vardefs:
                # output rows consisting of variable desc followed by R/L values
                row = _compose_varname(vardef).ljust(rowtitle_len)
                for ctxt, _ in contexts:
                    vardef_ctxt = [ctxt + vardef[0]] + vardef[1:]
                    if vardef_ctxt[0] not in session_vals:
                        logger.debug(
                            '%s was not collected for this session' % vardef_ctxt[0]
                        )
                        continue
                    this_vals = _nested_get(session_vals, vardef_ctxt)
                    mean, std = np.mean(this_vals), np.std(this_vals)
                    unit = _var_unit(vardef_ctxt)
                    if unit == 'deg':
                        unit = u'\u00B0'  # Unicode degree sign
                    else:
                        unit = ' ' + unit
                    element = u'%.2f±%.2f%s' % (mean, std, unit)
                    row += element.ljust(COL_WIDTH)
                yield row


def _print_analysis_table(trials):
    """Print analysis vars as text table"""
    res_avg_all, _ = _group_analysis_trials(trials)
    hdr = '%-25s%-9s%-9s\n' % ('Variable', 'Right', 'Left')
    yield hdr
    for _, cond_data in res_avg_all.items():
        for var, val in cond_data.items():
            li = '%-25s%-9.2f%-9.2f%s' % (var, val['Right'], val['Left'], val['unit'])
            yield li


def _print_analysis_text(trials, main_label=None):
    """Print analysis vars as text"""
    res_avg_all, _ = _group_analysis_trials(trials)
    hdr = 'Time-distance variables (R/L)'
    hdr += ' for %s:\n' % main_label if main_label else ':\n'
    yield hdr
    for _, cond_data in res_avg_all.items():
        for var, val in cond_data.items():
            li = u'%s: %.2f/%.2f %s' % (var, val['Right'], val['Left'], val['unit'])
            yield li
    yield ''


def _print_analysis_text_finnish(trials, vars_=None, main_label=None):
    """Print time-distance variables as Finnish text"""
    COL_WIDTH = 25  # width of the columns containing the data
    contexts = utils.get_contexts(right_first=True)
    contexts_fin = utils.get_contexts(right_first=True, in_finnish=True)
    if vars_ is None:
        vars_ = _timedist_vars
    res_avg_all, res_std_all = _group_analysis_trials(trials)
    hdr = '\nMatka-aikamuuttujat\n'
    hdr += '-' * len(hdr)
    hdr += '\n\n%s:' % main_label if main_label else '\n\n'
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
    unit_translations = {'steps/min': u'1/min'}
    for cond, cond_data in res_avg_all.items():
        rowtitle_len = max(len(translations[var] if var in translations else var) for var in vars_) + 5
        hdr = ' ' * rowtitle_len
        hdr += ''.join(ctxt_name.ljust(COL_WIDTH) for _, ctxt_name in contexts_fin)
        yield hdr
        for var in vars_:
            val = cond_data[var]
            val_std = res_std_all[cond][var]
            var_ = translations[var] if var in translations else var
            unit = val['unit']
            unit_ = unit_translations[unit] if unit in unit_translations else unit
            li = u''
            li += var_.ljust(rowtitle_len)
            for _, ctxt_name in contexts:
                element = u'%.2f±%.2f %s' % (val[ctxt_name], val_std[ctxt_name], unit_)
                li += element.ljust(COL_WIDTH)
            yield li
    yield ''


def _session_analysis_text_finnish(sessionpath):
    """Return session time-distance vars as text"""
    from .. import cfg
    sessiondir = op.split(sessionpath)[-1]
    tagged_trials = sessionutils.get_c3ds(
        sessionpath, tags=cfg.eclipse.tags, trial_type='dynamic'
    )
    return '\n'.join(
        _print_analysis_text_finnish({sessiondir: tagged_trials}, main_label=sessiondir)
    )
