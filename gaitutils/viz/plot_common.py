# -*- coding: utf-8 -*-
"""

Plotting functionality shared between backends.

@author: Jussi (jnu@iki.fi)
"""


from builtins import str
from builtins import next
from past.builtins import basestring
from itertools import cycle
from collections import defaultdict, namedtuple
import datetime
import logging
import numpy as np

from .. import models
from ..config import cfg
from ..envutils import GaitDataError


logger = logging.getLogger(__name__)


def _get_trial_cycles(trial, cycles, max_cycles):
    """Get the specified cycles from a trial"""
    model_cycles = trial.get_cycles(
        cycles['model'], max_cycles_per_context=max_cycles['model']
    )
    marker_cycles = trial.get_cycles(
        cycles['marker'], max_cycles_per_context=max_cycles['marker']
    )
    emg_cycles = trial.get_cycles(
        cycles['emg'], max_cycles_per_context=max_cycles['emg']
    )
    allcycles = list(set.union(set(model_cycles), set(marker_cycles), set(emg_cycles)))
    if not allcycles:
        logger.debug('trial %s has no cycles of specified type' % trial.trialname)
    logger.debug(
        'got total of %d cycles for %s (%d model, %d marker, %d EMG)'
        % (
            len(allcycles),
            trial.trialname,
            len(model_cycles),
            len(marker_cycles),
            len(emg_cycles),
        )
    )
    Cyclebunch = namedtuple(
        'Cyclebunch', 'allcycles, model_cycles, marker_cycles, emg_cycles'
    )
    return Cyclebunch(allcycles, model_cycles, marker_cycles, emg_cycles)


def _emg_yscale(emg_mode):
    """Compute EMG y range for plotting"""
    if emg_mode == 'rms':
        emg_yrange = np.array([0, cfg.plot.emg_yscale]) * cfg.plot.emg_multiplier
    else:
        emg_yrange = (
            np.array([-cfg.plot.emg_yscale, cfg.plot.emg_yscale])
            * cfg.plot.emg_multiplier
        )
    return emg_yrange


def _color_by_params(spec, mapper, trial, cyc, context, dimension=None):
    """Helper to return a color.

    spec is colorspec and mapper is a color mapper. Returns color according to
    trial, context etc., depending on what spec says. Depending on spec, color
    may come from the mapper or elsewhere (e.g. config). 'dimension' refers to
    variable dimension in case of multidimensional vars (e.g. markers).
    """
    if spec == 'session':
        return mapper[trial.sessiondir]
    elif spec == 'trial':
        return mapper[trial]
    elif spec == 'cycle':
        return mapper[cyc]
    elif spec == 'context':
        return cfg.plot.context_colors[context]
    elif spec == 'dimension':
        return mapper[dimension]
    elif spec is None:
        return mapper[None]
    else:
        raise RuntimeError('Unexpected colorspec: %s' % spec)


def _style_by_params(spec, mapper, trial, cyc, context, dimension=None):
    """Helper to return a style.

    See above for details."""
    if spec == 'session':
        return mapper[trial.sessiondir]
    elif spec == 'trial':
        return mapper[trial]
    elif spec == 'cycle':
        return mapper[cyc]
    elif spec == 'context':
        return mapper[context]
    elif spec == 'dimension':
        return mapper[dimension]
    elif spec is None:
        return mapper[None]
    else:
        raise RuntimeError('Unexpected colorspec: %s' % spec)


def _cyclical_mapper(it):
    """Map iterator to keys cyclically.

    Example:
    colors = ['red', 'blue', 'yellow']
    mapper = _cyclical_mapper(colors)
    mapper['foo']  # red
    mapper['bar']  # blue
    mapper['baz']  # yellow
    mapper['zzz']  # red (iterator cycles over)
    mapper['foo']  # red (old mappings are preserved)
    """
    cyc_it = cycle(it)
    return defaultdict(lambda: next(cyc_it))


def _handle_cyclespec(cycles):
    """Handle cyclespec argument to plotter functions"""
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
    vals_ok = set(('session', 'trial', 'context', 'dimension', None))
    style_by_defaults = cfg.plot.style_by
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

    color_by_defaults = cfg.plot.color_by
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
    """Map style argument from matplotlib to plotly"""
    return {'-': 'solid', '--': '5px', '-.': 'dashdot', ':': '2px'}[style]


def _var_title(var):
    """Get proper title for a variable"""
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
    """Shorten trial name"""
    tname_split = trialname.split('_')
    try:  # see if trial begins with valid date
        datetxt = '-'.join(tname_split[:3])
        d = datetime.datetime.strptime(datetxt, '%Y-%m-%d')
    except ValueError:
        # if trial was not named as expected, do nothing
        return trialname
    if len(tname_split) >= 5:
        # trialname is probably of the standard form:
        # yyyy_mm_dd_measinfo_sessioninfo1_sessioninfo2_trialn
        measinfo = tname_split[3]
        if len(tname_split) > 5:
            # pick all sessioninfo strings
            sessioninfo = '/'.join(tname_split[4:-1])
        else:
            sessioninfo = ''
        s = '%d/%d %s' % (d.month, d.year, measinfo)
        if sessioninfo:
            s += '/%s' % sessioninfo
        return s
    else:
        return trialname


def _get_cycle_name(trial, cyc, name_type):
    """Return descriptive name for a gait cycle"""
    if name_type == 'name_with_tag':
        cyclename = '%s/%s' % (trial.trialname, trial.eclipse_tag)
    elif name_type == 'short_name_with_tag':
        cyclename = '%s / %s' % (
            _truncate_trialname(trial.trialname),
            trial.eclipse_tag,
        )
    elif name_type == 'short_name_with_tag_and_cycle':
        cyclename = _truncate_trialname(trial.trialname)
        if trial.eclipse_tag is not None:
            cyclename += ' %s/%s' % (trial.eclipse_tag, cyc.name)
    elif name_type == 'tag_only':
        cyclename = trial.eclipse_tag
    elif name_type == 'tag_with_cycle':
        cyclename = '%s/%s' % (trial.eclipse_tag, cyc.name)
    elif name_type == 'full':
        cyclename = '%s/%s' % (trial.name_with_description, cyc.name)
    elif name_type == 'short_name_with_cyclename':
        cyclename = '%s/%s' % (_truncate_trialname(trial.trialname), cyc.name)
    else:
        raise ValueError('Invalid name_type')
    return cyclename


def _triage_var(var, trial):
    """Return category of variable (model, marker etc.).

    Returns 'model', 'marker' or 'emg' for known types,
    'unknown' if type cannot be inferred, None for None
    """
    categs = {'model': False, 'marker': False, 'emg': False}
    if var is None:
        return None
    if models.model_from_var(var):
        categs['model'] = True
    if var in trial._full_marker_data:
        categs['marker'] = True
    if var in cfg.emg.channel_labels:
        categs['emg'] = True
    if list(categs.values()).count(True) > 1:
        categs_matching = [key for key, val in categs.items() if val]
        raise GaitDataError(
            'ambiguous variable name %s (matches categories %s)'
            % (var, categs_matching)
        )
    else:
        for k, v in categs.items():
            if v:
                return k
        return 'unknown'
