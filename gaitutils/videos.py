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


def get_trial_videos(fname):
    """Return list of video files for trial file. File may be c3d or enf etc"""
    vid_exts = ['avi', 'ogv']
    trialbase = op.splitext(fname)[0]
    globs_ = ('%s*%s' % (trialbase, vid_ext) for vid_ext in vid_exts)
    return itertools.chain.from_iterable(glob.iglob(glob_) for glob_ in globs_)


def _filter_by_label(vids, camera_label):
    """Filter videos by label"""
    ids = [id_ for id_, label in cfg.general.camera_labels.items() if
           camera_label == label]
    # find all videos matching any id
    for id in ids:
        for vid in _filter_by_id(vids, id):
            yield vid


def _filter_by_extension(vids, ext):
    """Filter by filename extension. Case insensitive"""
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
