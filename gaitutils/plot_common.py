#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Created on Tue Apr 28 11:37:51 2015

Plot currently loaded Nexus trial.

@author: Jussi (jnu@iki.fi)
"""

from PyQt5 import QtWidgets
import plotly

from .gui import qt_dialogs
from .config import cfg


def show_fig(fig, backend=None):
    """Simple interactive show fig thing, intended for command line scripts"""
    if backend is None:
        backend = cfg.plot.backend
    if backend == 'matplotlib':
        app = QtWidgets.QApplication([])
        _mpl_win = qt_dialogs.qt_matplotlib_window(fig)
        app.exec_()
    elif backend == 'plotly':
        plotly.offline.plot(fig)
