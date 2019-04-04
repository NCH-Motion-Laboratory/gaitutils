# -*- coding: utf-8 -*-
"""

misc plotting related stuff

@author: Jussi (jnu@iki.fi)
"""

from PyQt5 import QtWidgets
import plotly

from ..gui import qt_dialogs
from ..config import cfg

from matplotlib.figure import Figure


def show_fig(fig):
    if not fig:
        raise ValueError('No figure to show')
    if isinstance(fig, Figure):  # matplotlib
        app = QtWidgets.QApplication([])
        win = qt_dialogs.qt_matplotlib_window(fig)
        app.exec_()
    else:  # hopefully plotly
        plotly.offline.plot(fig)
