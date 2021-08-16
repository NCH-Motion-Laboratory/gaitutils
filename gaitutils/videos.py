# -*- coding: utf-8 -*-
"""
Video file related code.

@author: Jussi (jnu@iki.fi)
"""

import logging
import os
import os.path as op
from pathlib import Path
import glob
import itertools
import ctypes
import subprocess

from .config import cfg
from . import sessionutils, numutils

logger = logging.getLogger(__name__)


def convert_videos(vidfiles, check_only=False):
    """Convert video files using an external command.

    Command and args are defined in cfg.
    NB: Instantly starts as many converter processes as there are files and
    returns. This has the disadvantage of potentially starting dozens of
    processes, causing slowdown.

    Parameters
    ----------
    vidfiles : list | str | Path
        List of video filenames, or a single filename
    check_only : bool, optional
        Instead of converting, return True if all files are already converted
        (target exists).
    """
    TARGET_SUFFIX = '.ogv'  # extension for converted files
    if not isinstance(vidfiles, list):
        vidfiles = [vidfiles]
    vidfiles = [Path(vidfile) for vidfile in vidfiles]
    # result files
    convfiles = {vidfile: vidfile.with_suffix(TARGET_SUFFIX) for vidfile in vidfiles}
    converted = [p.is_file() for p in convfiles.values()]  # files that are already done
    if check_only:
        return all(converted)

    # XXX: this disables Windows protection fault dialogs
    # needed since ffmpeg2theora may crash after conversion is complete (?)
    SEM_NOGPFAULTERRORBOX = 0x0002  # From MSDN
    ctypes.windll.kernel32.SetErrorMode(SEM_NOGPFAULTERRORBOX)

    vidconv_bin = Path(cfg.general.videoconv_path)
    vidconv_opts = cfg.general.videoconv_opts
    if not (vidconv_bin.is_file() and os.access(vidconv_bin, os.X_OK)):
        raise RuntimeError(f'Invalid configured video converter: {vidconv_bin}')
    procs = []
    for vidfile in convfiles:
        cmd = [vidconv_bin] + vidconv_opts.split() + [vidfile]
        # supply NO_WINDOW flag to prevent opening of consoles
        p = subprocess.Popen(cmd, stdout=None, creationflags=0x08000000)
        procs.append(p)
    return procs


def _collect_session_videos(session, tags):
    """Collect session .avi files (trial videos). This only collects
    files for tagged dynamic trials, extra video-only trials and static trials."""
    c3ds = sessionutils.get_c3ds(
        session, tags=tags, trial_type='dynamic', check_if_exists=False
    )
    c3ds += sessionutils.get_c3ds(
        session,
        tags=cfg.eclipse.video_tags,
        trial_type='dynamic',
        check_if_exists=False,
    )
    c3ds += sessionutils.get_c3ds(session, trial_type='static')
    camlabels = set(cfg.general.camera_labels.values())
    # for each trial, pick at most one avi and one overlay avi per camera
    vids_it = (
        get_trial_videos(
            c3d,
            camera_label=camlabel,
            vid_ext='.avi',
            overlay=overlay,
            single_file=True,
        )
        for c3d in c3ds
        for camlabel in camlabels
        for overlay in [True, False]
    )
    # chain resulting video files into single list
    return list(itertools.chain.from_iterable(vids_it))


def get_trial_videos(
    trialfile, camera_label=None, vid_ext=None, overlay=None, single_file=False
):
    """Gets list of video files associated with a trial file.

    Trial file must be e.g. c3d, x1d or x2d (enf files won't work, since they
    are named according to different logic).

    Parameters
    ----------
    trialfile : str
        The name of the file.
    camera_label : [type], optional
        If not None, return only videos corresponding to given camera label.
    vid_ext : str
        If not None, return only video files with given extension, e.g. '.avi'
    overlay : bool
        If not None, return only overlay or non-overlay videos, for True and False
        respectively
    single_file : bool
        If True, return only one file.

    Returns
    -------
    list
        The list of video filenames.
    """
    trialbase = op.splitext(trialfile)[0]
    # XXX: should really be case insensitive, but it does not matter on Windows
    vid_exts = ['.avi', '.ogv']
    if vid_ext is not None and vid_ext not in vid_exts:
        raise ValueError('unrecognized video extension %s' % vid_ext)
    globs_ = ('%s.*%s' % (trialbase, vid_ext) for vid_ext in vid_exts)
    vids = itertools.chain.from_iterable(glob.iglob(glob_) for glob_ in globs_)
    if camera_label is not None:
        vids = _filter_by_label(vids, camera_label)
    if vid_ext is not None:
        vids = _filter_by_extension(vids, vid_ext)
    if overlay is not None:
        vids = _filter_by_overlay(vids, overlay)
    return sorted(vids)[-1:] if single_file else sorted(vids)


def _filter_by_label(vids, camera_label):
    """Filter videos by given camera label"""
    if camera_label not in cfg.general.camera_labels.values():
        raise ValueError('unconfigured camera label %s' % camera_label)
    ids = [
        id_ for id_, label in cfg.general.camera_labels.items() if camera_label == label
    ]
    vid_its = itertools.tee(vids, len(ids))  # need to reuse vids iterator
    for id_, vids_ in zip(ids, vid_its):
        for vid in _filter_by_id(vids_, id_):
            yield vid


def _filter_by_extension(vids, ext):
    """Filter videos by filename extension. Case insensitive"""
    for vid in vids:
        if op.splitext(vid)[1].upper() == ext.upper():
            yield vid


def _filter_by_id(vids, camera_id):
    """Filter videos by camera id"""
    for vid in vids:
        if _camera_id(vid) == camera_id:
            yield vid


def _filter_by_overlay(vids, overlay=True):
    """Filter to get overlay or non-overlay videos"""
    for vid in vids:
        if 'overlay' in vid and overlay:
            yield vid
        elif 'overlay' not in vid and not overlay:
            yield vid


def _camera_id(fname):
    """Return camera id for a video file"""
    # camera id should be the second component of dot-separated filename
    fn_split = op.split(fname)[-1].split('.')
    id_ = fn_split[1]
    if not numutils._isint(id_):
        return None
    return id_
