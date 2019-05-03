# -*- coding: utf-8 -*-
"""

misc plotting related stuff

@author: Jussi (jnu@iki.fi)
"""

import plotly
from matplotlib.figure import Figure
from PyQt5 import QtWidgets

from . import plot_matplotlib, plot_plotly
from ..config import cfg
from ..gui import qt_dialogs


def get_backend(backend_name):
    """Returns plotting backend module according to name, default for None"""
    if backend_name is None:
        backend_name = cfg.plot.backend
    backends = {'plotly': plot_plotly, 'matplotlib': plot_matplotlib}
    return backends[backend_name]


def show_fig(fig):
    if not fig:
        raise ValueError('No figure to show')
    if isinstance(fig, Figure):  # matplotlib
        app = QtWidgets.QApplication([])
        win = qt_dialogs.qt_matplotlib_window(fig)
        app.exec_()
    else:  # plotly
        # plotly figures may be of different types (list of traces etc.)
        # so just lazily hope that it's actually a plotly figure
        plotly.offline.plot(fig)
