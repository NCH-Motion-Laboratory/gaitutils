# -*- coding: utf-8 -*-
"""

Test video related functions.

@author: Jussi (jnu@iki.fi)
"""

import logging
import tempfile

from gaitutils import videos, sessionutils
import time
from utils import _file_path, cfg

logger = logging.getLogger(__name__)


# test session
sessiondir_ = 'test_subjects/D0063_RR/2018_12_17_preOp_RR'  # rel path
sessiondir_abs = _file_path(sessiondir_)  # absolute path
tmpdir = tempfile.gettempdir()


def test_convert_videos():
    c3d_file = sessionutils.get_c3ds(
        sessiondir_abs, tags=None, trial_type='dynamic', check_if_exists=False
    )[0]
    original_vids = videos.get_trial_videos(c3d_file, vid_ext='.avi', overlay=False)
    assert len(original_vids) == 3
    target_vids = videos.get_trial_videos(c3d_file, vid_ext=cfg.general.video_converted_ext, overlay=False)
    # remove target videos if they exist
    for vidfile in target_vids:
        vidfile.unlink()
    # check should not find target videos any more
    assert not videos.convert_videos(original_vids, check_only=True)
    # start conversion process
    procs = videos.convert_videos(original_vids)
    assert procs
    completed = False
    # wait in a sleep loop until processes have finished
    while not completed:
        n_complete = len([p for p in procs if p.poll() is not None])
        completed = n_complete == len(procs)
        time.sleep(0.1)
    # now conversion target videos should exist
    assert videos.convert_videos(original_vids, check_only=True)


def test_collect_session_videos():
    vids = videos._collect_session_videos(sessiondir_abs, cfg.eclipse.tags)
    # should be 6 (dyn) x 3 + 3 (vidonly) x 3 + 1 (static) x 3 = 30
    assert len(vids) == 30


def test_get_trial_videos():
    # this trial has one extra video (two vids for front camera)
    trialfile_ = '2018_12_17_preOp_RR07.c3d'
    trialfile = sessiondir_abs / trialfile_
    vids = videos.get_trial_videos(trialfile)  # get all
    assert len(vids) == 4
    for vid in vids:
        assert vid.is_file()
    vids = videos.get_trial_videos(
        trialfile, camera_label='Front camera', vid_ext='.avi'
    )
    assert len(vids) == 2
    vids = videos.get_trial_videos(
        trialfile, camera_label='Front camera', vid_ext='.avi', single_file=True
    )
    # get single video, must be one with the most recent timestamp
    assert len(vids) == 1
    assert (
        vids[0] == sessiondir_abs / '2018_12_17_preOp_RR07.2114551.20181317142825.avi'
    )
    vids = videos.get_trial_videos(trialfile, vid_ext=cfg.general.video_converted_ext)
    assert len(vids) == 3
    vids = videos.get_trial_videos(trialfile, vid_ext='.avi', overlay=True)
    assert not vids
