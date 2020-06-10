# -*- coding: utf-8 -*-
"""

misc plotting related stuff

@author: Jussi (jnu@iki.fi)
"""

import plotly
from matplotlib.figure import Figure
from PyQt5 import QtWidgets
import tempfile
import os.path as op
import subprocess
import logging

from . import plot_matplotlib, plot_plotly
from ..config import cfg
from ..gui import qt_dialogs

logger = logging.getLogger(__name__)


def _show_plotly_fig(fig):
    """Show a Plotly fig in the configured browser"""
    tmp_html = op.join(tempfile.gettempdir(), 'gaitutils_temp.html')
    plotly.offline.plot(fig, filename=tmp_html, auto_open=False, validate=False)
    _browse_localhost(url='file:///%s' % tmp_html)


def _browse_localhost(url=None, port=None):
    """Open configured browser on url or localhost:port"""
    if not url:
        if port:
            url = '127.0.0.1:%d' % port
        else:
            raise ValueError('neither url nor valid localhost port specified')
    try:
        proc = subprocess.Popen([cfg.general.browser_path, url])
        logger.debug('new browser pid %d' % proc.pid)
    except Exception:
        raise RuntimeError(
            'Cannot start configured web browser: %s' % cfg.general.browser_path
        )


def get_backend(backend_name):
    """Return plotting backend module.

    Parameters
    ----------
    backend_name : str | None
        Name of the backend. Currently supported backends are 'plotly' and
        'matplotlib'. If None, return configured default backend.

    Returns
    -------
    backend : module
        The module.
    """
    if backend_name is None:
        backend_name = cfg.plot.backend
    backends = {'plotly': plot_plotly, 'matplotlib': plot_matplotlib}
    if backend_name not in backends:
        raise ValueError('no such plotting backend %s' % backend_name)
    return backends[backend_name]


def show_fig(fig):
    """Show a figure created by the plotting functions.

    What actually happens depends on the backend. Plotly figures are shown in a
    browser window. For matplotlib plots, a new Qt window is created and the
    plot is shown there.

    Parameters
    ----------
    fig : Figure | dict
        The figure to show.
    """
    if not fig:
        raise ValueError('No figure to show')
    if isinstance(fig, Figure):  # matplotlib
        app = QtWidgets.QApplication([])
        win = qt_dialogs.qt_matplotlib_window(fig)
        app.exec_()
    else:  # plotly
        # plotly figures may be of different types (list of traces etc.)
        # so just lazily hope that it's actually a plotly figure
        _show_plotly_fig(fig)
