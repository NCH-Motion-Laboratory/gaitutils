# -*- coding: utf-8 -*-
"""
Embed gaitplotter figure canvas into PyQt5 GUI
WIP


@author: Jussi (jnu@iki.fi)
"""

import sys
from PyQt5 import QtGui, QtWidgets, uic
from matplotlib.backends.backend_qt5agg import (FigureCanvasQTAgg as
                                                FigureCanvas)
from matplotlib.backends.backend_qt5agg import (NavigationToolbar2QT as
                                                NavigationToolbar)
from matplotlib.figure import Figure
from gaitutils import Plotter, layouts, cfg


class PlotterWindow(QtWidgets.QMainWindow):
    def __init__(self, parent=None):
        super(PlotterWindow, self).__init__(parent)

        pl = Plotter()
        pl.open_nexus_trial()
        pl.layout = cfg.layouts.lb_kin
        pl.plot_trial(interactive=False)
        uifile = 'plotter_gui.ui'
        uic.loadUi(uifile, self)
        
        self.figure = pl.fig

        # this is the Canvas Widget that displays the `figure`
        # it takes the `figure` instance as a parameter to __init__
        self.canvas = FigureCanvas(self.figure)

        # self.setStyleSheet("background-color: white;");
        # canvas into last column, span all rows
        self.mainGridLayout.addWidget(self.canvas, 0,
                                      self.mainGridLayout.columnCount(), 
                                      self.mainGridLayout.rowCount(), 1)
        # this is the Navigation widget
        # it takes the Canvas widget and a parent
        #self.toolbar = NavigationToolbar(self.canvas, self)

    def plot(self):
      
        # refresh canvas
        self.canvas.draw()

if __name__ == '__main__':
   
    app = QtWidgets.QApplication(sys.argv)
    win = PlotterWindow()
    win.show()

    sys.exit(app.exec_())