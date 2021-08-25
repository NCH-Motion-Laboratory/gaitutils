#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Time-distance computations

@author: Jussi (jnu@iki.fi)
"""

import logging
import numpy as np
from collections import defaultdict

from .envutils import GaitDataError
from . import c3d

logger = logging.getLogger(__name__)


def group_analysis(an_list, fun=np.mean):
    """Apply function (e.g. mean or stddev) to analysis dicts.

    Parameters
    ----------
    an_list : list
        List of analysis dicts returned by read_data.get_analysis(). All dicts
        must have the same condition label.
    fun : function
        The reducing function to apply, by default np.mean. This must accept a
        1-D ndarray of values and return a single value. Examples of useful
        functions would be np.mean, np.std and np.median.

    Returns
    -------
    dict
        The resulting analysis dict after the reducing function has been
        applied. The condition label is identical with the input dicts.
    """

    if not isinstance(an_list, list):
        raise TypeError('Need a list of analysis dicts')
    if not an_list:
        return None

    # check conditions
    condsets = [set(an.keys()) for an in an_list]
    conds = condsets[0]
    if not all(cset == conds for cset in condsets):
        raise RuntimeError('Conditions need to match between analysis dicts')

    # figure out variables that are in all of the analysis dicts
    for cond in conds:
        varsets = [set(an[cond].keys()) for an in an_list for cond in conds]
    vars_ = set.intersection(*varsets)
    not_in_all = set.union(*varsets) - vars_
    if not_in_all:
        logger.warning(
            'Some analysis dicts are missing the following variables: %s'
            % ', '.join(not_in_all)
        )

    # gather data and apply function
    res = defaultdict(lambda: defaultdict(dict))
    for cond in conds:
        for var in vars_:
            # this will fail if vars are not strictly matched between dicts
            res[cond][var]['unit'] = an_list[0][cond][var]['unit']
            for context in ['Right', 'Left']:
                # gather valus from analysis dicts
                allvals = np.array(
                    [
                        an[cond][var][context]
                        for an in an_list
                        if context in an[cond][var]
                    ]
                )
                # filter out missing values (nans)
                allvals = allvals[~np.isnan(allvals)]
                res[cond][var][context] = fun(allvals) if allvals.size else np.nan
    return res


def _group_analysis_trials(trials):
    """Multitrial analysis from given trials (.c3d files).
    trials: dict of lists keyed by condition name
    If there are multiple trials per condition, they will be averaged.
    """
    res_avg_all = dict()  # preserve condition ordering
    res_std_all = dict()  # for plots etc.
    for cond_label, cond_files in trials.items():
        ans = list()
        for c3dfile in cond_files:
            try:
                an = c3d.get_analysis(c3dfile, condition=cond_label)
                ans.append(an)
            except GaitDataError:
                logger.warning(f'no analysis values found in {c3dfile}')
        if ans:
            res_avg = group_analysis(ans)
            res_std = group_analysis(ans, fun=np.std)
            res_avg_all.update(res_avg)
            res_std_all.update(res_std)
    return res_avg_all, res_std_all


def _pick_common_vars(values, vars_wanted=None):
    """Helper to pick analysis vars data that exist for
    all conditions. Returns vars and corresponding units"""
    conds = list(values.keys())
    if not conds:
        raise GaitDataError('no analysis values')
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
                f'some conditions are missing variables: {vars_wanted_set - vars_ok}'
            )
        # preserve original var order
        vars_ = [var for var in vars_wanted if var in vars_ok]
    else:
        vars_ = list(vars_common)
    units = [vals_1[var]['unit'] for var in vars_]
    return conds, vars_, units
