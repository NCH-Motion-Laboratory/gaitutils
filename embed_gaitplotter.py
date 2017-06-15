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


class gpCanvas(FigureCanvas):
    
    def __init__(self, figure):
        super(gpCanvas, self).__init__(figure)

    def refresh(self, figure):
        super(gpCanvas, self).__init__(figure)
        self.draw()
    

class PlotterWindow(QtWidgets.QMainWindow):
    def __init__(self, parent=None):
        super(PlotterWindow, self).__init__(parent)

        uifile = 'plotter_gui.ui'
        uic.loadUi(uifile, self)

        self.pl = Plotter()
        self.pl.layout = cfg.layouts.lb_kin
        self.pl.open_nexus_trial()
        self.pl.plot_trial(interactive=False)
        
        # this is the Canvas Widget that displays the `figure`
        # it takes the `figure` instance as a parameter to __init__
        # self.canvas = FigureCanvas(self.pl.fig)
        
        self.canvas = gpCanvas(self.pl.fig)

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
        # self.canvas.figure = self.pl.fig
        #self.canvas = FigureCanvas(self.pl.fig)
        #self.mainGridLayout.addWidget(self.canvas, 0,
        #                              self.mainGridLayout.columnCount(), 
        #                              self.mainGridLayout.rowCount(), 1)
        self.canvas.draw()

if __name__ == '__main__':
   
    logging.basicConfig(level=logging.DEBUG)

    app = QtWidgets.QApplication(sys.argv)
    win = PlotterWindow()
    win.show()

    sys.exit(app.exec_())