# -*- coding: utf-8 -*-
"""
Compute statistics across/within trials


@author: Jussi (jnu@iki.fi)
"""

import logging
import numpy as np
import scipy
import os.path as op
from collections import defaultdict

from .trial import Trial, Gaitcycle
from . import models, GaitDataError, cfg, numutils


logger = logging.getLogger(__name__)


def create_avgtrial(
    trials, reject_zeros=True, reject_outliers=None, fp_cycles_only=False
):
    """Build an AvgTrial from list of trials."""

    avgdata, stddata, n_ok, _ = average_trials(
        trials, reject_outliers=reject_outliers, fp_cycles_only=fp_cycles_only
    )


class AvgTrial(Trial):
    def __repr__(self):
        s = '<AvgTrial |'
        s += ' trial name: %s' % self.trialname
        s += ', trials: %s' % self.source
        s += '>'
        return s

    def __init__(self, avgdata, stddata, sessionpath=None):
        if sessionpath:
            self.sessionpath = sessionpath
            self.sessiondir = op.split(sessionpath)[-1]
            self.trialname = '%s avg.' % self.sessiondir
        else:
            self.trialname = '%d trial avg.' % self.nfiles
            self.sessiondir = None
            self.sessionpath = None
        self.source = 'averaged data'
        self.name = 'Unknown'
        self.is_static = False
        self._model_data = avgdata
        self.stddev_data = stddata
        self.n_ok = n_ok
        self.t = np.arange(101)  # data is on normalized cycle 0..100%
        # fake 2 gait cycles, L/R
        self.cycles = list()
        self.cycles.append(
            Gaitcycle(0, 101, 60, 'R', True, 1, 1000, name='right', trial=self)
        )
        self.cycles.append(
            Gaitcycle(0, 101, 60, 'L', True, 1, 1000, name='left', trial=self)
        )
        self.ncycles = 2
        self.eclipse_data = defaultdict(lambda: '', {})

    @property
    def emg(self):
        # FIXME: could average EMG RMS
        raise GaitDataError('EMG averaging not supported yet')

    def get_model_data(self, var):
        return self.t, self._model_data[var]

    def set_norm_cycle(self, cycle=None):
        if cycle is None:
            raise ValueError('AvgTrial does not support unnormalized data')
        else:
            logger.debug('setting norm. cycle for AvgTrial (no effect)')


def _robust_reject_rows(data, p_threshold):
    """Reject rows (observations) from data"""
    # a Bonferroni type correction for the p-threshold
    p_threshold_corr = p_threshold / data.shape[0]
    # when computing outliers, estimate median absolute deviation
    # using all data, instead of a frame-dependent MAD estimate.
    # this is necessary since frame-based MAD values
    # can become really small especially in small datasets, causing
    # Z-score to blow up and data getting rejected unnecessarily.
    outlier_inds = numutils.outliers(
        data, median_axis=0, mad_axis=None, p_threshold=p_threshold_corr
    )
    outlier_rows = np.unique(outlier_inds[0])
    if outlier_rows.size > 0:
        logger.info(
            'rejected %d outlier(s) (corrected P=%g)'
            % (outlier_rows.size, p_threshold_corr)
        )
        data = np.delete(data, outlier_rows, axis=0)
    return data


