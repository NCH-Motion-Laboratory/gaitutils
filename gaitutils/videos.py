# -*- coding: utf-8 -*-
"""
Video file related code.

@author: Jussi (jnu@iki.fi)
"""

from builtins import zip
import logging
import os
import os.path as op
import glob
import itertools
import ctypes
import subprocess

from . import cfg, sessionutils

logger = logging.getLogger(__name__)


def convert_videos(vidfiles, check_only=False):
    """Convert video files using command and options defined in cfg.
    If check_only, return whether files were already converted.
    Instantly starts as many converter processes as there are files and
    returns. This has the disadvantage of potentially starting dozens of
    processes, causing slowdown.
    """
    CONV_EXT = '.ogv'  # extension for converted files
    if not isinstance(vidfiles, list):
        vidfiles = [vidfiles]
    convfiles = {vidfile: op.splitext(vidfile)[0] + CONV_EXT for vidfile
                 in vidfiles}
    converted = [op.isfile(fn) for fn in convfiles.values()]  # already done
    if check_only:
        return all(converted)

    # XXX: this disables Windows protection fault dialogs
    # needed since ffmpeg2theora may crash after conversion is complete (?)
    SEM_NOGPFAULTERRORBOX = 0x0002  # From MSDN
    ctypes.windll.kernel32.SetErrorMode(SEM_NOGPFAULTERRORBOX)

    vidconv_bin = cfg.general.videoconv_path
    vidconv_opts = cfg.general.videoconv_opts
    if not (op.isfile(vidconv_bin) and os.access(vidconv_bin, os.X_OK)):
        raise ValueError('Invalid video converter executable: %s'
                         % vidconv_bin)
    procs = []
    for vidfile, convfile in convfiles.items():
        if not op.isfile(convfile):
            # supply NO_WINDOW flag to prevent opening of consoles
            cmd = [vidconv_bin]+vidconv_opts.split()+[vidfile]
            cmd = [s.encode('iso-8859-1') for s in cmd]
            p = subprocess.Popen(cmd,
                                 stdout=None, creationflags=0x08000000)
            procs.append(p)
    return procs


def _collect_session_videos(session, tags):
    """Collect session AVI files"""
    c3ds = sessionutils.get_c3ds(session, tags=tags,
                                 trial_type='dynamic')
    c3ds += sessionutils.get_c3ds(session, tags=cfg.eclipse.video_tags,
                                  trial_type='dynamic')
    c3ds += sessionutils.get_c3ds(session, trial_type='static')
    vids_it = (get_trial_videos(c3d, vid_ext='.avi')
               for c3d in c3ds)
    return list(itertools.chain.from_iterable(vids_it))


def get_trial_videos(trialfile, camera_label=None, vid_ext=None, overlay=None):
    """Return list of video files for trial file. File may be c3d or enf etc"""
    trialbase = op.splitext(trialfile)[0]
    # XXX: should really be case insensitive, but does not matter on Windows
    vid_exts = ['avi', 'ogv']
    globs_ = ('%s*%s' % (trialbase, vid_ext) for vid_ext in vid_exts)
    vids = itertools.chain.from_iterable(glob.iglob(glob_) for glob_ in globs_)
    if camera_label is not None:
        vids = _filter_by_label(vids, camera_label)
    if vid_ext is not None:
        vids = _filter_by_extension(vids, vid_ext)
    if overlay is not None:
        vids = _filter_by_overlay(vids, overlay)
    return list(vids)


def _filter_by_label(vids, camera_label):
    """Filter videos by camera label"""
    ids = [id for id, label in cfg.general.camera_labels.items() if
           camera_label == label]
    vid_its = itertools.tee(vids, len(ids))  # need to reuse vids iterator
    for id, vids_ in zip(ids, vid_its):
        for vid in _filter_by_id(vids_, id):
            yield vid


def _filter_by_extension(vids, ext):
    """Filter videos by filename extension. Case insensitive"""
    for vid in vids:
        if op.splitext(vid)[1].upper() == ext.upper():
            yield vid


def _filter_by_id(vids, camera_id):
    """Filter videos by id"""
    for vid in vids:
        if _camera_id(vid) == camera_id:
            yield vid


def _filter_by_overlay(vids, overlay=True):
    """Filter to get overlay or non-overlay videos"""
    for vid in vids:
        if 'overlay' in vid:
            if overlay:
                yield vid
        else:
            if not overlay:
                yield vid


def _camera_id(fname):
    """ Returns camera id for a video file """
    fn_split = op.split(fname)[-1].split('.')
    if len(fn_split) < 3:
        raise ValueError('Unexpected video file name %s' % fname)
    return fn_split[-3]
