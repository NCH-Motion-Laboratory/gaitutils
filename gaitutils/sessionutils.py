# -*- coding: utf-8 -*-
"""
Patient info functions

FIXME: refactor session related funcs into session.py ?

@author: Jussi (jnu@iki.fi)
"""

import io
import os.path as op
import json

from .eclipse import get_eclipse_keys


def default_info():
    return dict(fullname=None, hetu=None, session_description=None)

    pdata = self._load_patient_data(session)
    pdata.update(patient_data)


def load_info(self, session):
    """Return the patient info dict from the given session"""
    fname = op.join(session, 'patient_info.json')
    if op.isfile(fname):
        with io.open(fname, 'r', encoding='utf-8') as f:
            try:
                patient_data.update(json.load(f))
            except (UnicodeDecodeError, EOFError, IOError, TypeError):
                raise ValueError('Error loading patient info file %s' % fname)
        return patient_data
    else:
        return None


def save_info(self, session, patient_info):
    """Save patient info. Existing unmodified keys will be kept."""
    fname = op.join(session, 'patient_info.json')
    try:
        with io.open(fname, 'w', encoding='utf-8') as f:
            f.write(unicode(json.dumps(patient_info, ensure_ascii=False)))
    except (UnicodeDecodeError, EOFError, IOError, TypeError):
        raise ValueError('Error saving patient info file %s ' % fname)


def get_session_date(sessionpath=None):
    """Return date when session was recorded (datetime.datetime object)"""
    if sessionpath is None:
        sessionpath = get_sessionpath()
    enfs = get_session_enfs(sessionpath)
    x1ds = [_enf2other(fn, 'x1d') for fn in enfs]
    if not x1ds:
        raise ValueError('No .x1d files for given session')
    return datetime.datetime.fromtimestamp(op.getmtime(x1ds[0]))


def get_session_enfs(sessionpath=None):
    """Return list of .enf files for the Nexus session (or specified path)"""
    if sessionpath is None:
        sessionpath = get_sessionpath()
    enfglob = op.join(sessionpath, '*Trial*.enf')
    enffiles = glob.glob(enfglob) if sessionpath else None
    logger.debug('found %d .enf files for session %s' %
                 (len(enffiles) if enffiles else 0, sessionpath))
    return enffiles


def find_tagged(tags=None, eclipse_keys=None, sessionpath=None):
    """ Find tagged trials in Nexus session path (or given path).
    Returns a list of .c3d files. """
    # FIXME: into config?
    if eclipse_keys is None:
        eclipse_keys = ['DESCRIPTION', 'NOTES']

    if tags is None:
        tags = cfg.plot.eclipse_tags

    tagged_enfs = list(_find_enfs(tags, eclipse_keys, sessionpath))
    return [_enf2other(fn, 'c3d') for fn in tagged_enfs]


def _find_enfs(tags, eclipse_keys, sessionpath=None):
    """ Yield .enf files for trials in current Nexus session directory
    (or given session path) whose Eclipse fields (list) contain any of
    strings (list). Case insensitive. """
    tags = [t.upper() for t in tags]
    enffiles = get_session_enfs(sessionpath)

    if enffiles is None:
        return

    for enf in enffiles:
        ecldi = get_eclipse_keys(enf).items()
        eclvals = [val.upper() for key, val in ecldi if key in eclipse_keys]
        if any([s in val for s in tags for val in eclvals]):
            yield enf