def average_analog_data(
    data,
    rms=True,    
    reject_outliers=None,
    use_medians=False,
):
    """Average collected EMG data.

    Parameters
    ----------
    data : dict
        Data to average (from collect_trial_data)
    rms : bool
        Compute RMS before averaging.
    reject_outliers : float or None
        None for no automatic outlier rejection. Otherwise, a P value for false
        rejection (assuming strictly normally distributed data). Outliers are
        rejected based on robust statistics (modified Z-score).
    use_medians: bool
        Use median and MAD (median absolute deviation) instead of mean and
        stddev. The median is robust to outliers but not robust to small
        sample size. Thus, use of medians may be a bad idea for small samples.

    Returns
    -------
    avgdata : dict
        Averaged (or median) data as numpy array for each variable.
    stddata : dict
        Standard dev (or MAD) as numpy array for each variable.
    ncycles_ok : dict
        N of accepted cycles for each variable.
    """
    stddata = dict()
    avgdata = dict()
    ncycles_ok = dict()

    if reject_outliers is None:
        reject_outliers = 1e-3

    for var, vardata in data.items():
        if vardata is None:
            stddata[var] = None
            avgdata[var] = None
            ncycles_ok[var] = 0
            continue
        else:
            if rms:
                vardata = numutils.rms(vardata, cfg.emg.rms_win, axis=1)
            n_ok = vardata.shape[0]
            if n_ok > 0 and reject_outliers is not None and not use_medians:
                rms_status = 'RMS for ' if rms else ''
                logger.info('averaging %s%s (N=%d)' % (rms_status, var, n_ok))
                vardata = _robust_reject_rows(vardata, reject_outliers)
            n_ok = vardata.shape[0]
            if n_ok == 0:
                stddata[var] = None
                avgdata[var] = None
            elif use_medians:
                stddata[var] = numutils.mad(vardata, axis=0)
                avgdata[var] = np.median(vardata, axis=0)
            else:
                stddata[var] = vardata.std(axis=0) if n_ok > 0 else None
                avgdata[var] = vardata.mean(axis=0) if n_ok > 0 else None
            ncycles_ok[var] = n_ok

    if not avgdata:
        logger.warning('nothing averaged')
    return (avgdata, stddata, ncycles_ok)


def average_model_data(
    data,
    reject_zeros=True,
    reject_outliers=None,
    use_medians=False,
):
    """Average collected model data.

    Parameters
    ----------
    data : dict
        Data to average (from collect_trial_data)
    reject_zeros : bool
        Reject any curves which contain zero values. Exact zero values are
        commonly used to mark gaps. No zero rejection is done for kinetic vars,
        since these may become zero due to clamping of force data.
    reject_outliers : float or None
        None for no automatic outlier rejection. Otherwise, a P value for false
        rejection (assuming strictly normally distributed data). Outliers are
        rejected based on robust statistics (modified Z-score).
    use_medians: bool
        Use median and MAD (median absolute deviation) instead of mean and
        stddev. The median is robust to outliers but not robust to small
        sample size. Thus, use of medians may be a bad idea for small samples.

    Returns
    -------
    avgdata : dict
        Averaged (or median) data as numpy array for each variable.
    stddata : dict
        Standard dev (or MAD) as numpy array for each variable.
    ncycles_ok : dict
        N of accepted cycles for each variable.
    """
    stddata = dict()
    avgdata = dict()
    ncycles_ok = dict()

    if reject_outliers is None:
        reject_outliers = 1e-3

    for var, vardata in data.items():
        if vardata is None:
            stddata[var] = None
            avgdata[var] = None
            ncycles_ok[var] = 0
            continue
        else:
            Ntot = vardata.shape[0]
            if reject_zeros:
                this_model = models.model_from_var(var)
                if not this_model.is_kinetic_var(var):
                    rows_bad = np.where(np.any(vardata == 0, axis=1))[0]
                    if len(rows_bad) > 0:
                        logger.info(
                            '%s: rejecting %d curves with zero values'
                            % (var, len(rows_bad))
                        )
                        vardata = np.delete(vardata, rows_bad, axis=0)
            n_ok = vardata.shape[0]
            if n_ok > 0 and reject_outliers is not None and not use_medians:
                logger.info('%s:' % var)
                vardata = _robust_reject_rows(vardata, reject_outliers)
            n_ok = vardata.shape[0]
            if n_ok == 0:
                stddata[var] = None
                avgdata[var] = None
            elif use_medians:
                stddata[var] = numutils.mad(vardata, axis=0)
                avgdata[var] = np.median(vardata, axis=0)
            else:
                stddata[var] = vardata.std(axis=0) if n_ok > 0 else None
                avgdata[var] = vardata.mean(axis=0) if n_ok > 0 else None
            logger.debug('%s: averaged %d/%d curves' % (var, n_ok, Ntot))
            ncycles_ok[var] = n_ok

    if not avgdata:
        logger.warning('nothing averaged')
    return (avgdata, stddata, ncycles_ok)


