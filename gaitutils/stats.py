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
from . import models, numutils
from .envutils import GaitDataError
from .config import cfg
from .emg import AvgEMG


logger = logging.getLogger(__name__)


class AvgTrial(Trial):
    def __repr__(self):
        s = '<AvgTrial |'
        s += ' trial name: %s' % self.trialname
        s += ', trials: %s' % self.source
        s += '>'
        return s

    @classmethod
    def from_trials(
        cls,
        trials,
        sessionpath=None,
        reject_zeros=None,
        reject_outliers=None,
        use_medians=None,
    ):
        """Build AvgTrial from a list of trials"""
        nfiles = len(trials)
        data_all, ncycles, _ = collect_trial_data(trials)

        avgdata_model, stddata_model, ncycles_ok_analog = average_model_data(
            data_all['model'],
            reject_zeros=reject_zeros,
            reject_outliers=reject_outliers,
            use_medians=use_medians,
        )
        avgdata_emg, stddata_emg, ncycles_ok_emg = average_analog_data(
            data_all['emg'],
            rms=True,
            reject_outliers=reject_outliers,
            use_medians=use_medians,
        )

        return cls(
            avgdata_model=avgdata_model,
            stddata_model=stddata_model,
            avgdata_emg=avgdata_emg,
            stddata_emg=stddata_emg,
            sessionpath=sessionpath,
            nfiles=nfiles,
        )

    def __init__(
        self,
        avgdata_model=None,
        stddata_model=None,
        avgdata_emg=None,
        stddata_emg=None,
        sessionpath=None,
        nfiles=None,
    ):
        if avgdata_model is None and avgdata_emg is None:
            raise ValueError('no data for average')

        if nfiles is None:
            raise ValueError('nfiles must be supplied')

        self.nfiles = nfiles
        if sessionpath:
            self.sessionpath = sessionpath
            self.sessiondir = op.split(sessionpath)[-1]
            self.trialname = '%s avg. (%d trials)' % (self.sessiondir, self.nfiles)
        else:
            self.trialname = '%d trial avg.' % self.nfiles
            self.sessiondir = None
            self.sessionpath = None

        if avgdata_model is None:
            self._model_data = dict()
        else:
            self._model_data = avgdata_model
        self.stddev_data = stddata_model

        if avgdata_emg is None:
            avgdata_emg = dict()
        self.emg = AvgEMG(avgdata_emg)
        analog_npts = 1000  # default
        for ch in list(avgdata_emg.keys()):
            if avgdata_emg[ch] is not None:
                analog_npts = len(avgdata_emg[ch])

        self.tn_analog = np.linspace(0, 100, analog_npts)

        self.source = 'averaged data'
        self.name = 'Unknown'
        self.is_static = False
        # self.n_ok = n_ok  XXX
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
        self._marker_data = dict()

    def get_model_data(self, var, cycle=None):
        """Get averaged model variable.

        Parameters
        ----------
        var : str
            The variable name.
        """
        try:
            data = self._model_data[var]
        except KeyError:
            logger.info('no averaged data for %s, returning nans' % var)
            var_dims = (3, 101)  # is this universal?
            data = np.empty(var_dims)
            data[:] = np.nan
        return self.t, data

    def get_emg_data(self, ch, rms=None, cycle=None):
        """Get averaged EMG RMS data.

        Parameters
        ----------
        ch : str
            The channel name.
        """
        if not rms:
            raise ValueError('AvgTrial only supports EMG in RMS mode')
        return self.tn_analog, self.emg.get_channel_data(ch, rms=True)

    def get_marker_data(self, marker, cycle=None):
        raise GaitDataError('AvgTrial does not average marker data yet')


def _robust_reject_rows(data, p_threshold):
    """Reject rows (observations) from data based on robust Z-score"""
    # a Bonferroni type correction for the p-threshold
    p_threshold_corr = p_threshold / data.shape[1]
    # when computing outliers, estimate median absolute deviation
    # using all data, instead of a frame-based MAD estimates.
    # this is necessary since frame-based MAD values
    # can become really small especially in small datasets, causing
    # the Z-score to blow up and data getting rejected unnecessarily.
    outlier_inds = numutils.outliers(
        data, axis=0, single_mad=False, p_threshold=p_threshold_corr
    )
    outlier_rows = np.unique(outlier_inds[0])
    if outlier_rows.size > 0:
        logger.info(
            'rejected %d outlier(s) (corrected P=%g)'
            % (outlier_rows.size, p_threshold_corr)
        )
        data = np.delete(data, outlier_rows, axis=0)
    return data


