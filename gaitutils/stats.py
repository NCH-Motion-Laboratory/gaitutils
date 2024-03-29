# -*- coding: utf-8 -*-
"""
Compute statistics across/within trials


@author: Jussi (jnu@iki.fi)
"""


import logging
import numpy as np
import scipy
import itertools
from collections import defaultdict

from .trial import Trial, Gaitcycle
from . import models, numutils
from .envutils import GaitDataError
from .numutils import _get_local_max, _get_local_min
from .config import cfg
from .emg import AvgEMG


logger = logging.getLogger(__name__)


class AvgTrial(Trial):
    """Gait trial -style class that holds averaged data. The API is designed to mimic trial.Trial.

    An AvgTrial instance can be created from averaged data using __init__()
    or from a list of trials using from_trials().
    """

    def __repr__(self):
        s = '<AvgTrial |'
        s += f' trial name: {self.trialname}'
        s += f', trials: {self.source}'
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
        data_all, cycles = collect_trial_data(trials)

        avgdata_model, stddata_model, ncycles_ok_analog = average_model_data(
            data_all['model'],
            reject_zeros=reject_zeros,
            reject_outliers=reject_outliers,
            use_medians=use_medians,
        )
        avgdata_emg, stddata_emg, ncycles_ok_emg = average_analog_data(
            data_all['emg'],
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
            raise ValueError('no averaged data supplied')

        if nfiles is None:
            raise ValueError('nfiles must be supplied')

        self.nfiles = nfiles
        if sessionpath:
            self.sessionpath = sessionpath
            self.sessiondir = sessionpath.name
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

        self.emg = AvgEMG(avgdata_emg, stddata_emg)
        analog_npts = 1000  # default
        for ch in list(avgdata_emg.keys()):
            if avgdata_emg[ch] is not None:
                analog_npts = len(avgdata_emg[ch])

        self.tn_analog = np.linspace(0, 100, analog_npts)

        self.source = 'averaged data'
        self.subject_name = 'Unknown'
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
            logger.info(f'no averaged data for {var}, returning nans')
            var_dims = (3, 101)  # is this universal?
            data = np.empty(var_dims)
            data[:] = np.nan
        return self.t, data

    # XXX: why the cycle argument?
    def get_emg_data(self, ch, envelope=None, cycle=None):
        """Get averaged EMG RMS data.

        Parameters
        ----------
        ch : str
            The channel name.
        """
        if not envelope:
            raise ValueError('AvgTrial only supports EMG in RMS mode')
        return self.tn_analog, self.emg.get_channel_data(ch, envelope=True)

    def get_emg_stddata(self, ch):
        """Get averaged EMG RMS standard deviation.

        Parameters
        ----------
        ch : str
            The channel name.
        """
        return self.tn_analog, self.emg.get_channel_stddata(ch)

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


def average_analog_data(data, reject_outliers=None, use_medians=None):
    """Average collected analog data.

    Parameters
    ----------
    data : dict
        Data to average (from collect_trial_data). Keys should be names of
        analog variables and values should be corresponding 1-D data.
    reject_outliers : float or None
        None for no automatic outlier rejection. Otherwise, a P value for false
        rejection (assuming strictly normally distributed data). Outliers are
        rejected based on robust statistics (modified Z-score).
    use_medians: bool
        Use median and MAD (median absolute deviation) instead of mean and
        stddev. The median is robust to outliers, but not robust to small
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

    if use_medians is None:
        use_medians = False

    for var, vardata in data.items():
        if vardata is None:
            stddata[var] = None
            avgdata[var] = None
            ncycles_ok[var] = 0
            continue
        else:
            n_ok = vardata.shape[0]
            # do the outlier rejection
            if n_ok > 0 and reject_outliers is not None and not use_medians:
                logger.info('averaging %s (N=%d)' % (var, n_ok))
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
        Data to average (from collect_trial_data).
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
                logger.info(f'{var}:')
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
    trials,
    collect_types=None,
    fp_cycles_only=None,
    force_collect_all_cycles=None,
    analog_len=None,
    analog_envelope=None,
):
    """Read model and analog cycle-normalized data from trials into numpy arrays.

    Parameters
    ----------
    trials : list | str | Trial
        List of c3d filenames or Trial instances to collect data from.
        Alternatively, a single filename or Trial instance.
    collect_types : list | None
        The types of data to collect. Currently supported types: 'model', 'emg'.
        If None, collect all supported types.
    fp_cycles_only : bool
        If True, collect data from forceplate cycles only. Kinetics model vars
        will always be collected from forceplate cycles only (unless
        force_collect_all_cycles is True).
    force_collect_all_cycles: bool
        If True, return all the cycles, including kinetic non-forceplate. Overrides
        fp_cycles_only.
    analog_len : int
        Analog data length varies by gait cycle, so it will be resampled into
        grid length specified by analog_len (default 1000 samples)
    analog_envelope : bool
        Whether to compute envelope of analog data or return raw data. By
        default the data will be enveloped.

    Returns
    -------
    tuple
        Tuple of (data_all, cycles_all):

            data_all : dict
                Nested dict of the collected data. First key is the variable type,
                second key is the variable name. The values are NxT ndarrays of the data,
                where N is the number of collected curves and T is the dimensionality.
            cycles_all : dict
                Nested dict of the collected cycles. First key is the variable type,
                second key is the variable name. The values are Gaitcycle instances.

        Example: you can obtain all collected curves for LKneeAnglesX as
        data_all['model']['LKneeAnglesX']. This will be a Nx101 ndarray. You can obtain
        the corresponding gait cycles as cycles_all['model']['LKneeAnglesX']. This will
        be a length N list of Gaitcycles. You can use that to obtain various metadata, e.g.
        create a list of toeoff frames for each curve:
        [cyc.toeoffn for cyc in cycles_all['model']['LKneeAnglesX']]
    """

    data_all = dict()
    cycles_all = dict()

    if fp_cycles_only is None:
        fp_cycles_only = False

    if collect_types is None:
        collect_types = ['model', 'emg']

    if analog_len is None:
        analog_len = 1000  # reasonable default for analog data (?)

    if analog_envelope is None:
        analog_envelope = True

    if not trials:
        return None, None

    if not isinstance(trials, list):
        trials = [trials]

    if 'model' in collect_types:
        data_all['model'] = defaultdict(lambda: None)
        cycles_all['model'] = defaultdict(list)
        models_to_collect = models.models_all
    else:
        models_to_collect = list()

    if 'emg' in collect_types:
        data_all['emg'] = defaultdict(lambda: None)
        cycles_all['emg'] = defaultdict(list)
        emg_chs_to_collect = cfg.emg.channel_labels.keys()
    else:
        emg_chs_to_collect = list()

    trial_types = list()
    for trial_ in trials:
        # create Trial instance in case we got filenames as args
        trial = trial_ if isinstance(trial_, Trial) else Trial(trial_)
        logger.info(f'collecting data for {trial.trialname}')
        trial_types.append(trial.is_static)
        if any(trial_types) and not all(trial_types):
            raise GaitDataError('Cannot mix dynamic and static trials')

        cycles = [None] if trial.is_static else trial.cycles

        for cycle in cycles:

            # collect model data
            for model in models_to_collect:
                for var in model.varnames:
                    if not trial.is_static:
                        # pick data only if var context matches cycle context
                        # FIXME: should implement context() for models
                        # (and a filter for context?)
                        if var[0] != cycle.context:
                            continue

                        if not force_collect_all_cycles:
                            # don't collect kinetics if cycle is not on forceplate
                            if (
                                model.is_kinetic_var(var) or fp_cycles_only
                            ) and not cycle.on_forceplate:
                                continue

                    _, data = trial.get_model_data(var, cycle=cycle)
                    if np.all(np.isnan(data)):
                        logger.debug(f'no data for {trial.trialname}/{var}')
                    else:
                        cycles_all['model'][var].append(cycle)
                        if var not in data_all['model']:
                            data_all['model'][var] = data[None, :]
                        else:
                            data_all['model'][var] = np.concatenate(
                                [data_all['model'][var], data[None, :]]
                            )

            # collect EMG data
            for ch in emg_chs_to_collect:
                # check whether cycle matches channel context
                if not trial.is_static and not trial.emg.context_ok(ch, cycle.context):
                    continue

                if not force_collect_all_cycles:
                    if fp_cycles_only and not cycle.on_forceplate:
                        continue

                # get data on analog sampling grid
                try:
                    logger.debug(f'collecting EMG channel {ch} from {cycle}')
                    _, data = trial.get_emg_data(
                        ch, cycle=cycle, envelope=analog_envelope
                    )
                except (KeyError, GaitDataError):
                    logger.warning(f'no channel {ch} for {trial}')
                    continue
                # resample to requested grid
                data_cyc = scipy.signal.resample(data, analog_len)
                cycles_all['emg'][ch].append(cycle)
                if ch not in data_all['emg']:
                    data_all['emg'][ch] = data_cyc[None, :]
                else:
                    data_all['emg'][ch] = np.concatenate(
                        [data_all['emg'][ch], data_cyc[None, :]]
                    )
    logger.info('collected %d trials' % len(trials))
    return data_all, cycles_all


def curve_extract_values(curves, toeoffs):
    """Extract values from gait curves.

    This extracts values such as swing phase maximum from a set of gait curves.
    The curves are input as ndarrays, returned by e.g. collect_trial_data().
    Data with any nans will result in (at least partially) nan output values.

    Parameters
    ----------
    curves : ndarray
        NxT array of gait curves. Typically T==101 for normalized data.
    toeoffs : ndarray
        Nx1 array of toeoff frame indices, one for each curve. This frame
        separates the contact phase from the swing phase.

    Returns
    -------
    dict
        Dictionary of results, with following keys:
            'contact' : list of curve values at initial foot contact (frame 0)
            'toeoff' : list of curve values at toeoff
            'extrema' : nested dict of simple extrema
            'peaks' : nested dict of peaks (local extrema)
        The nested dicts have keys:
            1: 'overall', 'swing', or 'stance' : the phase of the gait curve
            2: 'min', 'argmin', 'max', or 'argmax' : the values and indices

    Thus, to get maximum peak values at swing phase, use
    results['peaks']['swing']['max'].
    """

    if isinstance(curves, list):
        curves = np.array(curves)
    if isinstance(toeoffs, list):
        toeoffs = np.array(toeoffs)
    if curves.shape[0] != toeoffs.shape[0]:
        raise ValueError('invalid shape of arguments')
    # use defaultdict to reduct dict initialization boilerplate
    results = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    results['contact'] = list()
    results['toeoff'] = list()

    for curve, toeoff in zip(curves, toeoffs):

        # extract stance and swing phases; swing phase begins at the toeoff frame
        curve_stance, curve_swing = np.split(curve, [toeoff])

        # get the simple extrema
        results['extrema']['overall']['min'].append(curve.min())
        results['extrema']['overall']['argmin'].append(curve.argmin())
        results['extrema']['overall']['max'].append(curve.max())
        results['extrema']['overall']['argmax'].append(curve.argmax())

        results['extrema']['stance']['min'].append(curve_stance.min())
        results['extrema']['stance']['argmin'].append(curve_stance.argmin())
        results['extrema']['stance']['max'].append(curve_stance.max())
        results['extrema']['stance']['argmax'].append(curve_stance.argmax())

        # swing phase indices need to be offset by the toeff frame
        results['extrema']['swing']['min'].append(curve_swing.min())
        results['extrema']['swing']['argmin'].append(curve_swing.argmin() + toeoff)
        results['extrema']['swing']['max'].append(curve_swing.max())
        results['extrema']['swing']['argmax'].append(curve_swing.argmax() + toeoff)

        # get the peaks (local extrema)
        ind, val = _get_local_min(curve)
        results['peaks']['overall']['argmin'].append(ind)
        results['peaks']['overall']['min'].append(val)
        ind, val = _get_local_max(curve)
        results['peaks']['overall']['argmax'].append(ind)
        results['peaks']['overall']['max'].append(val)

        ind, val = _get_local_min(curve_stance)
        results['peaks']['stance']['argmin'].append(ind)
        results['peaks']['stance']['min'].append(val)
        ind, val = _get_local_max(curve_stance)
        results['peaks']['stance']['argmax'].append(ind)
        results['peaks']['stance']['max'].append(val)

        ind, val = _get_local_min(curve_swing)
        results['peaks']['swing']['argmin'].append(ind + toeoff)
        results['peaks']['swing']['min'].append(val)
        ind, val = _get_local_max(curve_swing)
        results['peaks']['swing']['argmax'].append(ind + toeoff)
        results['peaks']['swing']['max'].append(val)

        # get some single values
        results['contact'].append(curve[0])
        results['toeoff'].append(curve[toeoff])

        # if needed, we can finally return a regular dict
        # results = dict(results)
        # for k in 'extrema', 'peaks':
        #     results[k] = dict(results[k])
        #     for x, v in results[k].items():
        #         results[k][x] = dict(v)

    return results


def _trials_extract_values(trials, from_models=None):
    """Extract curve values from given trials.

    Parameters
    ----------
    trials: list
        List of c3d files or Trial instances to extract data from.
    from_models : list
        List of GaitModel instances. These determine the variables to collect
        data for.

    Returns
    -------
    dict
        Dict keyed by variable. The values are dicts as returned by
        curve_extract_values().
    """
    if from_models is None:
        from_models = [
            models.pig_lowerbody,
        ]
    try:
        thevars = itertools.chain.from_iterable(mod.varnames for mod in from_models)
    except AttributeError:
        raise RuntimeError('')
    # collect all curves
    data, cycles = collect_trial_data(trials, collect_types=['model'])
    vals = dict()
    # extract values for each variable
    for var in thevars:
        data_var = data['model'][var]
        toeoffs_var = [cyc.toeoffn for cyc in cycles['model'][var]]
        if data_var is not None and toeoffs_var is not None:
            vals[var] = curve_extract_values(data_var, toeoffs_var)
        else:
            logger.info(f'no data for {var}')
    return vals