def collect_trial_data(
    trials, collect_types=None, fp_cycles_only=False, analog_len=None
):
    """Read model and analog data across trials into numpy arrays.

    Parameters
    ----------
    trials : list | str
        filename, or list of filenames (c3d) to collect data from, or list
        of Trial instances
    collect_types : dict
        Which kind of vars to collect. Currently supported keys: 'model', 'emg'. Default is to
        collect all supported types.
    fp_cycles_only : bool
        If True, only collect data from forceplate cycles. Kinetics model vars will always
        be collected from forceplate cycles only.
    analog_len : int
        Analog data length varies by gait cycle, so it will be resampled into grid length
        specified by analog_len (default 501 samples)

    Returns
    -------
    data_all : dict
        dict keyed by variable type. Each value is a dict keyed by variable, whose values are numpy arrays of data.
    ncycles : dict
        Total number of collected cycles for 'R', 'L', 'R_fp', 'L_fp'
        (last two are for forceplate cycles)
    """
    data_all = dict()
    ncycles = defaultdict(lambda: 0)

    if collect_types is None:
        collect_types = defaultdict(lambda: True)

    if analog_len is None:
        analog_len = 501

    if not trials:
        logger.warning('no trials')
        return None, None
    if not isinstance(trials, list):
        trials = [trials]

    if collect_types['emg']:
        data_all['emg'] = defaultdict(lambda: None)
        emg_chs_to_collect = cfg.emg.channel_labels.keys()
    else:
        emg_chs_to_collect = list()

    if collect_types['model']:
        data_all['model'] = defaultdict(lambda: None)
        models_to_collect = models.models_all
    else:
        models_to_collect = list()

    for trial_ in trials:
        trial = trial_ if isinstance(trial_, Trial) else Trial(trial_)
        logger.info('collecting data for %s' % trial.trialname)

        for cycle in trial.cycles:
            trial.set_norm_cycle(cycle)
            context = cycle.context
            if cycle.on_forceplate:
                ncycles[context + '_fp'] += 1
                ncycles[context] += 1
            elif not fp_cycles_only:
                ncycles[context] += 1

            # collect model data
            for model in models_to_collect:
                for var in model.varnames:
                    # pick data only if var context matches cycle context
                    # FIXME: should implement context() for models
                    if var[0] != context:
                        continue
                    # don't collect kinetics if cycle is not on forceplate
                    if (
                        model.is_kinetic_var(var) or fp_cycles_only
                    ) and not cycle.on_forceplate:
                        continue
                    _, data = trial.get_model_data(var)
                    if np.all(np.isnan(data)):
                        logger.debug('no data for %s/%s' % (trial.trialname, var))
                    else:
                        # add as first row or concatenate to existing data
                        data_all['model'][var] = (
                            data[None, :]
                            if data_all['model'][var] is None
                            else np.concatenate([data_all['model'][var], data[None, :]])
                        )

            for ch in emg_chs_to_collect:
                # check whether cycle matches channel context
                if not trial.emg.context_ok(ch, cycle.context):
                    continue
                # get data on analog sampling grid and compute rms
                try:
                    t, data = trial.get_emg_data(ch)
                except KeyError:
                    logger.warning('no channel %s for %s' % (ch, trial))
                    continue
                data_cyc = scipy.signal.resample(data, analog_len)
                if ch not in data_all['emg']:
                    data_all['emg'][ch] = data_cyc[None, :]
                else:
                    data_all['emg'][ch] = np.concatenate([data_all['emg'][ch], data_cyc[None, :]])

    logger.debug(
        'collected %d trials, %d/%d R/L cycles, %d/%d forceplate cycles'
        % (len(trials), ncycles['R'], ncycles['L'], ncycles['R_fp'], ncycles['L_fp'])
    )
    return data_all, ncycles

