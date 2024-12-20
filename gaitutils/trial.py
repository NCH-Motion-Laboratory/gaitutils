# -*- coding: utf-8 -*-
"""
Created on Tue Mar 17 14:41:31 2015

Read gait trials.

@author: Jussi (jnu@iki.fi)
"""


from collections import defaultdict
import numpy as np
from scipy.interpolate import interp1d
import re
import logging
from pathlib import Path
from copy import copy

from .emg import EMG
from .config import cfg
from .envutils import GaitDataError
from .events import GaitEvents
from . import (
    read_data,
    nexus,
    utils,
    eclipse,
    models,
    videos,
    sessionutils,
)

logger = logging.getLogger(__name__)


def nexus_trial(from_c3d=False):
    """Return Trial instance created from the currently open Nexus trial.

    Parameters
    ----------
    from_c3d : bool
        If True, try to read the trial data from the corresponding c3d file.
        If False, read via Nexus API (slower).

    Returns
    -------
    Trial
        A Trial instance.
    """
    vicon = nexus.viconnexus()
    trname = vicon.GetTrialName()  # 2-tuple of (path, name)
    if not trname[1]:
        raise GaitDataError('No trial loaded in Nexus')
    if from_c3d:
        c3dfile = trname[0] / Path(trname[1]).with_suffix('.c3d')
        if c3dfile.is_file():
            logger.debug('loading Nexus trial via C3D')
            return Trial(c3dfile)
        else:
            logger.info(
                f'no c3d file {c3dfile} for currently loaded trial, loading '
                'directly from Nexus'
            )
            return Trial(nexus.viconnexus())
    else:
        return Trial(nexus.viconnexus())


class Noncycle:
    """Used in place of Gaitcycle when requesting unnormalized data.

    Has a context parameter, to facilitate plotting unnormalized data for left
    and right separately.

    Parameters
    ----------
    context : str
        Cycle context: 'R' or 'L' for right and left, respectively.
    trial : Trial
        The trial instance owning this cycle. Does not need to be set.
    """

    def __init__(self, context, trial=None):
        self.context = context
        self.trial = trial
        self.name = f'unnorm. ({context})'
        self.toeoffn = None
        self.on_forceplate = False
        self.start = 0  # to allow cycle sorting
        self.end = None


