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
    return Trial(nexus.viconnexus())


def _nexus_crop_events_before_forceplate():
    """Delete events before forceplate strike so that the first cycle starts
    on forceplate
    FIXME: why not use events from trial instance?"""
    vicon = nexus.viconnexus()
    tr = Trial(vicon)
    fp_cycles = [cyc for cyc in tr.cycles if cyc.on_forceplate]
    cycs_sorted = sorted(fp_cycles, key=lambda cyc: cyc.start)
    if not cycs_sorted:
        return
    cyc1 = cycs_sorted[0]
    context = {'L': 'Left', 'R': 'Right'}[cyc1.context]
    context_other = 'Left' if context == 'Right' else 'Right'
    strike_ctxt = vicon.GetEvents(tr.name, context, "Foot Strike")[0]
    strike_ctxt = [f for f in strike_ctxt if f >= cyc1.start]
    toeoff_ctxt = vicon.GetEvents(tr.name, context, "Foot Off")[0]
    toeoff_ctxt = [f for f in toeoff_ctxt if f >= cyc1.start]
    strike_other = vicon.GetEvents(tr.name, context_other, "Foot Strike")[0]
    toeoff_other = vicon.GetEvents(tr.name, context_other, "Foot Off")[0]
    vicon.ClearAllEvents()
    for ev in strike_ctxt:
        vicon.CreateAnEvent(tr.name, context, 'Foot Strike', ev, 0)
    for ev in strike_other:
        vicon.CreateAnEvent(tr.name, context_other, 'Foot Strike', ev, 0)
    for ev in toeoff_ctxt:
        vicon.CreateAnEvent(tr.name, context, 'Foot Off', ev, 0)
    for ev in toeoff_other:
        vicon.CreateAnEvent(tr.name, context_other, 'Foot Off', ev, 0)


class Noncycle(object):
    """Used in place of Gaitcycle when requesting unnormalized data.
    Just stores context and trial info. """
    def __init__(self, context, trial=None):
        self.context = context
        self.trial = trial
        self.name = 'unnormalized (%s)' % context
        self.toeoffn = None
        self.on_forceplate = False


class Gaitcycle(object):
    """ Holds information about one gait cycle """
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

        # look for alternative (older style?) enf name
        if not op.isfile(enfpath):
            trialn_re = re.search('\.*(\d*)$', self.trialname)
            trialn = trialn_re.group(1)
            if trialn:
                trialname_ = '%s.Trial%s.enf' % (self.trialname, trialn)
                enfpath = enfpath = op.join(self.sessionpath, trialname_)

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

    def video_files(self, ext='avi'):
        """Return video files associated with trial"""
        return glob.glob(op.join(self.sessionpath, self.trialname+'*%s' % ext))

    def _get_videos_by_id(self, camera_id, ext='avi'):
        """Get trial video corresponding to given camera id (str)"""
        return [vid for vid in self.video_files(ext=ext) if camera_id in vid]

    def get_video_by_label(self, camera_label, ext='avi'):
        """Get trial video correspoding to given camera id (str)"""
        ids = [id_ for id_, label in cfg.general.camera_labels.items() if
               camera_label == label]
        vids = [vid for id_ in ids for vid in
                self._get_videos_by_id(id_, ext=ext)]
        if len(vids) > 1:
            logger.warning('Multiple video files match label "%s", using the '
                           'newest one' % camera_label)
            # this relies on the yyyymmdd... timestamp in the filename
            return sorted(vids)[-1]
        return vids[0] if vids else None

    @property
    def eclipse_tag(self):
        """Return (first) Eclipse tag for this trial"""
        for tag in cfg.eclipse.tags:
            if any([tag in self.eclipse_data[fld] for fld in
                    cfg.eclipse.tag_keys]):
                return tag
        return None

    @property
    def name_with_description(self):
        """Return trial name with some Eclipse info"""
        # FIXME: Eclipse keys hardcoded
        return '%s (%s, %s)' % (self.trialname,
                                self.eclipse_data['DESCRIPTION'],
                                self.eclipse_data['NOTES'])

    def __getitem__(self, item):
        """ Get model variable or EMG channel by indexing, normalized
        according to normalization cycle.
        FIXME: risk of duplicate names is getting too high, need to change to
        dedicated getters or include variable type in name (e.g. EMG:LHam)
        """
        try:
            t = self.t
            data = self._get_modelvar(item)
            if self._normalize is not None:
                t, data = self._normalize.normalize(data)
            return t, data
        except ValueError:
            t = self.t_analog
            data = self.emg[item]
            if self._normalize is not None:
                t, data = self._normalize.crop_analog(data)
            return t, data

    """ The following properties are WIP and do not implement gait cycle
    normalization """
    @property
    def accelerometer_data(self):
        # FIXME: caching?
        return read_data.get_accelerometer_data(self.source)

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
            return dict(R_strikes=[], R_toeoffs=[], L_strikes=[], L_toeoffs=[],
                        valid=set(), R_strikes_plate=[], L_strikes_plate=[])

    def set_norm_cycle(self, cycle=None):
        """ Set normalization cycle (int for cycle index or a Gaitcycle
        instance). None to get unnormalized data. Affects the data returned
        by __getitem__ """
        if isinstance(cycle, int):
            if cycle >= len(self.cycles) or cycle < 0:
                raise ValueError('No such cycle')
            cycle = self.cycles[cycle]
            self._normalize = cycle
        elif isinstance(cycle, Gaitcycle):
            self._normalize = cycle
        elif isinstance(cycle, Noncycle):
            self._normalize = None

    def get_cycles(self, cyclespec):
        """ Get specified gait cycles (Gaitcycle instances) from the trial.
        cyclespec: 'all' | 'forceplate' | Gaitcycle | int | list of int |
                    list of Gaitcycle | tuple
        Corresponding to: all cycles | cycles starting with forceplate
        contact | cycle number | list of cycle numbers | tuple
        of the above options.
        In case of tuple, it will return the first condition of the tuple that
        has corresponding cycles.

        Alternatively, dict with keys 'R' and 'L' and values as above, to give
        separate cyclespecs for left and right.
        Returns list of gaitcycle instances.
        XXX: cycle numbering is now zero-based
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

        return cycs_ok

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