def average_analog_data(data, rms=None, reject_outliers=None, use_medians=None):
    """Average collected analog data.

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

    if rms is None:
        rms = False

    if use_medians is None:
        use_medians = False

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
            # do the outlier rejection
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


def average_model_data(data, reject_zeros=None, reject_outliers=None, use_medians=None):
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
        stddev. The median is robust to outliers but not robust to small sample
        size. Thus, use of medians may be a bad idea for small samples.

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

    if use_medians is None:
        use_medians = False

    if reject_zeros is None:
        reject_zeros = True

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
            # do the outlier rejection
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
    trials, collect_types=None, fp_cycles_only=None, analog_len=None
):
    """Read model and analog data across trials into numpy arrays.

    Parameters
    ----------
    trials : list | str
        filename, or list of filenames (c3d) to collect data from, or list
        of Trial instances
    collect_types : dict
        Which kind of vars to collect. Currently supported keys: 'model', 'emg'.
        Default is to collect all supported types.
    fp_cycles_only : bool
        If True, only collect data from forceplate cycles. Kinetics model vars
        will always be collected from forceplate cycles only.
    analog_len : int
        Analog data length varies by gait cycle, so it will be resampled into
        grid length specified by analog_len (default 1000 samples)

    Returns
    -------
    tuple
        Tuple of (data_all, ncycles), where:

            data_all : dict
                Dict keyed by variable type. Each value is a dict keyed by variable,
                whose values are ndarrays of data.
            ncycles : dict
                Total number of collected cycles for 'R', 'L', 'R_fp', 'L_fp' (last two
                are for forceplate cycles)

    """

    data_all = dict()
    toeoff_frames = defaultdict(list)
    ncycles = defaultdict(lambda: 0)

    if fp_cycles_only is None:
        fp_cycles_only = False

    if collect_types is None:
        collect_types = defaultdict(lambda: True)

    if analog_len is None:
        analog_len = 1000  # reasonable default for analog data (?)

    if not trials:
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

    trial_types = list()
    for trial_ in trials:
        # create Trial instance in case we got filenames as args
        trial = trial_ if isinstance(trial_, Trial) else Trial(trial_)
        logger.info('collecting data for %s' % trial.trialname)
        trial_types.append(trial.is_static)
        if any(trial_types) and not all(trial_types):
            raise GaitDataError('Cannot mix dynamic and static trials')

        cycles = [None] if trial.is_static else trial.cycles
        for cycle in cycles:
            if not trial.is_static:
                context = cycle.context
                if cycle.on_forceplate:
                    ncycles[context + '_fp'] += 1
                    ncycles[context] += 1
                elif not fp_cycles_only:
                    ncycles[context] += 1

            # collect model data
            for model in models_to_collect:
                for var in model.varnames:
                    if not trial.is_static:
                        # pick data only if var context matches cycle context
                        # FIXME: should implement context() for models
                        # (and a filter for context?)
                        if var[0] != context:
                            continue
                        # don't collect kinetics if cycle is not on forceplate
                        if (
                            model.is_kinetic_var(var) or fp_cycles_only
                        ) and not cycle.on_forceplate:
                            continue
                    _, data = trial.get_model_data(var, cycle)
                    if np.all(np.isnan(data)):
                        logger.debug('no data for %s/%s' % (trial.trialname, var))
                    else:
                        # add as first row or concatenate to existing data
                        data_all['model'][var] = (
                            data[None, :]
                            if data_all['model'][var] is None
                            else np.concatenate([data_all['model'][var], data[None, :]])
                        )
                        toeoff_frames[var].append(cycle.toeoffn)
            for ch in emg_chs_to_collect:
                # check whether cycle matches channel context
                if not trial.is_static and not trial.emg.context_ok(ch, cycle.context):
                    continue
                # get data on analog sampling grid and compute rms
                try:
                    _, data = trial.get_emg_data(ch)
                except (KeyError, GaitDataError):
                    logger.warning('no channel %s for %s' % (ch, trial))
                    continue
                # resample to requested grid
                data_cyc = scipy.signal.resample(data, analog_len)
                if ch not in data_all['emg']:
                    data_all['emg'][ch] = data_cyc[None, :]
                else:
                    data_all['emg'][ch] = np.concatenate(
                        [data_all['emg'][ch], data_cyc[None, :]]
                    )
    logger.info(
        'collected %d trials, %d/%d R/L cycles, %d/%d forceplate cycles'
        % (len(trials), ncycles['R'], ncycles['L'], ncycles['R_fp'], ncycles['L_fp'])
    )
    return data_all, ncycles, toeoff_frames
