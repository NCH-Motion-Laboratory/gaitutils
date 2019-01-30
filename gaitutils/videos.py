# -*- coding: utf-8 -*-
"""
Video file related code.

@author: Jussi (jnu@iki.fi)
"""

from builtins import str
from builtins import zip
import logging
import os.path as op
import glob
import itertools

from gaitutils import cfg

logger = logging.getLogger(__name__)


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
    return vids


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
