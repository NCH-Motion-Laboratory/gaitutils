# -*- coding: utf-8 -*-
"""
Embed gaitplotter figure canvas into PyQt5 GUI
WIP

TODO:
    Plotter should probably create figure at init()
    (so that valid figure instance is available without loading trial)
    


@author: Jussi (jnu@iki.fi)
"""

import sys
from PyQt5 import QtGui, QtWidgets, uic
from matplotlib.backends.backend_qt5agg import (FigureCanvasQTAgg as
                                                FigureCanvas)
from matplotlib.backends.backend_qt5agg import (NavigationToolbar2QT as
                                                NavigationToolbar)
from matplotlib.figure import Figure
from gaitutils import Plotter, Trial, layouts, cfg
import logging


class PlotterWindow(QtWidgets.QMainWindow):
    def __init__(self, parent=None):
        super(PlotterWindow, self).__init__(parent)

        uifile = 'plotter_gui.ui'
        uic.loadUi(uifile, self)

        self.trials = dict()

        self.pl = Plotter(interactive=False)
        self.pl.open_nexus_trial()
        self.pl.layout = cfg.layouts.std_emg
        self.pl.plot_trial()
        
        # this is the Canvas Widget that displays the `figure`
        # it takes the `figure` instance as a parameter to __init__
        # self.canvas = FigureCanvas(self.pl.fig)
        
        self.canvas = FigureCanvas(self.pl.fig)

        # self.setStyleSheet("background-color: white;");
        # canvas into last column, span all rows
        self.mainGridLayout.addWidget(self.canvas, 0, 3, 
                                      self.mainGridLayout.rowCount(), 1)
        # this is the Navigation widget
        # it takes the Canvas widget and a parent
        #self.toolbar = NavigationToolbar(self.canvas, self)

        # set up widgets
        self.btnOpenNexusTrial.clicked.connect(self.pl.open_nexus_trial)
        self.btnPlot.clicked.connect(self.draw_canvas)
        self.btnAddC3D.clicked.connect(self.load_dialog)
        self.btnDelC3D.clicked.connect(self.rm_c3d)
        self.cbLayout.addItems(cfg.layouts.__dict__.keys())


    def rm_c3d(self):
        self.listC3D.takeItem(self.listC3D.row(self.listC3D.currentItem()))
    
            
    @staticmethod
    def _enum_cycles(cycles):
        """ Enumerate cycles into strings R1, R2, L1 etc. """
        for k, cyc in enumerate(cycles):
            yield '%s%d' % (cyc.context, k)
            
    def _count_cycles(self, trial):
        """ Enumerate all cycles of trial as above """
        rcycles = [cyc for cyc in trial.cycles if cyc.context == 'R']
        lcycles = [cyc for cyc in trial.cycles if cyc.context == 'L']
        return list(self._enum_cycles(rcycles)) + list(self._enum_cycles(lcycles))
    
    def _common_cycles(self):
        """ Find cycles that are common to all loaded c3d trials """
        allcycles = []
        for trial in self.trials.items():
            allcycles.append(set(self._count_cycles(trial.cycles)))
        return set.intersection(*allcycles)

    def load_dialog(self):
        """ Bring up load dialog and load selected c3d file. """
        fname = QtWidgets.QFileDialog.getOpenFileName(self, 'Open C3D file',
                                                      '*.c3d')[0]
        if fname:
            fname = unicode(fname)
            tr = Trial(fname)
            self.trials[fname] = tr
            self.listC3D.addItem(fname)
            cycles = self._count_cycles(tr)
            self.listCycles.addItems(cycles)

    def draw_canvas(self):
        self.pl.fig.clear()
        self.pl.layout = cfg.layouts.__dict__[self.cbLayout.currentText()]
        self.pl.plot_trial()
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