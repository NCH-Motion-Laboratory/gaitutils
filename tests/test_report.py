# -*- coding: utf-8 -*-
"""

Test reporting functions.

@author: Jussi (jnu@iki.fi)
"""

import pytest
import logging
import tempfile
from pathlib import Path

from gaitutils.report import pdf, web
from utils import _file_path

logger = logging.getLogger(__name__)


# test session
sessiondir_ = Path('test_subjects/D0063_RR/2018_12_17_preOp_RR')
sessiondir_abs = _file_path(sessiondir_)

sessiondir2_ = Path('test_subjects/D0063_RR/2018_12_17_preOp_tuet_RR')
sessiondir2_abs = _file_path(sessiondir2_)

sessiondir_name = sessiondir_.name
tmpdir = Path(tempfile.gettempdir())


@pytest.mark.slow
def test_pdf_report():
    """Test creation of pdf report + time-distance text report"""
    pdfpath = tmpdir / (sessiondir_name + '.pdf')
    timedist_path = tmpdir / (sessiondir_name + '_time_distance.txt')
    if pdfpath.is_file():
        pdfpath.unlink()
    if timedist_path.is_file():
        timedist_path.unlink()
    pdf.create_report(
        sessiondir_abs, destdir=tmpdir, write_timedist=True, write_extracted=True
    )
    assert pdfpath.is_file()
    assert timedist_path.is_file()


@pytest.mark.slow
def test_pdf_comparison_report():
    """Test creation of pdf comparison report"""
    sessionpaths = [sessiondir_abs, sessiondir2_abs]
    # resulting pdf name - must be set according to what is defined in the function
    pdfname = ' VS '.join(sp.name for sp in sessionpaths) + '.pdf'
    pdfpath = tmpdir / pdfname
    if pdfpath.is_file():
        pdfpath.unlink()
    pdf.create_comparison_report(sessionpaths, destdir=tmpdir)
    assert pdfpath.is_file()


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
