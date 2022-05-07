# -*- coding: utf-8 -*-
"""

Gait events.

@author: Jussi (jnu@iki.fi)
"""

from dataclasses import dataclass
from itertools import product
import logging


logger = logging.getLogger(__name__)


@dataclass
class GaitEvent:
    """A gait event.

    Events are usually either foot strike or toeoff, but we also support a
    "general" event. Events can have a context: either right foot, left foot or
    None (mostly useful for general events).

    Events occur at a given frame. We use 0-based frame numbering. Thus, frames
    can directly be used to index data arrays (model data, marker data etc.)
    read from the source. Due to this choice, frame numbers stored by this class
    usually differ from the frames shown in Nexus or in C3D files. When events
    are read by reader functions, the frames are automatically corrected for the
    Nexus or C3D offset. If needed, the offset is available in the Nexus or C3D
    metadata.

    Foot strike and toeoff events may occur on a forceplate. For such events,
    the forceplate_index can be set. This index is also 0-based.

    This class only stores event data, so it's defined as a dataclass.
    """

    _event_types = ['strike', 'toeoff', 'general']  # supported event types
    _contexts = [None, 'L', 'R']  # supported context values
    frame: int  # the frame of occurence
    event_type: str  # the type of event
    context: str = None  # the context
    forceplate_index: int = None  # forceplate index

    def __post_init__(self):
        """Validate arguments"""
        if self.context not in GaitEvent._contexts:
            raise ValueError('Invalid context')
        if self.event_type not in GaitEvent._event_types:
            raise ValueError('Invalid event type')
        if not isinstance(self.frame, int):
            raise TypeError(f'Frame needs to be an int (not {type(self.frame)})')
        if self.forceplate_index is not None:
            if self.context is None:
                raise ValueError('forceplate events are required to have a context')
            if not isinstance(self.forceplate_index, int) or self.forceplate_index < 0:
                raise ValueError('forceplate index needs to be an integer > 0')


class GaitEvents:
    """A collection of gait events (GaitEvent instances).

    This class stores events, allows getting them by their properties and offers
    a few utility functions.
    """

    def __init__(self):
        self._events = list()

    def __repr__(self) -> str:
        s = '<GaitEvents |\n'
        for ev in self.get_events():
            s += repr(ev)
            s += '\n'
        s += '>'
        return s

    def append(self, event):
        """Append a gait event.

        Parameters
        ----------
        event : GaitEvent
            The event to add.
        """
        if not isinstance(event, GaitEvent):
            raise ValueError('append() can only accept GaitEvent instances')
        self._events.append(event)
        self._events.sort(key=lambda ev: ev.frame)  # keep events sorted

    @staticmethod
    def _filter_context(events, context):
        for ev in events:
            if ev.context == context:
                yield ev

    @staticmethod
    def _filter_type(events, ev_type):
        for ev in events:
            if ev.event_type == ev_type:
                yield ev

    @staticmethod
    def _filter_forceplate(events):
        for ev in events:
            if ev.forceplate_index is not None:
                yield ev

    def get_events(self, event_type=None, context=None, forceplate=None):
        """Get desired events.

        Parameters
        ----------
        event_type : str | None
            The desired event type. If None, include all event types.
        context : str | None
            The desired context. If None, include all.
        forceplate : bool | None
            If True, get forceplate events only. If None, get all events.

        Returns
        -------
        list
            List of GaitEvent instances.
        """
        events = self._events
        if event_type is not None:
            events = self._filter_type(events, event_type)
        if context is not None:
            events = self._filter_context(events, context)
        if forceplate is not None:
            events = self._filter_forceplate(events)
        return list(events)

    def merge_forceplate_events(self, fp_events, adjust_frames=False):
        """Read forceplate-based event info and update our events.

        Nexus and C3D events do not include any info about forceplates. Thus,
        forceplate contacts have to be detected separately. This method can be
        used to update events with information from forceplate detected events.
        A tolerance of FRAME_TOL is used to determine if the events are "the
        same".

        For example, if self.events includes a foot strike at frame 100 and
        fp_events has a foot strike on forceplate 0 at frame 101, the foot
        strike at frame 100 will be updated with the forceplate index.

        If adjust_frames is True, the event frames will be adjusted according to
        the forceplate data (which is usually regarded as the golden standard).
        This option is not used when e.g. loading trials, so that user-defined
        events are kept as they are.

        Parameters
        ----------
        fp_events : GaitEvents
            The forceplate events.
        adjust_frames : bool
            If True, the frames of the events will be adjusted according to the
            forceplate data.
        """
        FRAME_TOL = 7
        for context in 'LR':
            for event_type in ['strike', 'toeoff']:
                events_this = self.get_events(event_type=event_type, context=context)
                fp_events_this = fp_events.get_events(
                    event_type=event_type, context=context
                )
                for ev, fp_ev in product(events_this, fp_events_this):
                    if abs(ev.frame - fp_ev.frame) < FRAME_TOL:
                        ev.forceplate_index = fp_ev.forceplate_index
                        if adjust_frames:
                            ev.frame = fp_ev.frame

    def get_forceplate_info(self, n_plates):
        """Return Eclipse-style forceplate info dict and a coded string.

        Parameters
        ----------
        n_plates : int
            Number of forceplates.

        Returns
        -------
        tuple
            A tuple of (fp_dict, fp_coded) where fp_dict contains Eclipse-style
            forceplate contact info. Example for three forceplates:
            {'FP1': 'Right', 'FP2': 'Invalid', 'FP3': 'Left'}
            fp_coded is the same info coded into a string, used by CGM2. 'X'
            marks invalid context. For the same data as the above dict it would
            be 'RXL'.
        """
        fp_dict = dict()
        coded = ''
        for ind in range(n_plates):
            strike_events = self.get_events(event_type='strike', forceplate=True)
            plate_strikes = [ev for ev in strike_events if ev.forceplate_index == ind]
            if plate_strikes:
                strike = plate_strikes[0]
                plate_context = 'Right' if strike.context == 'R' else 'Left'
                coded += strike.context
            else:
                plate_context = 'Invalid'
                coded += 'X'
            plate_name = f'FP{ind + 1}'  # Eclipse uses 1-based index
            fp_dict[plate_name] = plate_context
        return fp_dict, coded
