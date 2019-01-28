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

from gaitutils import cfg

logger = logging.getLogger(__name__)


def get_trial_videos(fname, camera_id=None, ext='avi'):
    """Return list of video files for trial file. File may be c3d or enf etc"""
    trialbase = op.splitext(fname)[0]
    vids = glob.glob(trialbase + '*' + ext)
    if camera_id is None:
        return vids
    else:
        return _video_id_filter(vids, camera_id=camera_id)


def _video_id_filter(vids, camera_id):
    """Filter videos by id"""
    for vid in vids:
        if _camera_id(vid) == camera_id:
            yield vid


def _video_overlay_filter(vids, overlay=True):
    """Filter to get overlay or non-overlay videos"""
    for vid in vids:
        if 'overlay' in vid:
            if overlay:
                yield vid
        else:
            if not overlay:
                yield vid


def _video_label_filter(vids, camera_label):
    """Filter videos by label"""
    ids = [id_ for id_, label in cfg.general.camera_labels.items() if
           camera_label == label]
    # find all videos matching any id
    for id in ids:
        for vid in _video_id_filter(vids, id):
            yield vid


def _camera_id(fname):
    """ Returns camera id for a video file """
    fn_split = op.split(fname)[-1].split('.')
    if len(fn_split) < 3:
        raise ValueError('Unexpected video file name %s' % fname)
    return fn_split[-3]
