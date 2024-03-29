# -*- coding: utf-8 -*-
"""
Reporting in text format.

@author: Jussi (jnu@iki.fi)
"""


import logging
import numpy as np
from pathlib import Path

from .translations import translate
from .. import utils, sessionutils
from ..config import cfg
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
    # width of the data columns containing the data
    COL_WIDTH = 20
    # we use right/left for textual data (consistency with patient system)
    contexts = utils.get_contexts(right_first=True)
    # write out main title
    is_comparison = len(curve_vals) > 1
    sessions_str = ' vs. '.join(curve_vals.keys())
    yield f'\nCurve extracted values for {sessions_str}'
    # write the pages
    for title, vardefs in vardefs_dict.items():
        # the page title
        yield f'\n\n{title}'
        yield '-' * len(title)  # underline
        rowtitle_len = max(len(_compose_varname(vardef)) for vardef in vardefs) + 5
        for session, session_vals in curve_vals.items():
            # session header (only for multiple sessions)
            if is_comparison:
                yield f'\n{session}:'
            # context header
            hdr = ' ' * rowtitle_len
            hdr += ''.join(ctxt_name.ljust(COL_WIDTH) for _, ctxt_name in contexts)
            yield hdr
            for vardef in vardefs:
                # output rows consisting of variable description followed by the R/L values
                row = _compose_varname(vardef).ljust(rowtitle_len)
                for ctxt, _ in contexts:
                    vardef_ctxt = [ctxt + vardef[0]] + vardef[1:]
                    if vardef_ctxt[0] not in session_vals:
                        logger.debug(
                            f'{vardef_ctxt[0]} was not collected for this session'
                        )
                        continue
                    this_vals = _nested_get(session_vals, vardef_ctxt)
                    mean, std = np.mean(this_vals), np.std(this_vals)
                    unit = _var_unit(vardef_ctxt)
                    if unit == 'deg':
                        unit = '\u00B0'  # Unicode degree sign
                    else:
                        unit = ' ' + unit
                    element = f'{mean:.2f}±{std:.2f}{unit}'
                    row += element.ljust(COL_WIDTH)
                yield row


def _print_analysis_text(trials, vars_=None, main_label=None):
    """Print time-distance variables as text"""
    COL_WIDTH = 25  # width of the columns containing the data
    contexts = utils.get_contexts(right_first=True)
    if vars_ is None:
        vars_ = _timedist_vars
    res_avg_all, res_std_all = _group_analysis_trials(trials)
    hdr = f"\n{translate('Time-distance variables')}\n"
    hdr += '-' * len(hdr)
    hdr += f'\n\n{main_label}:' if main_label else '\n\n'
    yield hdr
    for cond, cond_data in res_avg_all.items():
        varnames_trans = [translate(varname) for varname in vars_]
        rowtitle_len = max(len(varname) for varname in varnames_trans) + 5
        hdr = ' ' * rowtitle_len
        hdr += ''.join(
            translate(ctxt_name).ljust(COL_WIDTH) for _, ctxt_name in contexts
        )
        yield hdr
        for varname, varname_trans in zip(vars_, varnames_trans):
            val = cond_data[varname]
            val_std = res_std_all[cond][varname]
            unit = translate(val['unit'])
            li = ''
            li += varname_trans.ljust(rowtitle_len)
            for _, ctxt_name in contexts:
                element = f'{val[ctxt_name]:.2f}±{val_std[ctxt_name]:.2f} {unit}'
                li += element.ljust(COL_WIDTH)
            yield li
    yield ''


def _session_analysis_text(sessionpath):
    """Return session time-distance vars as text"""
    sessionpath = Path(sessionpath)
    sessiondir = sessionpath.name
    tagged_trials = sessionutils.get_c3ds(
        sessionpath, tags=cfg.eclipse.tags, trial_type='dynamic'
    )
    return '\n'.join(
        _print_analysis_text({sessiondir: tagged_trials}, main_label=sessiondir)
    )
