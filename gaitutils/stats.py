# -*- coding: utf-8 -*-
"""
Compute statistics across/within trials


@author: Jussi (jnu@iki.fi)
"""

from trial import Trial
from envutils import GaitDataError
import logging
import numpy as np

logger = logging.getLogger(__name__)


def average_trials(trials, models):
    """ Average model data from several trials.

    trials: list
        filename, or list of filenames (c3d) to read trials from
    models: model (GaitModel instance) or list of models to average
    """
    data, Ncyc = _collect_model_data(trials, models)

    stddata = dict()
    avgdata = dict()
    for var in data:
        stddata[var] = data[var].std(axis=0)
        avgdata[var] = data[var].mean(axis=0)
        
    return (avgdata, stddata, Ncyc)


def _collect_model_data(trials, models):
    """ Collect given model data across trials and cycles.
    Returns a dict of numpy arrays keyed by variable.

    trials: list
        filename, or list of filenames (c3d) to read trials from
    models: model (GaitModel instance) or list of models to average
    """
    if not trials:
        logger.debug('no trials')
        return
    if not isinstance(trials, list):
        trials = [trials]
    if not isinstance(models, list):
        models = [models]

    data_all = dict()
    nc = dict()
    nc['R'], nc['L'], nc['Rkin'], nc['Lkin'] = (0,)*4

    for n, file in enumerate(trials):
        try:
            tr = Trial(file)
        except GaitDataError:
            logger.warning('cannot load %s for averaging' % file)
        models_ok = True
        for model in models:
            # test whether read is ok for all models (only test 1st var)
            var = model.varnames[0]
            try:
                data = tr[var][1]
            except GaitDataError:
                logger.warning('cannot read variable %s from %s' %
                              (var, file))
                models_ok = False
        if not models_ok:
            continue
        for cycle in tr.cycles:
            tr.set_norm_cycle(cycle)
            side = cycle.context
            if cycle.on_forceplate:
                nc[side+'kin'] += 1
            nc[side] += 1
            for model in models:
                for var in model.varnames:
                    # pick data only if var context matches cycle context
                    if var[0] == side:
                        # don't collect kinetics data if cycle not on forceplate
                        if model.is_kinetic_var(var) and not cycle.on_forceplate:
                            continue
                        data = tr[var][1]
                        data_all[var] = (data[None, :] if var not in data_all
                                         else
                                         np.concatenate([data_all[var],
                                                        data[None, :]]))
    logger.debug('averaged %d trials, %d/%d R/L cycles, %d/%d kinetics cycles'
                 % (n, nc['R'], nc['L'], nc['Rkin'], nc['Lkin']))
    return data_all, nc
        
        
        
        