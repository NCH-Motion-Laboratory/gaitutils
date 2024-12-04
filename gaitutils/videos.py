# -*- coding: utf-8 -*-
"""
Video file related code.

@author: Jussi (jnu@iki.fi)
"""

import logging
import os
from pathlib import Path
import glob
import itertools
import ctypes
import platform
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
    if not isinstance(vidfiles, list):
        vidfiles = [vidfiles]
    vidfiles = [Path(vidfile) for vidfile in vidfiles]
    # result files
    convfiles = {vidfile: vidfile.with_suffix(cfg.general.video_converted_ext) for vidfile in vidfiles}

    if check_only:
        # return True if all conversion targets already exists
        return all(p.is_file() for p in convfiles.values())

    vidconv_bin = Path(cfg.general.videoconv_path)
    vidconv_opts = cfg.general.videoconv_opts
    if not (vidconv_bin.is_file() and os.access(vidconv_bin, os.X_OK)):
        raise RuntimeError(f'Invalid configured video converter: {vidconv_bin}')

    procs = []    

    for vidfile in convfiles:
        if vidconv_opts == '':
            # For compatibility purposes, if no video converter options are
            # specified, pass to the converter just input file name.
            cmd = [vidconv_bin] + [vidfile]
        else:
            # Video converter parameters given as a list of two lists.
            # e.g. [['-i', '', '-o', ''], [1, 3]] means that the 1-st and 3-rd
            # elements of ['-i', '', '-o', ''] should be replaced with the input
            # and output filenames correspondingly, and the result should be
            # given to the video converter command as command-line parameters.
            try:
                vidconv_opts[0][vidconv_opts[1][0]] = vidfile
                if len(vidconv_opts[1]) > 1:
                    vidconv_opts[0][vidconv_opts[1][1]] = str(convfiles[vidfile])
            except:
                raise RuntimeError(f'Incorrect video converter parameters.')
            
            cmd = [vidconv_bin] + vidconv_opts[0]

        if platform.system() == 'Windows':
            # supply NO_WINDOW flag to prevent opening of consoles
            p = subprocess.Popen(cmd, stdout=None, creationflags=0x08000000)
        else:
            p = subprocess.Popen(cmd, stdout=None)
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
    trialfile : str | Path
        Trial file path.
    camera_label : [type], optional
        If not None, return only videos corresponding to given camera label.
    vid_ext : str
        Return video files with given extension. Default is '.avi'
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
    # XXX: should really be case insensitive, but it does not matter on Windows
    if vid_ext is None:
        vid_ext = '.avi'
    trialbase = Path(trialfile).with_suffix('')
    glob_ = f'{trialbase}.*{vid_ext}'
    vids = glob.iglob(glob_)
    if camera_label is not None:
        vids = _filter_by_label(vids, camera_label)
    if overlay is not None:
        vids = _filter_by_overlay(vids, overlay)
    vids = sorted(vids)[-1:] if single_file else sorted(vids)
    return [Path(vid) for vid in vids]


def _filter_by_label(vids, camera_label):
    """Filter videos by given camera label"""
    if camera_label not in cfg.general.camera_labels.values():
        raise ValueError(f'unconfigured camera label {camera_label}')
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
        if Path(vid).suffix.upper() == ext.upper():
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
    # camera id should be the second component of dot-delimited filename
    id_ = Path(fname).name.split('.')[1]
    return id_ if numutils._isint(id_) else None
