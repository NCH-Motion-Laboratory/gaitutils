# -*- coding: utf-8 -*-
"""
Created on Tue Mar 17 14:41:31 2015

Read gait trials.

@author: Jussi (jnu@iki.fi)
"""


from __future__ import division
from builtins import range
from builtins import object
from collections import defaultdict
import numpy as np
import re
import os.path as op
import logging

from .emg import EMG
from . import (cfg, GaitDataError, read_data, nexus, utils, eclipse, models,
               videos, sessionutils)

logger = logging.getLogger(__name__)


def nexus_trial(from_c3d=False):
    """Return Trial instance from currently open Nexus trial.
   
    Parameters
    ----------
    from_c3d : bool
        If True, try to read the trial data from the corresponding c3d file.

    Returns
    -------
        A Trial instance.

    """
    vicon = nexus.viconnexus()
    if from_c3d:
        trname = vicon.GetTrialName()
        c3dfile = op.join(*trname) + '.c3d'
        if op.isfile(c3dfile):
            return Trial(c3dfile)
        else:
            logger.info('no c3d file %s for currently loaded trial, loading '
                        'directly from Nexus' % c3dfile)
            return Trial(nexus.viconnexus())
    else:
        return Trial(nexus.viconnexus())


class Noncycle(object):
    """Used in place of Gaitcycle when requesting unnormalized data."""
    def __init__(self, context, trial=None):
        self.context = context
        self.trial = trial
        self.name = 'unnorm. (%s)' % context
        self.toeoffn = None
        self.on_forceplate = False
        self.start = None
        self.end = None


class Gaitcycle(object):
    """ Gait cycle class.

        Parameters
        ----------
        start : int
            Starting frame for the cycle.
        start : int
            Ending frame for the cycle.
        toeoff : int
            Frame where toeoff occurs.
        context : str
            Cycle context: R or L for right and left, respectively.
        on_forceplate : bool
            Whether cycle starts on forceplate contact.
        plate_idx : int
            Index of forceplate.
        smp_per_frame : float
            Analog samples per frame.
        trial : instance of Trial
            The trial instance owning this cycle. Does not need to be set.
        name : str
            Name for the cycle. Can be set freely.
        index : int
            Cycle index.
    """

    def __init__(self, start, end, toeoff, context, on_forceplate, plate_idx,
                 smp_per_frame, trial=None, name=None, index=None):
        self.len = end - start
        # convert frame indices to 0-based
        self.start = start
        self.end = end
        self.toeoff = toeoff
        # which foot begins and ends the cycle
        self.context = context
        # whether cycle begins with forceplate strike
        self.on_forceplate = on_forceplate
        # start and end on the analog samples axis; round to whole samples
        self.start_smp = int(round(self.start * smp_per_frame))
        self.end_smp = int(round(self.end * smp_per_frame))
        self.len_smp = self.end_smp - self.start_smp
        # normalized x-axis (% of gait cycle) of same length as cycle
        self.t = np.linspace(0, 100, self.len)
        # same for analog variables
        self.tn_analog = np.linspace(0, 100, self.len_smp)
        # normalized x-axis of 0,1,2..100%
        self.tn = np.linspace(0, 100, 101)
        # normalize toe-off event to the cycle
        self.toeoffn = round(100*((self.toeoff - self.start) / self.len))
        self.trial = trial
        self.plate_idx = plate_idx
        self.index = index
        self.name = name

    def __repr__(self):
        s = '<Gaitcycle |'
        s += ' start: %d,' % self.start
        s += ' end: %d,' % self.end
        s += ' context: %s,' % self.context
        s += ' on forceplate,' if self.on_forceplate else ' not on forceplate,'
        s += ' toeoff: %d' % self.toeoff
        s += '>'
        return s

    def normalize(self, var):
        """Normalize (columns of) frames-based variable var to the cycle.

        Parameters
        ----------
        var : array
            NxM array of frame-based data to normalize.

        Returns
        -------
        tn, ndata
        
        """
        # convert 1D arrays to 2D
        if len(var.shape) == 1:
            var = var[:, np.newaxis]
        ncols = var.shape[1]
        idata = np.array([np.interp(self.tn,
                                    self.t, var[self.start:self.end, k])
                          for k in range(ncols)]).T
        return self.tn, np.squeeze(idata)

    def crop_analog(self, var):
        """Crop analog variable (EMG, forceplate, etc. ) to the gait cycle.

        Parameters
        ----------
        var : array
            NxM array of analog data to normalize.
        """
        return self.tn_analog, var[self.start_smp:self.end_smp]


