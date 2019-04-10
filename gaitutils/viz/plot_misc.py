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


def backend_selector(backend_name):
    backends = {'plotly': plot_plotly, 'matplotlib': plot_matplotlib}
    return backends[backend_name]


def show_fig(fig):
    if not fig:
        raise ValueError('No figure to show')
    if isinstance(fig, Figure):  # matplotlib
        app = QtWidgets.QApplication([])
        win = qt_dialogs.qt_matplotlib_window(fig)
        app.exec_()
    else:  # hopefully plotly
        plotly.offline.plot(fig)
