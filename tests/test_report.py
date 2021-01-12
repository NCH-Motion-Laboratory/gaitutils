# -*- coding: utf-8 -*-
"""

Test reporting functions.

@author: Jussi (jnu@iki.fi)
"""

import pytest
import logging
import tempfile
import os
import os.path as op

from gaitutils.report import pdf, web
from utils import _file_path

logger = logging.getLogger(__name__)


# test session
sessiondir_ = 'test_subjects/D0063_RR/2018_12_17_preOp_RR'
sessiondir_abs = _file_path(sessiondir_)
sessiondir2_ = 'test_subjects/D0063_RR/2018_12_17_preOp_tuet_RR'
sessiondir2_abs = _file_path(sessiondir2_)
sessiondir__ = op.split(sessiondir_)[-1]
tmpdir = tempfile.gettempdir()


def test_pdf_report():
    """Test creation of pdf report + time-distance text report"""
    pdfname = sessiondir__ + '.pdf'
    pdfpath = op.join(tmpdir, pdfname)
    timedist_name = sessiondir__ + '_time_distance.txt'
    timedist_path = op.join(tmpdir, timedist_name)
    if op.isfile(pdfpath):
        os.remove(pdfpath)
    if op.isfile(timedist_path):
        os.remove(timedist_path)
    pdf.create_report(sessiondir_abs, destdir=tmpdir, write_timedist=True)
    assert op.isfile(pdfpath)
    assert op.isfile(timedist_path)


def test_pdf_comparison_report():
    """Test creation of pdf comparison report"""
    sessionpaths = [sessiondir_abs, sessiondir2_abs]
    # resulting pdf name - must be set according to what is defined in the function
    pdfname = ' VS '.join(op.split(sp)[1] for sp in sessionpaths) + '.pdf'
    pdfpath = op.join(tmpdir, pdfname)
    if op.isfile(pdfpath):
        os.remove(pdfpath)
    pdf.create_comparison_report(sessionpaths, destdir=tmpdir)
    assert op.isfile(pdfpath)


@pytest.mark.slow
def test_web_report():
    """Test creation of web report"""
    # fake classes for dash_report progress signaling
    class Foo:
        canceled = None

    class Bar:
        def emit(*args):
            pass

    foo = Foo()
    foo.progress = Bar()

    # single session
    app = web.dash_report([sessiondir_abs], info=None, signals=foo, recreate_plots=True)
    assert app

    # video-only
    app = web.dash_report(
        [sessiondir_abs],
        info=None,
        signals=foo,
        recreate_plots=True,
        video_only=True,
    )
    assert app

    # comparison
    app = web.dash_report(
        [sessiondir_abs, sessiondir2_abs],
        info=None,
        signals=foo,
        recreate_plots=True,
    )

    # video-only comparison
    app = web.dash_report(
        [sessiondir_abs, sessiondir2_abs],
        info=None,
        signals=foo,
        recreate_plots=True,
        video_only=True,
    )

    assert app
