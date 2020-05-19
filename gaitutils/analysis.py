# -*- coding: utf-8 -*-
"""
Created on Tue Mar 17 14:41:31 2015

Analysis of time-distance variables

@author: Jussi (jnu@iki.fi)
"""


from __future__ import division
from builtins import zip
import numpy as np
import logging
from collections import defaultdict

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
            % ' '.join(not_in_all)
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


def _step_width(source):
    """Compute step width over trial cycles.
    
    For details of computation, see:
    https://www.vicon.com/faqs/software/how-does-nexus-plug-in-gait-and-polygon-calculate-gait-cycle-parameters-spatial-and-temporal
    Returns context keyed dict of lists.
    FIXME: marker name into params?
    FIXME: this (and similar) may also need to take Trial instance as argument
    to avoid creating new Trials
    """
    from .trial import Trial

    tr = Trial(source)
    sw = dict()
    mkr = 'TOE'  # marker name without context
    mkrdata = tr._full_marker_data
    # FIXME: why not use cycles here?
    for context, strikes in zip(['L', 'R'], [tr.events.lstrikes, tr.events.rstrikes]):
        sw[context] = list()
        nstrikes = len(strikes)
        if nstrikes < 2:
            continue
        # contralateral vars
        context_co = 'L' if context == 'R' else 'R'
        strikes_co = tr.events.lstrikes if context == 'R' else tr.events.rstrikes
        mname = context + mkr
        mname_co = context_co + mkr
        for j, strike in enumerate(strikes):
            if strike == strikes[-1]:  # last strike on this side
                break
            pos_this = mkrdata[mname][strike]
            pos_next = mkrdata[mname][strikes[j + 1]]
            strikes_next_co = [k for k in strikes_co if k > strike]
            if len(strikes_next_co) == 0:  # no subsequent contralateral strike
                break
            pos_next_co = mkrdata[mname_co][strikes_next_co[0]]
            # vector distance between 'step lines' (see url above)
            V1 = pos_next - pos_this
            V1 /= np.linalg.norm(V1)
            VC = pos_next_co - pos_this
            VCP = V1 * np.dot(VC, V1)  # proj to ipsilateral line
            VSW = VCP - VC
            # marker data is in mm, but return step width in m
            sw[context].append(np.linalg.norm(VSW) / 1000.0)
    return sw
