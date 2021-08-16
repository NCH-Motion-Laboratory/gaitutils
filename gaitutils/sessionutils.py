# -*- coding: utf-8 -*-
"""
Session related functions


@author: Jussi (jnu@iki.fi)
"""

import io
import os.path as op
from pathlib import Path
import json
import datetime
import glob
import re
import logging

from .eclipse import get_eclipse_keys
from .config import cfg
from .envutils import GaitDataError


logger = logging.getLogger(__name__)

# the patient info keys
json_keys = ['fullname', 'hetu', 'session_description']
# exceptions that may occur when saving/loading json
json_exceptions = (UnicodeDecodeError, EOFError, IOError, TypeError, ValueError)


def load_quirks(session):
    """Load quirks JSON file.

    Quirks represent session-specific oddities that have to be taken into account
    when loading trials, e.g. wrong EMG scaling etc.

    Currently supported quirks are:

    emg_correction_factor : float
        All EMG data will be multiplied by this factor after reading.
    ignore_eclipse_fp_info : bool
        If True, Eclipse forceplate fields will be ignored when loading trials from
        the session.
    emg_chs_disabled : list
        List of EMG channels to disable.

    Parameters
    ----------
    session : str | Path
        The session path.

    Returns
    -------
    dict
        The quirks in a dict.
    """
    session = Path(session)
    fname = session / 'quirks.json'
    quirks = dict()
    if fname.is_file():
        with io.open(fname, 'r', encoding='utf-8') as f:
            try:
                quirks.update(json.load(f))
            except json_exceptions:
                logger.warning('cannot load quirks file %s' % fname)
    return quirks


def default_info():
    """Return a default patient info dict.

    Returns
    -------
    dict
        The info dict with all keys set to None.
    """
    return {key: None for key in json_keys}


def load_info(session):
    """Load the patient info dict from a given session

    Parameters
    ----------
    session : str | Path
        The session path.

    Returns
    -------
    dict
        The patient info.
    """
    session = Path(session)
    fname = session / 'patient_info.json'
    if fname.is_file():
        with io.open(fname, 'r', encoding='utf-8') as f:
            try:
                info = json.load(f)
                # check for extra keys (e.g. obsoleted ones), do not return them
                extra_keys = set(info.keys()) - set(json_keys)
                if extra_keys:
                    logger.warning(
                        'Extra keys %s in patient info file %s' % (extra_keys, fname)
                    )
                    for key in extra_keys:
                        info.pop(key)
                missing_keys = set(json_keys) - set(info.keys())
                if missing_keys:
                    logger.warning(
                        'Missing keys %s in patient info file %s'
                        % (missing_keys, fname)
                    )
                    # supply default values for missing keys
                    for key in missing_keys:
                        info[key] = default_info()[key]
            except json_exceptions:
                raise GaitDataError(f'Error loading patient info file {fname}')
    else:
        info = None
    return info


def save_info(session, patient_info):
    """Save an info dict into a session.

    Parameters
    ----------
    session : str | Path
        The session path.
    patient_info : dict
        The patient info.
    """
    session = Path(session)
    fname = session / 'patient_info.json'
    try:
        with io.open(fname, 'w', encoding='utf-8') as f:
            f.write(str(json.dumps(patient_info, ensure_ascii=False)))
    except json_exceptions:
        raise GaitDataError(f'Error saving patient info file {fname}')


def _merge_session_info(sessions):
    """Merge patient info files across sessions.

    The fullname and hetu keys must match.
    Returns a 2-tuple with: dict of individual session infos, merged info"""
    session_infos = {
        session: (load_info(session) or default_info()) for session in sessions
    }
    info = default_info()
    # merging session descriptions does not really make sense, but do it for
    # consistency (so we can also call this for single session)
    for key in json_keys:
        allvals = set([session_infos[session][key] for session in sessions])
        if None in allvals:
            allvals.remove(None)
        if key == 'fullname' or key == 'hetu':
            if len(allvals) > 1:
                logger.warning('name / hetu do not match across sessions')
                return session_infos, None
        # in case of conflicts, this just picks from the last session
        info[key] = allvals.pop() if allvals else None
    return session_infos, info


def enf_to_trialfile(fname, ext):
    """Convert the name of a trial .enf file to another type of trial file.

    Parameters
    ----------
    fname : str | Path
        The .enf file path.
    ext : str
        File extension, e.g. 'c3d'. Can be supplied with a leading dot.

    Returns
    -------
    str
        The converted filename.
    """
    fname = str(fname)
    if ext[0] == '.':
        ext = ext[1:]
    enfre = r'\.*.Trial\d*.enf'  # .Trial followed by zero or more digits
    res = re.search(enfre, fname)
    if res is None:
        raise GaitDataError(f'Filename {fname} is not a trial .enf')
    return Path(fname.replace(res.group(), f'.{ext}'))


