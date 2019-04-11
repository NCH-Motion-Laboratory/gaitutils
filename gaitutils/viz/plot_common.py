# -*- coding: utf-8 -*-
"""

plotting functionality shared between backends

@author: Jussi (jnu@iki.fi)
"""


import datetime

from gaitutils import models, cfg


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
        return ''


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
