# -*- coding: utf-8 -*-
"""

plotting functionality shared between backends

@author: Jussi (jnu@iki.fi)
"""


from builtins import str
from builtins import next
from past.builtins import basestring
from builtins import object
import datetime
import logging
import copy

from gaitutils import models, cfg


logger = logging.getLogger(__name__)


class IteratorMapper(object):
    """Map iterator values to keys. If key has been seen, previously mapped
    value is reused. Otherwise new value is taken from the iterator."""

    def __init__(self, iterator):
        self._iterator = iterator
        self._prop_dict = dict()

    def __repr__(self):
        s = '<IteratorMapper|'
        s += str(self._prop_dict)
        return s

    def get_prop(self, key):
        if key in self._prop_dict:
            return self._prop_dict[key]
        else:
            prop = next(self._iterator)
            self._prop_dict[key] = prop
            return prop


def _handle_cyclespec(cycles):
    """Handle cyclespec argument"""
    default_cycles = cfg.plot.default_cycles
    if cycles == 'unnormalized':
        cycles = {vartype: 'unnormalized' for vartype in default_cycles}
    elif cycles is None:
        cycles = default_cycles
    elif isinstance(cycles, dict):
        if set(cycles) - set(default_cycles):  # unknown keys
            raise ValueError('invalid cycle argument')
        _defcycles = default_cycles.copy()
        _defcycles.update(cycles)
        cycles = _defcycles
    else:
        raise ValueError('invalid cycle argument')
    return cycles


def _handle_style_and_color_args(style_by, color_by):
    """Handle style and color choice"""
    vals_ok = set(('session', 'trial', 'context', None))

    style_by_defaults = {'model': cfg.plot.model_style_by}
    if style_by is None:
        style_by = dict()
    elif isinstance(style_by, basestring):
        style_by = {'model': style_by}
    elif not isinstance(style_by, dict):
        raise TypeError('style_by must be str or dict')
    for k in set(style_by_defaults) - set(style_by):
        style_by[k] = style_by_defaults[k]  # update missing values
    if not set(style_by.values()).issubset(vals_ok):
        raise ValueError('invalid style_by argument in %s' % style_by.items())
    
    color_by_defaults = {'model': cfg.plot.model_color_by, 'emg': cfg.plot.emg_color_by}
    if color_by is None:
        color_by = dict()
    elif isinstance(color_by, basestring):
        color_by = {'model': color_by, 'emg': color_by}
    elif not isinstance(color_by, dict):
        raise TypeError('color_by must be str or dict')
    for k in set(color_by_defaults) - set(color_by):
        color_by[k] = color_by_defaults[k]  # update missing values
    if not set(color_by.values()).issubset(vals_ok):
        raise ValueError('invalid color_by argument in %s' % color_by.items())

    return style_by, color_by


def _style_mpl_to_plotly(style):
    """Style mapper matplotlib -> plotly"""
    return {'-': 'solid', '--': '5px', '-.': 'dashdot', '..': '2px'}[style]


def _var_title(var):
    """Get proper title for variable"""
    mod = models.model_from_var(var)
    if mod:
        if var in mod.varlabels_noside:
            return mod.varlabels_noside[var]
        elif var in mod.varlabels:
            return mod.varlabels[var]
    elif var in cfg.emg.channel_labels:
        return cfg.emg.channel_labels[var]
    else:
        return var


def _truncate_trialname(trialname):
    """Shorten trial name."""
    try:
        # try to truncate date string of the form yyyy_mm_dd
        tn_split = trialname.split('_')
        datetxt = '-'.join(tn_split[:3])
        d = datetime.datetime.strptime(datetxt, '%Y-%m-%d')
        return '%d..%s' % (d.year, '_'.join(tn_split[3:]))
    except ValueError:  # trial was not named as expected
        return trialname


def _get_cycle_name(trial, cycle, name_type):
    """Return descriptive name for a gait cycle"""
    if name_type == 'name_with_tag':
        cyclename = '%s / %s' % (trial.trialname,
                                 trial.eclipse_tag)
    elif name_type == 'short_name_with_tag':
        cyclename = '%s / %s' % (_truncate_trialname(trial.trialname),
                                 trial.eclipse_tag)
    elif name_type == 'short_name_with_tag_and_cycle':
        cyclename = '%s / %s %s' % (_truncate_trialname(trial.trialname),
                                    trial.eclipse_tag, cycle.name)
    elif name_type == 'tag_only':
        cyclename = trial.eclipse_tag
    elif name_type == 'tag_with_cycle':
        cyclename = '%s / %s' % (trial.eclipse_tag,
                                 cycle.name)
    elif name_type == 'full':
        cyclename = '%s / %s' % (trial.name_with_description,
                                 cycle.name)
    elif name_type == 'short_name_with_cyclename':
        cyclename = '%s / %s' % (_truncate_trialname(trial.trialname),
                                 cycle.name)
    else:
        raise ValueError('Invalid name_type')
    return cyclename