def get_session_date(sessionpath):
    """Get the date when the session was recorded (datetime.datetime object).

    Parameters
    ----------
    sessionpath : str | Path
        The session path.

    Returns
    -------
    datetime.datetime
        The datetime.
    """
    enfs = get_enfs(sessionpath)
    x1ds = [enf_to_trialfile(fn, 'x1d') for fn in enfs]
    if not x1ds:
        raise GaitDataError(f'Invalid session: {sessionpath}')
    else:
        x1ds = [x1d for x1d in x1ds if x1d.is_file()]
        if not x1ds:
            raise GaitDataError('cannot find any .x1d trial files in session')
        else:
            x1d = x1ds[-1]
        return datetime.datetime.fromtimestamp(x1d.lstat().st_mtime)


def _get_session_enfs(sessionpath):
    """Return list of .enf files for the session"""
    # we could use pathlib here too, but it's really not intended for globs
    enfglob = op.join(sessionpath, '*Trial*.enf')
    for fp in glob.iglob(enfglob):
        yield Path(fp)


def _filter_by_eclipse_keys(enfs, patterns, eclipse_keys):
    """Filter for enfs whose Eclipse key values match given patterns."""
    if not isinstance(patterns, list):
        patterns = [patterns]
    if not isinstance(eclipse_keys, list):
        eclipse_keys = [eclipse_keys]
    for enf in enfs:
        ecldi = {key.upper(): val.upper() for key, val in get_eclipse_keys(enf).items()}
        eclvals = [val for key, val in ecldi.items() if key in eclipse_keys]
        for pattern in patterns:
            if any(pattern.upper() in eclval for eclval in eclvals):
                yield enf


def _filter_by_tags(enfs, tags):
    """Filter by given tags"""
    return _filter_by_eclipse_keys(enfs, tags, cfg.eclipse.tag_keys)


def _filter_by_type(enfs, trial_type):
    """Filter by trial type"""
    return _filter_by_eclipse_keys(enfs, trial_type, 'TYPE')


def _filter_to_c3ds(enfs):
    """Convert enf filenames to c3d"""
    for enf in enfs:
        yield enf_to_trialfile(enf, 'c3d')


def _filter_exists(files):
    for f in files:
        if Path(f).is_file():
            yield f


def get_enfs(sessionpath, tags=None, trial_type=None, check_if_exists=True):
    """Get specified enf files for a session.

    Parameters
    ----------
    sessionpath : str | Path
        The session path.
    tags : list, optional
        List of Eclipse tags to filter for. E.g. ['T1'] would return only .enf
        files that are tagged with 'T1' in Eclipse. An empty list or None
        disables filtering by tags.
    trial_type : str, optional
        Trial type (Eclipse TYPE field), e.g. 'static' or 'dynamic'.
    check_if_exists : bool, optional
        If True, return only enf files that actually exist.

    Returns
    -------
    list
        List of enf files.
    """

    enfs = _get_session_enfs(sessionpath)
    if trial_type is not None:
        enfs = _filter_by_type(enfs, trial_type)
    if tags:
        enfs = _filter_by_tags(enfs, tags)
    if check_if_exists:
        enfs = _filter_exists(enfs)
    return list(enfs)


def get_c3ds(sessionpath, tags=None, trial_type=None, check_if_exists=True):
    """Get c3d files for a session. Similar to get_enfs above.

    Parameters
    ----------
    sessionpath : str
        The session path.
    tags : list, optional
        List of Eclipse tags to filter for. E.g. ['T1'] would return only .enf
        files that are tagged with 'T1' in Eclipse. An empty list or None
        disables filtering by tags.
    trial_type : str, optional
        Trial type (Eclipse TYPE field), e.g. 'static' or 'dynamic'.
    check_if_exists : bool, optional
        If True, return only c3d files that actually exist.

    Returns
    -------
    list
        List of c3d files.
    """

    enfs = get_enfs(
        sessionpath, tags=tags, trial_type=trial_type, check_if_exists=check_if_exists
    )
    c3ds = _filter_to_c3ds(enfs)
    if check_if_exists:
        c3ds = _filter_exists(c3ds)
    return list(c3ds)


def _get_tagged_dynamic_c3ds_from_sessions(sessions, tags=None):
    """Gather all tagged dynamic c3d files from given sessions."""
    if not isinstance(sessions, list):
        sessions = [sessions]
    c3ds_all = list()
    for session in sessions:
        c3ds = get_c3ds(session, tags=tags, trial_type='dynamic')
        # we require at least on tagged trial for each session
        if not c3ds:
            raise GaitDataError('No tagged trials found for session %s' % session)
        c3ds_all.extend(c3ds)
    return c3ds_all


def _parse_name(name):
    """Parse trial or session name.

    Name is assumed to be the form:
    YYYY_MM_DD_desc1_desc2_..._descN_patientcode

    Returns tuple of: (datetime, patientcode, session_description)
    """
    name_split = name.split('_')
    if len(name_split) < 3:
        raise ValueError('Could not parse name')
    try:  # see if trial begins with valid date
        datetxt = '-'.join(name_split[:3])
        d = datetime.datetime.strptime(datetxt, '%Y-%m-%d')
    except ValueError:
        raise ValueError('Could not parse name')
    code = name_split[-1] if len(name_split) > 3 else None
    desc = ', '.join(name_split[3:-1]) if len(name_split) > 3 else None
    return d, code, desc
