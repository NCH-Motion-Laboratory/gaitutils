# -*- coding: utf-8 -*-
"""
Session related functions


@author: Jussi (jnu@iki.fi)
"""

from builtins import str
import io
import os.path as op
import json
import datetime
import glob
import re
import logging

from .eclipse import get_eclipse_keys
from .videos import get_trial_videos
from .envutils import GaitDataError
from .config import cfg


logger = logging.getLogger(__name__)

json_keys = ['fullname', 'hetu', 'session_description', 'report_notes']


def default_info():
    """Return info dict with placeholder values"""
    return {key: None for key in json_keys}


def load_info(session):
    """Return the patient info dict from the given session"""
    fname = op.join(session, 'patient_info.json')
    if op.isfile(fname):
        with io.open(fname, 'r', encoding='utf-8') as f:
            try:
                info = json.load(f)
                extra_keys = set(info.keys()) - set(json_keys)
                if extra_keys:
                    logger.warning('Extra keys %s in patient info file %s'
                                   % (extra_keys, fname))
                    for key in extra_keys:
                        info.pop(key)
                missing_keys = set(json_keys) - set(info.keys())
                if missing_keys:
                    logger.warning('Missing keys %s in patient info file %s'
                                   % (missing_keys, fname))
                    # supply default values for missing keys
                    for key in missing_keys:
                        info[key] = default_info()[key]
            except (UnicodeDecodeError, EOFError, IOError, TypeError,
                    ValueError):
                raise GaitDataError('Error loading patient info file %s'
                                    % fname)
    else:
        info = None

    return info


def save_info(session, patient_info):
    """Save patient info."""
    fname = op.join(session, 'patient_info.json')
    try:
        with io.open(fname, 'w', encoding='utf-8') as f:
            f.write(str(json.dumps(patient_info, ensure_ascii=False)))
    except (UnicodeDecodeError, EOFError, IOError, TypeError):
        raise GaitDataError('Error saving patient info file %s ' % fname)


def _merge_session_info(sessions):
    """merge patient info files across sessions. fullname and hetu must match.
    Returns dict of individual session infos and the mergeD info"""
    session_infos = {session: (load_info(session) or default_info())
                     for session in sessions}
    info = default_info()
    # ignore the session description
    for key in ['fullname', 'hetu', 'report_notes']:
        allvals = set([session_infos[session][key] for session in sessions])
        if None in allvals:
            allvals.remove(None)
        if key == 'fullname' or key == 'hetu':
            if len(allvals) > 1:
                logger.warning('name / hetu do not match across sessions')
                return session_infos, None
        if key == 'report_notes':
            if len(allvals) > 1:
                logger.warning('report notes do not match across sessions')
        # in case of conflicts, this just picks from the last session
        info[key] = allvals.pop() if allvals else None
    return session_infos, info


def _enf2other(fname, ext):
    """Converts name of trial .enf file to corresponding .c3d or other
    file type"""
    enfre = '\.*.Trial\d*.enf'  # .Trial followed by zero or more digits
    res = re.search(enfre, fname)
    if res is None:
        raise GaitDataError('Filename %s is not a trial .enf' % fname)
    return fname.replace(res.group(), '.%s' % ext)


def get_session_date(sessionpath):
    """Return date when session was recorded (datetime.datetime object)"""
    enfs = get_session_enfs(sessionpath)
    x1ds = [_enf2other(fn, 'x1d') for fn in enfs]
    if not x1ds:
        raise GaitDataError('Invalid session %s' % sessionpath)
    return datetime.datetime.fromtimestamp(op.getmtime(x1ds[0]))


def _trials_of_interest(session, tags=None):
    """Return tagged, static and video-tagged trials"""
    tagged = find_tagged(session, tags=tags)
    static = find_tagged(session, ['Static'], ['TYPE'])[:1]
    video_only = find_tagged(session, tags=cfg.eclipse.video_tags)
    return tagged + static + video_only


def _collect_videos(session, tags=None):
    """Collect video files of interest for session. Includes tagged trials,
    static trial and video-tagged trials as specified in config"""
    trials = _trials_of_interest(session, tags=None)
    vids = [get_trial_videos(c3dfile) for c3dfile in trials]
    return [vid for vids_ in vids for vid in vids_]  # flatten list of lists


def get_session_enfs(sessionpath):
    """Return list of .enf files for the session """
    enfglob = op.join(sessionpath, '*Trial*.enf')
    for enf in glob.iglob(enfglob):
        yield enf, None


def _filter_by_eclipse(enfs, patterns, eclipse_keys):
    """Filter for enfs whose Eclipse keys match given tags. Case insensitive.
    Yields tuples of (filename, tag)"""
    if not isinstance(patterns, list):
        patterns = [patterns]
    if not isinstance(eclipse_keys, list):
        eclipse_keys = [eclipse_keys]
    eclipse_keys = [key.upper() for key in eclipse_keys]
    for enf, _ in enfs:
        ecldi = {key.upper(): val.upper() for key, val in
                 get_eclipse_keys(enf).items()}
        eclvals = [val for key, val in ecldi.items() if key in eclipse_keys]
        for pattern in patterns:
            if any(pattern.upper() in eclval for eclval in eclvals):
                yield (enf, pattern)
                break  # only yield for 1st matching pattern


def _filter_tagged(enfs, tags):
    """Filter by given tags"""
    return _filter_by_eclipse(enfs, tags, cfg.eclipse.tag_keys)


def _filter_dynamic(enfs):
    """Filter for dynamic trials"""
    return _filter_by_eclipse(enfs, 'Dynamic', 'TYPE')


def _filter_static(enfs):
    """Filter for static trials"""
    return _filter_by_eclipse(enfs, 'Static', 'TYPE')


def _filter_to_c3ds(enfs):
    """Change filenames to c3ds and check existence"""
    for enf, tag in enfs:
        c3d = _enf2other(enf, 'c3d')
        if op.isfile(c3d):
            yield c3d, tag


def get_c3ds(sessionpath, tags=None, trial_type=None, return_tags=False):
    enfs = get_session_enfs(sessionpath)
    if trial_type is not None:
        if trial_type.lower() == 'dynamic':
            enfs = _filter_dynamic(enfs)
        elif trial_type.lower() == 'static':
            enfs = _filter_static(enfs)
    if tags is not None:
        enfs = _filter_tagged(enfs, tags)
    c3ds = _filter_to_c3ds(enfs)
    return list(c3ds) if return_tags else list(fn for fn, tag in c3ds)
