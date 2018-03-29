# -*- coding: utf-8 -*-
"""
Created on Tue Mar 17 14:41:31 2015

Read gait trials.

@author: Jussi (jnu@iki.fi)
"""


from __future__ import division
from collections import defaultdict
import numpy as np
import os.path as op
import glob
import logging

from . import read_data
from . import nexus
from . import utils
from . import eclipse
from . import models
from .emg import EMG
from .config import cfg
from .envutils import GaitDataError


logger = logging.getLogger(__name__)


def nexus_trial():
    """ Return Trial instance reading from Nexus """
    vicon = nexus.viconnexus()
    return Trial(vicon)


class Gaitcycle(object):
    """" Holds information about one gait cycle """
    def __init__(self, start, end, toeoff, context,
                 on_forceplate, smp_per_frame, trial=None, name=None,
                 index=None):
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
        """ Normalize frames-based variable var to the cycle.
        New interpolated x axis is 0..100% of the cycle. """
        return self.tn, np.interp(self.tn, self.t, var[self.start:self.end])

    def crop_analog(self, var):
        """ Crop analog variable (EMG, forceplate, etc. ) to the
        cycle; no interpolation. """
        return self.tn_analog, var[self.start_smp:self.end_smp]


class Trial(object):
    """ A gait trial. Contains:
    -subject and trial info
    -gait cycles
    -analog data (EMG, forceplate, etc.)
    -model output variables (Plug-in Gait, muscle length, etc.)
    FIXME: lazy reads should check whether underlying trial has changed
    (at least for Nexus)
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
        # read metadata into instance attributes
        meta = read_data.get_metadata(source)
        self.__dict__.update(meta)

        # sort events and make them 0-based so that indexing matches frame data
        self.lstrikes = [e - self.offset for e in sorted(self.lstrikes)]
        self.rstrikes = [e - self.offset for e in sorted(self.rstrikes)]
        self.ltoeoffs = [e - self.offset for e in sorted(self.ltoeoffs)]
        self.rtoeoffs = [e - self.offset for e in sorted(self.rtoeoffs)]

        self.sessiondir = op.split(self.sessionpath)[-1]
        # TODO: sometimes trial .enf name seems to be different?
        enfpath = op.join(self.sessionpath, self.trialname + '.Trial.enf')

        if op.isfile(enfpath):
            logger.debug('reading Eclipse info from %s' % enfpath)
            edata = eclipse.get_eclipse_keys(enfpath)
            # for convenience, eclipse_data returns '' for nonexistent keys
            self.eclipse_data = defaultdict(lambda: '', edata)
        else:
            logger.debug('no .enf file found')
            self.eclipse_data = defaultdict(lambda: '', {})
        # data are lazily read
        self.emg = EMG(self.source)
        self._forceplate_data = None
        self._marker_data = None
        self.fp_events = self._get_fp_events()
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
        self.cycles = list(self._scan_cycles())
        self.ncycles = len(self.cycles)
        self.video_files = glob.glob(self.sessionpath+self.trialname+'*avi')

    def __getitem__(self, item):
        """ Get model variable or EMG channel by indexing, normalized
        according to normalization cycle.
        FIXME: risk of duplicate names is getting too high, need to change to
        dedicated getters or include variable type in name (e.g. EMG:LHam)
        """
        try:
            t = self.t
            data = self._get_modelvar(item)
            if self._normalize:
                t, data = self._normalize.normalize(data)
            return t, data
        except ValueError:
                t = self.t_analog
                data = self.emg[item]
                if self._normalize:
                    t, data = self._normalize.crop_analog(data)
                return t, data

    @property
    def forceplate_data(self):
        if not self._forceplate_data:
            self._forceplate_data = read_data.get_forceplate_data(self.source)
        return self._forceplate_data

    @property
    def marker_data(self):
        if not self._marker_data:
            self._marker_data = read_data.get_marker_data(self.source,
                                                          self.markers)
        return self._marker_data

    def _get_fp_events(self):
        """Read the forceplate events or set to empty"""
        try:
            fp_info = (eclipse.eclipse_fp_keys(self.eclipse_data) if
                       cfg.trial.use_eclipse_fp_info else None)
            return utils.detect_forceplate_events(self.source, fp_info=fp_info)
        except GaitDataError:
            logger.warning('Could not detect forceplate events')
            _fp_events = dict()
            _fp_events['R_strikes'] = []
            _fp_events['R_toeoffs'] = []
            _fp_events['L_strikes'] = []
            _fp_events['L_toeoffs'] = []
            _fp_events['valid'] = set()
            return _fp_events

    def set_norm_cycle(self, cycle=None):
        """ Set normalization cycle (int for cycle index or a Gaitcycle
        instance). None to get unnormalized data. Affects the data returned
        by __getitem__ """
        if type(cycle) == int:
            cycle = self.cycles[cycle]
        self._normalize = cycle if cycle else None

    def get_cycle(self, context, ncycle):
        """ e.g. ncycle=2 and context='L' returns 2nd left gait cycle.
        Note that this uses 1-based indexing in contrast to
        set_norm_cycle() """
        cycles = [cycle for cycle in self.cycles
                  if cycle.context == context.upper()]
        if ncycle < 1:
            raise ValueError('Index of gait cycle must be >= 1')
        if len(cycles) < ncycle:
            raise ValueError('Requested gait cycle %d does not '
                             'exist in data' % ncycle)
        else:
            return cycles[ncycle-1]

    def _get_modelvar(self, var):
        """ Return (unnormalized) model variable, load and cache data for
        model if needed """
        model_ = models.model_from_var(var)
        if not model_:
            raise ValueError('No model found for %s' % var)
        if model_.desc not in self._models_data:
            # read and cache model data
            modeldata = read_data.get_model_data(self.source, model_)
            self._models_data[model_.desc] = modeldata
        return self._models_data[model_.desc][var]

    def _scan_cycles(self):
        """ Create gait cycle instances based on strike/toeoff markers. """
        # The events marked in the trial marked events need to be matched
        # with detected forceplate events, but may not match exactly, so use
        # a tolerance
        STRIKE_TOL = 4
        sidestrs = {'R': 'Right', 'L': 'Left'}
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
                else:
                    diffs = np.abs(fp_strikes - start)
                    on_forceplate = min(diffs) <= STRIKE_TOL
                    logger.debug('side %s: cycle start: %d, '
                                 'detected fp events: %s'
                                 % (context, start, fp_strikes))
                end = strikes[k+1]
                toeoff = [x for x in toeoffs if x > start and x < end]
                if len(toeoff) == 0:
                    raise GaitDataError('No toeoff for cycle starting at %d'
                                        % start)
                elif len(toeoff) > 1:
                    raise GaitDataError('Multiple toeoffs for cycle starting '
                                        'at %d' % start)
                else:
                    toeoff = toeoff[0]
                fp_str = '(on forceplate)' if on_forceplate else ''
                name = '%s %d %s' % (sidestrs[context], (k+1), fp_str)
                yield Gaitcycle(start, end, toeoff, context,
                                on_forceplate, self.samplesperframe,
                                trial=self, index=k+1, name=name)


def _step_width(trial):
    """ Compute step width over trial cycles. See:
    https://www.vicon.com/faqs/software/how-does-nexus-plug-in-gait-and-polygon-calculate-gait-cycle-parameters-spatial-and-temporal
    Returns context keyed dict of lists.
    FIXME: marker name into params?
    """
    sw = dict()
    mkr = 'TOE'  # marker name without context
    mdata = trial.marker_data
    for context, strikes in zip(['L', 'R'], [trial.lstrikes, trial.rstrikes]):
        sw[context] = list()
        nstrikes = len(strikes)
        if nstrikes < 2:
            continue
        # contralateral vars
        context_co = 'L' if context == 'R' else 'R'
        strikes_co = trial.lstrikes if context == 'R' else trial.rstrikes
        mname = context + mkr
        mname_co = context_co + mkr
        for j, strike in enumerate(strikes):
            if strike == strikes[-1]:  # last strike on this side
                break
            pos_this = mdata[mname+'_P'][strike]
            pos_next = mdata[mname+'_P'][strikes[j+1]]
            strikes_next_co = [k for k in strikes_co if k > strike]
            if len(strikes_next_co) == 0:  # no subsequent contralateral strike
                break
            pos_next_co = mdata[mname_co+'_P'][strikes_next_co[0]]
            # vector distance between 'step lines' (see url above)
            V1 = pos_next - pos_this
            V1 = V1 / np.linalg.norm(V1)
            VC = pos_next_co - pos_this
            VCP = V1 * np.dot(VC, V1)  # proj to ipsilateral line
            VSW = VCP - VC
            sw[context].append(np.linalg.norm(VSW))
    return sw
