# -*- coding: utf-8 -*-
"""
Compute statistics across/within trials


@author: Jussi (jnu@iki.fi)
"""

import logging
import numpy as np

from .trial import Trial, Gaitcycle
from .envutils import GaitDataError


logger = logging.getLogger(__name__)


class AvgTrial(Trial):
    """ Trial containing cycle-averaged data, for use with plotter
    TODO: does not support legends yet """

    def __init__(self, c3dfiles, models):
        avgdata, stddata, n_ok, _ = average_trials(c3dfiles, models)
        self.nfiles = len(c3dfiles)
        self.trialname = 'Averages from %d trials' % self.nfiles
        self.source = 'averaged data'
        self.name = 'Unknown'
        self._model_data = avgdata
        self.stddev_data = stddata
        self.n_ok = n_ok
        self.t = np.arange(101)  # 0..100%
        # fake 2 gait cycles, L/R
        self.cycles = list()
        self.cycles.append(Gaitcycle(0, 101, 1, 60, 'R', True, 1000))
        self.cycles.append(Gaitcycle(0, 101, 1, 60, 'L', True, 1000))
        self.ncycles = 2

    def __getitem__(self, item):
        return self.t, self._model_data[item]

    def set_norm_cycle(self, cycle):
        if cycle is None:
            raise ValueError('AvgTrial does not support unnormalized data')
        else:
            logger.debug('setting norm. cycle for AvgTrial (no effect)')


def average_trials(trials, models, max_dist=None):
    """ Average model data from several trials.

    trials: list
        filename, or list of filenames (c3d) to read trials from
    models: model (GaitModel instance) or list of models to average
    max_dist: maximum curve distance from median, for outlier rejection

    Returns:

    avgdata: dict
        The data
    stddata: dict
        Standard dev for each var
    N_ok: dict
        N of accepted trials for each var
    Ncyc: dict
        WIP
    """
    data, Ncyc = _collect_model_data(trials, models)

    stddata = dict()
    avgdata = dict()
    N_ok = dict()

    for var, vardata in data.items():
        if vardata is None:
            stddata[var] = None
            avgdata[var] = None
            N_ok[var] = 0
            continue
        else:
            Ntot = vardata.shape[0]
            # identify outliers
            if max_dist is not None:
                outliers = _outlier_rows(vardata, max_dist)
                N_out = np.count_nonzero(outliers)
                if N_out > 0:
                    logger.debug('%s: dropping %d outlier curves' %
                                 (var, N_out))
                    vardata = vardata[~outliers, :] if N_out else vardata
            stddata[var] = vardata.std(axis=0)
            avgdata[var] = vardata.mean(axis=0)
            n_ok = vardata.shape[0]
            logger.debug('%s: averaged %d/%d curves' % (var, n_ok, Ntot))
            N_ok[var] = n_ok

    return (avgdata, stddata, N_ok, Ncyc)


def _outlier_rows(A, max_dist):
    """ Find outlier rows from A, defined as max distance from median row """
    med = np.median(A, axis=0)
    return (np.abs(A-med)).max(axis=1) > max_dist


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
    for model in models:
        for var in model.varnames:
            data_all[var] = None
    nc = dict()
    nc['R'], nc['L'], nc['Rkin'], nc['Lkin'] = (0,)*4

    for n, file in enumerate(trials):
        try:
            tr = Trial(file)
        except GaitDataError:
            logger.warning('cannot load %s' % file)
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
                        data_all[var] = (data[None, :] if data_all[var] is None
                                         else
                                         np.concatenate([data_all[var],
                                                        data[None, :]]))
    logger.debug('collected %d trials, %d/%d R/L cycles, %d/%d kinetics cycles'
                 % (n, nc['R'], nc['L'], nc['Rkin'], nc['Lkin']))
    return data_all, nc
