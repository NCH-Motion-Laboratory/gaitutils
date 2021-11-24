# -*- coding: utf-8 -*-
"""

Plotting functionality shared between backends.

@author: Jussi (jnu@iki.fi)
"""

from itertools import cycle
from collections import defaultdict, namedtuple
import logging
import numpy as np
from matplotlib import ticker

from .. import models, sessionutils
from ..config import cfg
from ..envutils import GaitDataError


logger = logging.getLogger(__name__)


def _tick_spacing(vmin, vmax, max_nticks=None):
    """Calculate tick spacing for a given max. number of ticks"""
    if max_nticks is None:
        max_nticks = 10
    locator = ticker.MaxNLocator(nbins=max_nticks - 1)
    return locator.tick_values(vmin, vmax)


def _var_unit(vardef):
    """Return unit for a vardef"""
    varname = vardef[0]
    themodel = models.model_from_var(varname)
    return themodel.units[varname]


def _nested_get(di, keys):
    """Get a value from a nested dict, using a list of keys"""
    for key in keys:
        di = di[key]  # iterate until we exhaust the nested keys
    return di


def _compose_varname(vardef):
    """Compose a variable name for extracted variable.

    E.g. ['HipAnglesX', 'peaks', 'swing', 'max']
    -> 'Hip flexion maximum during swing phase'
    """
    varname = vardef[0]
    # get variable description from gaitutils.models
    themodel = models.model_from_var(varname)
    name = themodel.varlabels_nocontext[varname]
    if vardef[1] == 'contact':
        name += ' at IC'
    elif vardef[1] in ['peaks', 'extrema']:
        phase = vardef[2]  # swing, stance etc.
        valtype = vardef[3]  # min, max etc.
        val_trans = {'max': 'max.', 'min': 'min.'}
        if phase == 'overall':
            name += f', {phase} {val_trans[valtype]}'
        else:
            name += f', {phase} phase {val_trans[valtype]}'
        if vardef[1] == 'peaks':
            name += ' peak'
    return name


def _get_trial_cycles(trial, cycles, max_cycles):
    """Get the specified cycles from a trial"""
    # supply missing values as None
    def_cycles = defaultdict(lambda: None)
    _max_cycles = def_cycles | max_cycles

    model_cycles = trial.get_cycles(
        cycles['model'], max_cycles_per_context=_max_cycles['model']
    )
    marker_cycles = trial.get_cycles(
        cycles['marker'], max_cycles_per_context=_max_cycles['marker']
    )
    emg_cycles = trial.get_cycles(
        cycles['emg'], max_cycles_per_context=_max_cycles['emg']
    )
    allcycles = list(set.union(set(model_cycles), set(marker_cycles), set(emg_cycles)))
    if not allcycles:
        logger.debug(f'trial {trial.trialname} has no cycles of specified type')
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
    if emg_mode == 'envelope':
        emg_yrange = (
            np.array([0, cfg.plot.emg_yscale])
            * cfg.plot.emg_multiplier
            * cfg.plot.emg_envelope_rel_yscale
        )
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
        raise RuntimeError(f'Unexpected colorspec: {spec}')


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
        raise RuntimeError(f'Unexpected colorspec: {spec}')


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
    if cycles in ['all', 'unnormalized']:
        cycles = {vartype: cycles for vartype in default_cycles}
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
    elif isinstance(style_by, str):
        style_by = {'model': style_by}
    elif not isinstance(style_by, dict):
        raise TypeError('style_by must be str or dict')
    for k in set(style_by_defaults) - set(style_by):
        style_by[k] = style_by_defaults[k]  # update missing values
    if not set(style_by.values()).issubset(vals_ok):
        raise ValueError(f'invalid style_by argument in {style_by.items()}')

    color_by_defaults = cfg.plot.color_by
    if color_by is None:
        color_by = dict()
    elif isinstance(color_by, str):
        color_by = {'model': color_by, 'emg': color_by}
    elif not isinstance(color_by, dict):
        raise TypeError('color_by must be str or dict')
    for k in set(color_by_defaults) - set(color_by):
        color_by[k] = color_by_defaults[k]  # update missing values
    if not set(color_by.values()).issubset(vals_ok):
        raise ValueError(f'invalid color_by argument in {color_by.items()}')

    return style_by, color_by


def _style_mpl_to_plotly(style):
    """Map style argument from matplotlib to plotly"""
    return {'-': 'solid', '--': '5px', '-.': 'dashdot', ':': '2px'}[style]


def _var_title(var):
    """Get proper title for a variable"""
    mod = models.model_from_var(var)
    if mod:
        if var in mod.varlabels_nocontext:
            return mod.varlabels_nocontext[var]
        elif var in mod.varlabels:
            return mod.varlabels[var]
    elif var in cfg.emg.channel_labels:
        return cfg.emg.channel_labels[var]
    else:
        return var


def _truncate_trialname(trialname):
    """Shorten trial name"""
    try:
        d, code, desc = sessionutils._parse_name(trialname)
    except ValueError:
        return trialname
    return '%d/%d %s %s' % (d.year, d.month, desc, code)


def _get_cycle_name(trial, cyc, name_type):
    """Return descriptive name for a gait cycle"""
    if name_type == 'name_with_tag':
        cyclename = f'{trial.trialname}/{trial.eclipse_tag}'
    elif name_type == 'short_name_with_tag':
        cyclename = f'{_truncate_trialname(trial.trialname)} / {trial.eclipse_tag}'
    elif name_type == 'short_name_with_tag_and_cycle':
        cyclename = _truncate_trialname(trial.trialname)
        if trial.eclipse_tag is not None:
            cyclename += f' {trial.eclipse_tag}/{cyc.name}'
    elif name_type == 'tag_only':
        cyclename = trial.eclipse_tag
    elif name_type == 'tag_with_cycle':
        cyclename = f'{trial.eclipse_tag}/{cyc.name}'
    elif name_type == 'full':
        cyclename = f'{trial.name_with_description}/{cyc.name}'
    elif name_type == 'short_name_with_cyclename':
        cyclename = f'{_truncate_trialname(trial.trialname)}/{cyc.name}'
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
            f'ambiguous variable name {var} (matches categories {categs_matching})'
        )
    else:
        for k, v in categs.items():
            if v:
                return k
        return 'unknown'
