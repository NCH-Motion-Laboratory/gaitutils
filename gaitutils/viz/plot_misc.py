# -*- coding: utf-8 -*-
"""

misc plotting related stuff

@author: Jussi (jnu@iki.fi)
"""

from PyQt5 import QtWidgets
import plotly

from ..gui import qt_dialogs
from ..config import cfg


def show_fig(fig, backend=None):
    """Simple interactive show fig thing, intended for command line scripts"""
    if backend is None:
        backend = cfg.plot.backend
    if backend == 'matplotlib':
        app = QtWidgets.QApplication([])
        qt_dialogs.qt_matplotlib_window(fig)
        app.exec_()
    elif backend == 'plotly':
        plotly.offline.plot(fig)
