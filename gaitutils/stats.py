# -*- coding: utf-8 -*-
"""
Compute statistics across/within trials


@author: Jussi (jnu@iki.fi)
"""

import logging
import numpy as np
from collections import defaultdict

from .trial import Trial, Gaitcycle
from . import models, GaitDataError

logger = logging.getLogger(__name__)


class AvgTrial(Trial):
    """ Trial containing cycle-averaged data, for use with plotter
    TODO: does not support legends yet """

    def __init__(self, c3dfiles, fp_cycles_only=False, max_dist=None):
        avgdata, stddata, n_ok, _ = average_trials(c3dfiles, max_dist=max_dist,
                                                   fp_cycles_only=fp_cycles_only)
        # nfiles may be misleading since not all trials may contain valid data
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
        self.cycles.append(Gaitcycle(0, 101, 60, 'R', True, 1, 1000,
                                     name='Right average', trial=self))
        self.cycles.append(Gaitcycle(0, 101, 60, 'L', True, 1, 1000,
                                     name='Left average', trial=self))
        self.ncycles = 2
        self.sessionpath = None
        self.sessiondir = None
        self.eclipse_data = defaultdict(lambda: '', {})
        self.emg = None

    def get_model_data(self, var):
        return self.t, self._model_data[var]

    def set_norm_cycle(self, cycle=None):
        if cycle is None:
            raise ValueError('AvgTrial does not support unnormalized data')
        else:
            logger.debug('setting norm. cycle for AvgTrial (no effect)')


def average_trials(trials, max_dist=None, fp_cycles_only=False,
                   reject_zeros=True):
    """ Average model data from several trials.

    trials: list
        filename, or list of filenames (c3d) to read trials from, or list
        of Trial instances
    max_dist: maximum curve distance from median, for outlier rejection
    fp_cycles_only: bool
        If True, only collect data from forceplate cycles. Kinetics will always
        be collected from forceplate cycles only.

    Returns:

    avgdata: dict
        The data
    stddata: dict
        Standard dev for each var
    N_ok: dict
        N of accepted cycles for each var
    Ncyc: dict
        WIP
    """
    data, Ncyc = _collect_model_data(trials, fp_cycles_only=fp_cycles_only)

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

            # drop outliers
            if max_dist is not None:
                outliers = _outlier_rows(vardata, max_dist)
                N_out = np.count_nonzero(outliers)
                if N_out > 0:
                    logger.debug('%s: dropping %d outlier curves' %
                                 (var, N_out))
                    vardata = vardata[~outliers, :] if N_out else vardata

            # drop curves containing zero values
            if reject_zeros:
                rows_bad = np.where(np.any(vardata == 0, axis=1))[0]
                if len(rows_bad) > 0:
                    logger.debug('%s: dropping %d curves with zero output' %
                                 (var, len(rows_bad)))
                    vardata = np.delete(vardata, rows_bad, axis=0)

            n_ok = vardata.shape[0]
            stddata[var] = vardata.std(axis=0) if n_ok > 0 else None
            avgdata[var] = vardata.mean(axis=0) if n_ok > 0 else None

            logger.debug('%s: averaged %d/%d curves' % (var, n_ok, Ntot))
            N_ok[var] = n_ok

    if not avgdata:
        logger.warning('nothing averaged')
    return (avgdata, stddata, N_ok, Ncyc)


def _outlier_rows(A, max_dist):
    """ Find outlier rows from A, defined as max distance from median row """
    med = np.median(A, axis=0)
    return (np.abs(A-med)).max(axis=1) > max_dist


def _collect_model_data(trials, fp_cycles_only=False):
    """ Collect given model data across trials and cycles.
    Returns a dict of numpy arrays keyed by variable.

    trials: list
        filename, or list of filenames (c3d) to read trials from, or list
        of Trial instances
    fp_cycles_only: bool
        If True, only collect data from forceplate cycles. Kinetics will always
        be collected from forceplate cycles only.
    """

    if not trials:
        logger.debug('no trials')
        return
    if not isinstance(trials, list):
        trials = [trials]

    data_all = dict()

    for model in models.models_all:
        for var in model.varnames:
            data_all[var] = None

    nc = dict()
    nc['R'], nc['L'], nc['Rkin'], nc['Lkin'] = (0,)*4

    for n, trial_ in enumerate(trials):
        # see whether it's already a Trial instance or we need to create one
        if isinstance(trial_, Trial):
            trial = trial_
        else:
            try:
                trial = Trial(trial_)
            except GaitDataError:
                logger.warning('cannot load %s' % trial_)

        logger.debug('collecting data for %s' % trial.trialname)

        # see which models are included in trial
        models_ok = list()
        for model in models.models_all:
            var = model.varnames[0]
            try:
                data = trial.get_model_data(var)[1]
                models_ok.append(model)
            except GaitDataError:
                logger.debug('cannot read variable %s from %s, skipping '
                             'corresponding model %s' % (var, trial.trialname,
                                                         model.desc))
        for model in models_ok:
            # gather data
            for cycle in trial.cycles:
                trial.set_norm_cycle(cycle)
                side = cycle.context
                if cycle.on_forceplate:
                    nc[side+'kin'] += 1
                nc[side] += 1

                for var in model.varnames:
                    # pick data only if var context matches cycle context
                    # FIXME: this may not work with all models
                    if var[0] == side:
                        # don't collect kinetics if cycle is not on forceplate
                        if ((model.is_kinetic_var(var) or fp_cycles_only) and
                           not cycle.on_forceplate):
                                continue
                        data = trial.get_model_data(var)[1]
                        # add as first row or concatenate to existing data
                        data_all[var] = (data[None, :] if data_all[var]
                                         is None else
                                         np.concatenate([data_all[var],
                                                        data[None, :]]))

    n = len(trials)
    logger.debug('collected %d trials, %d/%d R/L cycles, %d/%d kinetics cycles'
                 % (n, nc['R'], nc['L'], nc['Rkin'], nc['Lkin']))

    return data_all, nc