class Gaitcycle:
    """Gait cycle class.

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

    def __init__(
        self,
        start,
        end,
        toeoff,
        context,
        on_forceplate,
        plate_idx,
        smp_per_frame,
        trial=None,
        name=None,
        index=None,
    ):
        self.len = end - start  # length of cycle in frames
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
        self.toeoffn = int(round(100 * ((self.toeoff - self.start) / self.len)))
        self.trial = trial
        self.plate_idx = plate_idx
        self.index = index
        self.name = name

    def __repr__(self):
        s = '<Gaitcycle |'
        s += f' start: {self.start}, '
        s += f' end: {self.end}, '
        s += f' context: {self.context}, '
        s += ' on forceplate,' if self.on_forceplate else ' not on forceplate,'
        s += f' toeoff: {self.toeoff}'
        s += '>'
        return s

    def normalize(self, var):
        """Normalize (columns of) frames-based variable var to the cycle.

        Parameters
        ----------
        var : ndarray
            NxM array of frame-based data to normalize. N is the number of frames.

        Returns
        -------
        tuple
            A tuple of (tn, ndata) where tn is the normalized time (0..100%) and ndata
            is the normalized data.
        """
        if self.end > var.shape[0]:
            raise GaitDataError('Cycle frame numbers exceed the available data')
        # convert 1D arrays to 2D
        if len(var.shape) == 1:
            var = var[:, np.newaxis]
        ncols = var.shape[1]
        idata = np.array(
            [
                interp1d(self.t, var[self.start : self.end, k], kind='quadratic')(self.tn)
                for k in range(ncols)
            ]
        ).T
        return self.tn, np.squeeze(idata)

    def crop_analog(self, var):
        """Crop analog variable (EMG, forceplate, etc. ) to the gait cycle.

        Parameters
        ----------
        var : ndarray
            NxM array of analog data to normalize.
        """
        return self.tn_analog, var[self.start_smp : self.end_smp]


class Trial:
    """Gait trial class.

    Represents a single gait trial (Nexus trial or C3D file).
    Used as a container for gait data, gait cycles and related metadata.

    Parameters
    ----------
    source : str | Path | instance of ViconNexus
        Source to read the data from. Can be a c3d file or a ViconNexus SDK object.

    Attributes
    ----------
    trialname : str
        Name of trial.
    eclipse_data : dict
        Vicon Eclipse data for the trial. Keys are Eclipse fields and values are
        the corresponding data.
    sessionpath : Path
        Path to session directory.
    length : int
        Trial length in frames.
    offset : int
        Offset of events from beginning of trial (in frames). Gaitutils
        internally stores events as zero-based, i.e. event at 0 means an event
        at first frame. Thus, these events can be used directly to index e.g.
        marker and model data arrays. To recover the original indices of events,
        you can add the offset. For example, the offset for Nexus is always 1
        (Nexus uses 1-based index for the frames). Thus, a gaitutils event at
        frame 0 occurs in Nexus at frame 1. For C3D files, the offset is
        variable.
    framerate : float
        Frame rate for capture (frames / sec).
    analograte : float
        Sampling rate for analog devices (samples / sec)-
    name : str
        Subject name.
    subj_params : dict
        Other subject parameters (bodymass etc.)
    events : GaitEvents
        Trial events (foot strikes, toeoffs etc.).
    """

    def __repr__(self):
        s = '<Trial |'
        s += f' trial: {self.trialname}'
        s += f', data source: {self.source}'
        s += f', subject: {self.subject_name}'
        s += f', gait cycles: {self.ncycles}'
        s += '>'
        return s

    def __init__(self, source):
        logger.debug(f'new trial instance from {source}')
        self.source = source
        self._source_is_nexus = nexus._is_vicon_instance(source)
        meta = read_data.get_metadata(source)
        # to avoid boilerplate, insert the metadata directly as instance
        # attributes
        self.__dict__.update(meta)
        # just in case, let's keep the original events (unmodified by forceplate data)
        self._raw_events = copy(self.events)
        if self.length == 1:
            raise GaitDataError('Cannot deal with single-frame trials (yet)')
        self.sessiondir = self.sessionpath.name
        # try to locate trial .enf (we do not require it)
        enfpath = self.sessionpath / Path(self.trialname).with_suffix('.Trial.enf')
        # also look for alternative (older style?) enf name
        if not enfpath.is_file():
            trialn_re = re.search('\.*(\d*)$', self.trialname)
            trialn = trialn_re.group(1)
            if trialn:
                trialname_ = f'{self.trialname}.Trial{trialn}.enf'
                enfpath = self.sessionpath / trialname_
        self.enfpath = enfpath
        if self.enfpath.is_file():
            logger.debug(f'reading Eclipse info from {self.enfpath}')
            edata = eclipse.get_eclipse_keys(self.enfpath)
            # for convenience, eclipse_data returns '' for nonexistent keys
            self.eclipse_data = defaultdict(lambda: '', edata)
        else:
            logger.debug('no .enf file found')
            self.eclipse_data = defaultdict(lambda: '', {})
        # heuristic for static trials
        self.is_static = self.eclipse_data['TYPE'].upper() == 'STATIC'
        # handle session quirks
        self._handle_quirks()
        # data are lazily read
        self.emg = EMG(
            self.source,
            correction_factor=self.emg_correction_factor,
            chs_disabled=self.emg_chs_disabled,
        )
        self._forceplate_data = None
        self._marker_data = None
        # read forceplate events and update the event data, since we need to
        # know which gait cycles start on a forceplate
        if not self.is_static:
            logger.debug('updating events with forceplate info')
            self.fp_events = self._get_fp_events()
            self.events.merge_forceplate_events(self.fp_events)
        else:
            self.fp_events = GaitEvents()
        self._models_data = dict()
        self.stddev_data = None  # AvgTrial only
        # frames 0...length
        self.t = np.arange(self.length)
        # analog frames 0...length
        self.t_analog = np.arange(self.length * self.samplesperframe)
        # normalized x-axis of 0, 1, 2 .. 100%
        self.tn = np.linspace(0, 100, 101)
        self.samplesperframe = self.analograte / self.framerate
        # create the gait cycles
        if not self.is_static:
            self.cycles = self._scan_cycles()
        else:
            self.cycles = list()
        self.ncycles = len(self.cycles)

    def _check_nexus_trial_still_valid(self):
        """Check if Nexus still has the original trial loaded.

        Lazy reads using Vicon Nexus are problematic, since the Nexus trial may
        change at any time due to e.g. user actions. Thus we should try to
        ensure that the original trial instance is still loaded in Nexus.
        """
        nexus._check_nexus_trial_identity(self.sessionpath, self.trialname)

    def _handle_quirks(self):
        """Handle session quirks"""
        quirks = sessionutils.load_quirks(self.sessionpath)
        if 'emg_chs_disabled' in quirks:
            self.emg_chs_disabled = quirks['emg_chs_disabled']
            logger.warning(
                f"using quirk: disable EMG channels {quirks['emg_chs_disabled']}"
            )
        else:
            self.emg_chs_disabled = None
        if 'emg_correction_factor' in quirks:
            self.emg_correction_factor = quirks['emg_correction_factor']
            logger.warning(
                f'using quirk: EMG correction factor = {self.emg_correction_factor:g}'
            )
        else:
            self.emg_correction_factor = 1
        if 'ignore_eclipse_fp_info' in quirks:
            logger.warning('using quirk: ignore Eclipse forceplate fields')
            self.use_eclipse_fp_info = False
        else:
            self.use_eclipse_fp_info = True

    @property
    def eclipse_tag(self):
        """Return the first matching Eclipse tag for the trial.

        The configured Eclipse fields (e.g. DESCRIPTION) are searched for the configured
        tags. If a configured tag is found, the it will be returned.

        Returns
        -------
        tag : str
            The tag.
        """
        for tag in cfg.eclipse.tags:
            if any([tag in self.eclipse_data[fld] for fld in cfg.eclipse.tag_keys]):
                return tag
        return None

    @property
    def name_with_description(self):
        """Return the trial name with Eclipse DESCRIPTION and NOTES keys.

        Returns
        -------
        desc : str
            The trial name and description.
        """
        s = self.trialname
        if self.eclipse_data['DESCRIPTION'] or self.eclipse_data['NOTES']:
            s += ' ('
            if self.eclipse_data['DESCRIPTION']:
                s += self.eclipse_data['DESCRIPTION']
            if self.eclipse_data['DESCRIPTION'] and self.eclipse_data['NOTES']:
                s += ','
            if self.eclipse_data['NOTES']:
                s += self.eclipse_data['NOTES']
            s += ')'
        return s

    def normalize_to_cycle(self, data, cycle):
        """Normalize frame-based data to a gait cycle.

        Parameters
        ----------
        data : ndarray
            A Nxd ndarray, where N is number of frames and d is number of variables.
        cycle : Gaitcycle | Noncycle | None | int
            The gait cycle to normalize to. If Noncycle or None, returns unnormalized
            data. If int, return nth cycle from the trial cycles list.
        """
        if isinstance(cycle, int):
            if cycle >= len(self.cycles) or cycle < 0:
                raise ValueError('No such cycle')
            cycle = self.cycles[cycle]
        if isinstance(cycle, Gaitcycle):
            t, data = cycle.normalize(data)
        elif cycle is None or isinstance(cycle, Noncycle):
            # return unnormalized time axis and data as it is
            t = self.t
        else:
            raise ValueError('invalid type for cycle argument')
        return t, data

    def normalize_analog_to_cycle(self, data, cycle):
        """Normalize analog data to a gait cycle.

        Parameters
        ----------
        data : (Nxd) ndarray
            The data, where N is number of samples and d is number of variables.
        cycle : Gaitcycle | Noncycle | None
            The gait cycle to normalize to. If Noncycle or None, returns unnormalized
            data. If int, return nth cycle from the trial cycles list.
        """
        if isinstance(cycle, int):
            if cycle >= len(self.cycles) or cycle < 0:
                raise ValueError('No such cycle')
            cycle = self.cycles[cycle]
        if isinstance(cycle, Gaitcycle):
            t, data = cycle.crop_analog(data)
        elif cycle is None or isinstance(cycle, Noncycle):
            # return unnormalized time axis and data as it is
            t = self.t_analog
        else:
            raise ValueError('invalid type for cycle argument')
        return t, data

    @property
    def _full_marker_data(self):
        """Return the full marker data dict."""
        if self._marker_data is None:
            if self._source_is_nexus:
                self._check_nexus_trial_still_valid()
            self._marker_data = read_data.get_marker_data(self.source, self.markers)
        return self._marker_data

    def _get_modelvar(self, var):
        """Return (unnormalized) data for a model variable."""
        model_ = models.model_from_var(var)
        if not model_:
            raise ValueError(f'No model found for {var}')
        if model_.desc not in self._models_data:
            # read and cache model data
            if self._source_is_nexus:
                self._check_nexus_trial_still_valid()
            modeldata = read_data.get_model_data(self.source, model_)
            self._models_data[model_.desc] = modeldata
        return self._models_data[model_.desc][var]

    def get_model_data(self, var, cycle=None):
        """Return trial data for a model variable.

        Parameters
        ----------
        var : string
            The name of the model variable (e.g. 'LHipMomentX')
        cycle : Gaitcycle
            The cycle to normalize to. None for no normalization.

        Returns
        -------
        t_data : tuple
            Tuple of (t, data) where t is the time axis as 1-dim ndarray, and data
            is the model variable data as 1-dim ndarray.
        """
        data = self._get_modelvar(var)
        return self.normalize_to_cycle(data, cycle)

    def get_emg_data(self, ch, cycle=None, envelope=False):
        """Return trial data for an EMG channel.

        Uses 'fuzzy' name matching: if the specified channel is not found in the
        data, partial name matches are considered and data for the shortest
        match is returned. For example, if ch == 'LGas' and the data has
        channels 'Voltage.LGas8' and 'Voltage.LGas8_dummy', the former is
        returned.

        Parameters
        ----------
        ch : string
            The EMG channel name. Fuzzy name matching is used.
        envelope : bool
            Return envelope of data. The envelope is computed as either RMS or
            linear envelope, according to settings in the config.

        Returns
        -------
        t_data : tuple
            Tuple of (t, data) where t is the time axis as 1-dim ndarray, and
            data is the EMG data as 1-dim ndarray.
        """
        data = self.emg.get_channel_data(ch, envelope=envelope)
        return self.normalize_analog_to_cycle(data, cycle)

    def get_marker_data(self, marker, cycle=None):
        """Return position data for a given marker.

        Parameters
        ----------
        marker : string
            The marker name.

        Returns
        -------
        t_data : tuple
            Tuple of (t, data) where t is the time axis as (Nt,) -shape ndarray, and data
            is the marker data as a (Nt, 3) ndarray.
        """
        data = self._full_marker_data[marker]
        return self.normalize_to_cycle(data, cycle)

    def get_forceplate_data(self, nplate, kind='force', cycle=None):
        """Return forceplate data.

        Parameters
        ----------
        nplate : int
            The forceplate index. Plates are numbered starting from 0, i.e.
            nplate=0 corresponds to Nexus plate 1.
        kind : str
            The type of data to return. Can be 'force', 'moment', or 'cop'
            (center of pressure).

        Returns
        -------
        t_data : tuple
            Tuple of (t, data) where t is the time axis as (Nt,) -shape ndarray,
            and data is the marker data as a (Nt, 3) ndarray.
        """
        if not self._forceplate_data:
            if self._source_is_nexus:
                self._check_nexus_trial_still_valid()
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
        return self.normalize_analog_to_cycle(data, cycle)

    def get_accelerometer_data(self):
        """Return accelerometer data."""
        raise NotImplementedError

    def _get_fp_events(self):
        """Read the forceplate events."""
        try:
            if cfg.trial.use_eclipse_fp_info and self.use_eclipse_fp_info:
                fp_info = eclipse._eclipse_forceplate_keys(self.eclipse_data)
            else:
                fp_info = None
            marker_data = self._full_marker_data
            return utils.detect_forceplate_events(
                self.source, marker_data=marker_data, eclipse_fp_info=fp_info
            )
        except GaitDataError:
            logger.warning('Could not detect forceplate events')
            return GaitEvents()  # return empty events

    def get_cycles(self, cyclespec, max_cycles_per_context=None):
        """Get specified gait cycles from the trial.

        Takes a specification for the desired gait cycles and returns a list of
        Gaitcycle instances.

        Parameters
        ----------
        cyclespec : dict | str | int | tuple | list | None
            The cycles to get. For a context specific cyclespec, supply a dict with keys:
            'R' and 'L', values: cyclespec as below. If not a dict, the same cyclespec
            will be applied to both contexts.
            For string args: 'all' gets all trial cycles. 'forceplate' gets cycles
            starting with valid forceplate contact. 'unnormalized' (or None) gets a
            Noncycle that indicates a request for unnormalized data.
            If int or a list of int, get the cycle(s) with given indices.
            Note that cycle numbering starts from 0.
            A tuple can be used to try different cyclespecs and return the first
            one that has matching cycle. For example, ('forceplate', 0) would return
            forceplate cycles if any, and the first cycle otherwise.

        max_cycles_per_context : int | None
            Maximum number of cycles returned per context. Forceplate cycles are
            given priority.

        Returns
        -------
        list
            List of Gaitcycle instances, sorted by starting frame.
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
                return [Noncycle(context=context, trial=self)]
            elif cyclespec == 'all':
                return cycles
            elif cyclespec == 'forceplate':  # all forceplate cycles
                return [c for c in cycles if c.on_forceplate]
            elif isinstance(cyclespec, tuple):
                # recurse until we have cycles (or cyclespec is exhausted)
                if not cyclespec:
                    return []
                else:
                    return _filter_cycles(
                        cycles, context, cyclespec[0]
                    ) or _filter_cycles(cycles, context, cyclespec[1:])
            else:
                raise TypeError('Invalid argument')

        def _limit_cycles(cycles, n):
            """Limit the number of cycles to n. Prioritize forceplate cycles"""
            if n is None or n >= len(cycles):
                cycs_ok = cycles
            else:
                fp_cycs = [c for c in cycles if c.on_forceplate]
                if len(fp_cycs) >= n:
                    cycs_ok = fp_cycs[:n]
                else:
                    non_fp_cycs = [c for c in cycles if not c.on_forceplate]
                    n_fp_cycs = n - len(fp_cycs)
                    cycs_ok = fp_cycs + non_fp_cycs[:n_fp_cycs]
            return cycs_ok

        if not isinstance(cyclespec, dict):
            cyclespec = {'R': cyclespec, 'L': cyclespec}

        cycs_ok = list()
        for context in cyclespec:
            # pick trial cycles for this context
            cycles_ = [c for c in self.cycles if c.context == context.upper()]
            # filter them according to cyclespec
            good_cycles = _filter_cycles(cycles_, context, cyclespec[context])
            good_cycles = _limit_cycles(good_cycles, max_cycles_per_context)
            cycs_ok.extend(good_cycles)

        return sorted(cycs_ok, key=lambda cyc: cyc.start)

    def _scan_cycles(self):
        """Make gait cycles based on foot strike and toeoff events"""

        cycles = list()

        for context, context_desc in utils.get_contexts():
            strike_events = self.events.get_events('strike', context)
            toeoff_events = self.events.get_events('toeoff', context)
            toeoff_frames = [ev.frame for ev in toeoff_events]

            # this relies on events being sorted by frame (but they should be)
            for k, (ev0, ev1) in enumerate(zip(strike_events[:-1], strike_events[1:])):
                on_forceplate = ev0.forceplate_index is not None
                fp_str = ' (f)' if on_forceplate else ''
                cyclename = f'{context_desc}{k+1}{fp_str}'
                start, end = ev0.frame, ev1.frame
                toeoff = [fr for fr in toeoff_frames if fr > start and fr < end]
                if len(toeoff) == 0:
                    if cfg.trial.no_toeoff == 'error':
                        raise GaitDataError(
                            '%s: no toeoff for cycle starting at %d'
                            % (self.trialname, start)
                        )
                    elif cfg.trial.no_toeoff == 'reject':
                        logger.warning(
                            'no toeoff for cycle starting at %d, rejecting cycle'
                            % start
                        )
                        continue
                    else:
                        raise RuntimeError('invalid no_toeoff parameter in config')
                elif len(toeoff) > 1:
                    if cfg.trial.multiple_toeoffs == 'error':
                        raise GaitDataError(
                            '%s: multiple toeoffs for cycle starting at %d'
                            % (self.trialname, start)
                        )
                    elif cfg.trial.multiple_toeoffs == 'accept_first':
                        logger.warning(
                            'multiple toeoffs for cycle starting at %d, picking the first one'
                            % start
                        )
                        toeoff = toeoff[0]
                    elif cfg.trial.multiple_toeoffs == 'reject':
                        logger.warning(
                            'multiple toeoffs for cycle starting at %d, skipping cycle'
                            % start
                        )
                        continue
                    else:
                        raise RuntimeError(
                            'invalid multiple_toeoffs parameter in config'
                        )
                else:
                    toeoff = toeoff[0]

                cyc = Gaitcycle(
                    start,
                    end,
                    toeoff,
                    context,
                    on_forceplate,
                    ev0.forceplate_index,
                    self.samplesperframe,
                    trial=self,
                    index=k + 1,
                    name=cyclename,
                )
                cycles.append(cyc)

        return cycles
