# -*- coding: utf-8 -*-
"""

Test video related functions.

@author: Jussi (jnu@iki.fi)
"""

import pytest
import numpy as np
import logging
import tempfile
import os
import os.path as op
from pkg_resources import resource_filename

from gaitutils import videos
from utils import _file_path, cfg

logger = logging.getLogger(__name__)


# test session
sessiondir_ = 'test_subjects/D0063_RR/2018_12_17_preOp_RR'
sessiondir_abs = _file_path(sessiondir_)
sessiondir__ = op.split(sessiondir_)[-1]
tmpdir = tempfile.gettempdir()


def test_session_videos():
    vids = videos._collect_session_videos(sessiondir_abs, cfg.eclipse.tags)
    # should be 6 (dyn) x 3 + 3 (vidonly) x 3 + 1 (static) x 3 = 30
    assert len(vids) == 30


def test_get_trial_videos():
    # this trial has one extra video (two vids for front camera)
    trialfile_ = "2018_12_17_preOp_RR07.c3d"
    trialfile = op.join(sessiondir_abs, trialfile_)
    vids = videos.get_trial_videos(trialfile)  # get all
    assert len(vids) == 7
    for vid in vids:
        assert op.isfile(vid)
    vids = videos.get_trial_videos(trialfile, camera_label='Front camera', vid_ext='.avi')
    assert len(vids) == 2
    vids = videos.get_trial_videos(trialfile, camera_label='Front camera', vid_ext='.avi',
                                   single_file=True)
    # get single video, must be one with the most recent timestamp
    assert len(vids) == 1
    assert vids[0] == op.join(sessiondir_abs, "2018_12_17_preOp_RR07.2114551.20181317142825.avi")
    vids = videos.get_trial_videos(trialfile, vid_ext='.ogv')
    assert len(vids) == 3
    vids = videos.get_trial_videos(trialfile, vid_ext='.avi', overlay=True)
    assert not vids