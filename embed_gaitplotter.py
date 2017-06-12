# -*- coding: utf-8 -*-
"""
Embed gaitplotter figure canvas into PyQt5 GUI
WIP


open trial 

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
import logging


class PlotterWindow(QtWidgets.QMainWindow):
    def __init__(self, parent=None):
        super(PlotterWindow, self).__init__(parent)

        self.pl = Plotter()
        self.pl.layout = cfg.layouts.lb_kin
        self.pl.open_nexus_trial()
        self.pl.plot_trial(interactive=False)      
        uifile = 'plotter_gui.ui'
        uic.loadUi(uifile, self)
        
        # this is the Canvas Widget that displays the `figure`
        # it takes the `figure` instance as a parameter to __init__
        self.canvas = FigureCanvas(self.pl.fig)

        # self.setStyleSheet("background-color: white;");
        # canvas into last column, span all rows
        self.mainGridLayout.addWidget(self.canvas, 0,
                                      self.mainGridLayout.columnCount(), 
                                      self.mainGridLayout.rowCount(), 1)
        # this is the Navigation widget
        # it takes the Canvas widget and a parent
        #self.toolbar = NavigationToolbar(self.canvas, self)

        # set up widgets
        self.btnOpenNexusTrial.clicked.connect(self.pl.open_nexus_trial)
        self.btnPlot.clicked.connect(self.draw_canvas)

    def draw_canvas(self):
        self.pl.fig.clear()
        self.pl.plot_trial(interactive=False)      
        self.canvas.draw()


if __name__ == '__main__':
   
    logging.basicConfig(level=logging.DEBUG)

    app = QtWidgets.QApplication(sys.argv)
    win = PlotterWindow()
    win.show()

    sys.exit(app.exec_())