class Trial(object):
    """Gait trial class.

        Parameters
        ----------
        source : str | instance of ViconNexus
            Source to read data from. Can be a c3d filename or a ViconNexus
            connection.
    """

    def __repr__(self):
        s = '<Trial |'
        s += ' trial: %s' % self.trialname
        s += ', data source: %s' % self.source
        s += ', subject: %s' % self.name
        s += ', gait cycles: %s' % self.ncycles
        s += '>'
        return s

    def __init__(self, source):
        logger.debug('new trial instance from %s' % source)
        self.source = source
        meta = read_data.get_metadata(source)
        # insert metadata dict directly as instance attributes
        self.__dict__.update(meta)

        # sort events and make them 0-based so that indexing matches frame data
        self.lstrikes = [e - self.offset for e in sorted(self.lstrikes)]
        self.rstrikes = [e - self.offset for e in sorted(self.rstrikes)]
        self.ltoeoffs = [e - self.offset for e in sorted(self.ltoeoffs)]
        self.rtoeoffs = [e - self.offset for e in sorted(self.rtoeoffs)]

        self.sessiondir = op.split(self.sessionpath)[-1]

        enfpath = op.join(self.sessionpath, '%s.Trial.enf' % self.trialname)
        # also look for alternative (older style?) enf name
        if not op.isfile(enfpath):
            trialn_re = re.search('\.*(\d*)$', self.trialname)
            trialn = trialn_re.group(1)
            if trialn:
                trialname_ = '%s.Trial%s.enf' % (self.trialname, trialn)
                enfpath = op.join(self.sessionpath, trialname_)
        self.enfpath = enfpath
        if op.isfile(self.enfpath):
            logger.debug('reading Eclipse info from %s' % self.enfpath)
            edata = eclipse.get_eclipse_keys(self.enfpath)
            # for convenience, eclipse_data returns '' for nonexistent keys
            self.eclipse_data = defaultdict(lambda: '', edata)
        else:
            logger.debug('no .enf file found')
            self.eclipse_data = defaultdict(lambda: '', {})
        self.is_static = self.eclipse_data['TYPE'].upper() == 'STATIC'
        # handle session quirks
        quirks = sessionutils.load_quirks(self.sessionpath)
        if 'emg_correction_factor' in quirks:
            emg_correction_factor = quirks['emg_correction_factor']
            logger.warning('using quirk: EMG correction factor = %g' % emg_correction_factor)
        else:
            emg_correction_factor = 1
        if 'ignore_eclipse_fp_info' in quirks:
            logger.warning('using quirk: ignore Eclipse forceplate fields')
            self.use_eclipse_fp_info = False
        else:
            self.use_eclipse_fp_info = True
        # data are lazily read
        self.emg = EMG(self.source, correction_factor=emg_correction_factor)
        self._forceplate_data = None
        self._marker_data = None
        if not self.is_static:
            self.fp_events = self._get_fp_events()
        else:
            self.fp_events = utils.empty_fp_events()

        self._models_data = dict()
        self.stddev_data = None  # AvgTrial only
        # whether to normalize data
        self._normalize = None
        # frames 0...length
        self.t = np.arange(self.length)
        # analog frames 0...length
        self.t_analog = np.arange(self.length * self.samplesperframe)
        # normalized x-axis of 0, 1, 2 .. 100%
        self.tn = np.linspace(0, 100, 101)
        self.samplesperframe = self.analograte/self.framerate
        self.cycles = list() if self.is_static else list(self._scan_cycles())
        self.ncycles = len(self.cycles)

    @property
    def videos(self):
        """Get all trial videos"""
        trialbase = op.join(self.sessionpath, self.trialname)
        return videos.get_trial_videos(trialbase)

    @property
    def eclipse_tag(self):
        """Return the first matching Eclipse tag for this trial."""
        for tag in cfg.eclipse.tags:
            if any([tag in self.eclipse_data[fld] for fld in
                    cfg.eclipse.tag_keys]):
                return tag
        return None

    @property
    def name_with_description(self):
        """Return string consisting of trial name and some Eclipse info."""
        # FIXME: Eclipse keys hardcoded
        return '%s (%s, %s)' % (self.trialname,
                                self.eclipse_data['DESCRIPTION'],
                                self.eclipse_data['NOTES'])

    def _normalized_frame_data(self, data):
        """Return time axis and cycle normalized frame data"""
        if self._normalize is not None:
            t, data = self._normalize.normalize(data)
        else:
            t = self.t
        return t, data

    def _normalized_analog_data(self, data):
        """Return time axis and cycle normalized (cropped) analog data"""
        if self._normalize is not None:
            t, data = self._normalize.crop_analog(data)
        else:
            t = self.t_analog
        return t, data

    @property
    def full_marker_data(self):
        """Return the full marker data dict."""
        if not self._marker_data:
            self._marker_data = read_data.get_marker_data(self.source,
                                                          self.markers)
        return self._marker_data

    def get_model_data(self, var):
        """Return trial data for a model variable.

        Parameters
        ----------
        var : string
            The model variable name.
        """
        data = self._get_modelvar(var)
        return self._normalized_frame_data(data)

    def get_emg_data(self, ch):
        """Return trial data for an EMG variable.

        Parameters
        ----------
        ch : string
            The EMG channel name.
        """
        data = self.emg[ch]
        return self._normalized_analog_data(data)

    def get_marker_data(self, marker):
        """Return trial data for a given marker.

        Parameters
        ----------
        marker : string
            The marker name.
        """
        if marker not in self.markers:
            raise GaitDataError('No such marker')
        data = self.full_marker_data[marker]
        return self._normalized_frame_data(data)

    def get_forceplate_data(self, nplate, kind='force'):
        """Return trial data for a forceplate.

        Parameters
        ----------
        nplate : int
            The forceplate index. Plates are numbered starting from 0, i.e.
            nplate=0 corresponds to Nexus plate 1.
        kind : str
            The type of data to return. Can be 'force', 'moment', or 'cop'
            (center of pressure).
        """
        if not self._forceplate_data:
            self._forceplate_data = read_data.get_forceplate_data(self.source)
        if nplate < 0 or nplate >= len(self._forceplate_data):
            raise GaitDataError('Invalid plate index %d' % nplate)
        if kind == 'force':
            data = self._forceplate_data[nplate]['F']
        elif kind == 'moment':
            data = self._forceplate_data[nplate]['M']
        elif kind == 'cop':
            data = self._forceplate_data[nplate]['CoP']
        else:
            raise ValueError('Invalid kind of forceplate data requested')
        return self._normalized_analog_data(data)

    """WIP"""
    def get_accelerometer_data(self):
        return read_data.get_accelerometer_data(self.source)

    def _get_fp_events(self):
        """Read the forceplate events."""
        try:
            fp_info = (eclipse.eclipse_fp_keys(self.eclipse_data) if
                       cfg.trial.use_eclipse_fp_info and self.use_eclipse_fp_info else None)
            # FIXME: marker data already read?
            return utils.detect_forceplate_events(self.source, fp_info=fp_info)
        except GaitDataError:
            logger.warning('Could not detect forceplate events')
            return utils.empty_fp_events()

    def set_norm_cycle(self, cycle=None):
        """ Set normalization cycle.

        The get_ methods will return data normalized to the given cycle.

        Parameters
        ----------
        cycle : int | Gaitcycle | None
            The cycle to normalize data to. Can be a Gaitcycle index (obtain
            cycle by e.g. get_cycles) or a direct index to trial.cycles.
            If None, do not normalize data to gait cycles.
        """

        if isinstance(cycle, int):
            if cycle >= len(self.cycles) or cycle < 0:
                raise ValueError('No such cycle')
            cycle = self.cycles[cycle]
            self._normalize = cycle
        elif isinstance(cycle, Gaitcycle):
            self._normalize = cycle
        elif cycle is None or isinstance(cycle, Noncycle):
            self._normalize = None

    def get_cycles(self, cyclespec):
        """ Get specified gait cycles from the trial as Gaitcycle instances.

        Parameters
        ----------
        cyclespec : dict | str | int | tuple | list
            The cycles to get. Can be dict with 'R' and 'L' keys and
            specification as values to get context specific cycles. If not a
            dict, the given specification will be applied to both contexts.

            'all' gets all trial cycles. 'forceplate' gets cycles starting with
            valid forceplate contact. '1st_forceplate' gets the 1st cycle with
            valid forceplate contact. 'unnormalized' gets a Noncycle that is
            used as a sentinel for unnormalized data.
            An int or a list of int gives the specified cycle indices from the
            trial.
            A tuple can be used to match conditions one by one. For example,
            ('forceplate', 0) would return forceplate cycles if any, and the
            first cycle in case there are none.

        Returns list of gaitcycle instances, sorted by starting frame.
        """
        def _filter_cycles(cycles, context, cyclespec):
            """Takes a list of cycles and filters it according to cyclespec,
            returning only cycles that match the spec"""
            if cyclespec is None:
                return [Noncycle(context=context, trial=self)]
            elif isinstance(cyclespec, int):
                return [cycles[cyclespec]] if cyclespec < len(cycles) else []
            elif isinstance(cyclespec, list):
                return [cycles[c] for c in cyclespec if c < len(cycles)]
            elif cyclespec == 'unnormalized':
                return [Noncycle(context=context)]
            elif cyclespec == 'all':
                return cycles
            elif cyclespec == 'forceplate':  # all forceplate cycles
                return [c for c in cycles if c.on_forceplate]
            elif cyclespec == '1st_forceplate':  # 1st forceplate cycle
                return [c for c in cycles if c.on_forceplate][:1]
            elif isinstance(cyclespec, tuple):
                # recurse until we have cycles (or cyclespec is exhausted)
                if not cyclespec:
                    return []
                else:
                    return (_filter_cycles(cycles, context, cyclespec[0]) or
                            _filter_cycles(cycles, context, cyclespec[1:]))
            else:
                raise ValueError('Invalid argument')

        if not isinstance(cyclespec, dict):
            cyclespec = {'R': cyclespec, 'L': cyclespec}

        cycs_ok = list()
        for context in cyclespec:
            # pick trial cycles for this context
            cycles_ = [c for c in self.cycles if c.context == context.upper()]
            # filter them according to cyclespec
            good_cycles = _filter_cycles(cycles_, context, cyclespec[context])
            cycs_ok.extend(good_cycles)

        return sorted(cycs_ok, key=lambda cyc: cyc.start)

    def _get_modelvar(self, var):
        """Return unnormalized data for a model variable."""
        model_ = models.model_from_var(var)
        if not model_:
            raise ValueError('No model found for %s' % var)
        if model_.desc not in self._models_data:
            # read and cache model data
            modeldata = read_data.get_model_data(self.source, model_)
            self._models_data[model_.desc] = modeldata
        return self._models_data[model_.desc][var]

    def _scan_cycles(self):
        """Create Gaitcycle instances based on trial strike/toeoff markers."""
        # The events marked in the trial marked events need to be matched
        # with detected forceplate events, but may not match exactly, so use
        # a tolerance
        STRIKE_TOL = 7
        sidestrs = {'R': 'right', 'L': 'left'}
        for strikes in [self.lstrikes, self.rstrikes]:
            len_s = len(strikes)
            if len_s < 2:
                continue
            if strikes == self.lstrikes:
                toeoffs = self.ltoeoffs
                context = 'L'
            else:
                toeoffs = self.rtoeoffs
                context = 'R'
            for k in range(0, len_s-1):
                start = strikes[k]
                # see if cycle starts on forceplate strike
                fp_strikes = np.array(self.fp_events[context + '_strikes'])
                if fp_strikes.size == 0:
                    on_forceplate = False
                    plate_idx = None
                else:
                    diffs = np.abs(fp_strikes - start)
                    on_forceplate = min(diffs) <= STRIKE_TOL
                    if on_forceplate:
                        strike_idx = np.argmin(diffs)
                        plate_idx = self.fp_events[context + '_strikes_plate'][strike_idx]
                    else:
                        plate_idx = None
                    logger.debug('side %s: cycle start: %d, '
                                 'detected fp events: %s'
                                 % (context, start, fp_strikes))
                end = strikes[k+1]
                toeoff = [x for x in toeoffs if x > start and x < end]
                if len(toeoff) == 0:
                    raise GaitDataError('%s: no toeoff for cycle starting at '
                                        '%d' % (self.trialname, start))
                elif len(toeoff) > 1:
                    raise GaitDataError('%s: multiple toeoffs for cycle '
                                        'starting at %d' % (self.trialname,
                                                            start))
                else:
                    toeoff = toeoff[0]
                fp_str = ' (fp)' if on_forceplate else ''
                name = '%s%d%s' % (sidestrs[context], (k+1), fp_str)
                yield Gaitcycle(start, end, toeoff, context,
                                on_forceplate, plate_idx, self.samplesperframe,
                                trial=self, index=k+1, name=name)
