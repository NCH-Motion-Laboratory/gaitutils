# -*- coding: utf-8 -*-
"""

Test EMG functions.

@author: Jussi (jnu@iki.fi)
"""

import logging
import tempfile
import tempfile
from pathlib import Path

from gaitutils import emg, cfg
from utils import _file_path

logger = logging.getLogger(__name__)


# test data
sessiondir_ = 'test_subjects/D0063_RR/2018_12_17_preOp_RR'
sessiondir_abs = _file_path(sessiondir_)
sessiondir2_ = 'test_subjects/D0063_RR/2018_12_17_preOp_tuet_RR'
sessiondir2_abs = _file_path(sessiondir2_)
sessiondir3_ = 'test_subjects/girl6v/test_session'
sessiondir3_abs = _file_path(sessiondir3_)


def test_emg_detect_bads():
    """Test bad channel detection"""
    cfg.emg.autodetect_bads = True
    # this file is tricky; RVas is disconnected but shows some kind of artifact
    # instead of 50 Hz
    fn = r'2018_12_17_preOp_RR21.c3d'
    fpath = sessiondir_abs / fn
    e = emg.EMG(fpath)
    expected_ok = {
        'RGas': True,
        'LHam': True,
        'RSol': True,
        'RGlut': False,
        'LVas': False,
        'LGas': True,
        'LRec': True,
        'RPer': True,
        'RVas': False,
        'LSol': True,
        'RTibA': True,
        'RHam': True,
        'LTibA': True,
        'RRec': True,
        'LPer': True,
        'LGlut': False,
    }
    for chname, exp_ok in expected_ok.items():
        assert e.status_ok(chname) == exp_ok
    # all should be ok
    fn = r'2015_10_22_girl6v_IN03.c3d'
    fpath = sessiondir3_abs / fn
    e = emg.EMG(fpath)
    for chname, exp_ok in expected_ok.items():
        assert e.status_ok(chname) == True
    cfg.emg.autodetect_bads = False


def test_emg_write_edf():
    """Test the edf writer"""
    fn = r'2018_12_17_preOp_RR21.c3d'
    fpath = sessiondir_abs / fn
    e = emg.EMG(fpath)
    tmp_edf = Path(tempfile.gettempdir()) / 'edf_dump.edf'
    e._edf_export(tmp_edf)
    assert tmp_edf.is_file()
    # FIXME: read edf file and check output


def test_emg_get_data():
    """Test the EMG data getter"""
    fn = r'2018_12_17_preOp_RR04.c3d'
    fpath = sessiondir_abs / fn
    e = emg.EMG(fpath)
    chnames = [
        'RGas',
        'LHam',
        'RSol',
        'RGlut',
        'LVas',
        'LGas',
        'LRec',
        'RPer',
        'RVas',
        'LSol',
        'RTibA',
        'RHam',
        'LTibA',
        'RRec',
        'LPer',
        'LGlut',
    ]
    for chname in chnames:
        chdata = e.get_channel_data(chname)
        assert chdata.shape == (1000,)
        chdata = e.get_channel_data(chname, envelope=True)
        assert chdata.shape == (1000,)
