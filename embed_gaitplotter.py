# -*- coding: utf-8 -*-
"""
Embed gaitplotter figure canvas into PyQt5 GUI
WIP

TODO:
    -maybe inherit QListWidget for cycles widget to get neater code (methods)
    -realtime updates to plot on widget changes (needs plotter to be faster?)
    -treat Nexus trial like c3d trials (add to list)
    -cycle logic for multiple trials (common cycles ?)
    -title and legend options for pdf writer  (figlegend?)
    -trial averaging / stddev (separate plot button)

@author: Jussi (jnu@iki.fi)
"""

import sys
from PyQt5 import QtGui, QtWidgets, uic, QtCore
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

        self.trials = list()

        self.pl = Plotter(interactive=False)
        #self.pl.open_nexus_trial()
        #self.pl.layout = cfg.layouts.std_emg
        #self.pl.plot_trial()
        # this is the Canvas Widget that displays the `figure`
        # it takes the `figure` instance as a parameter to __init__
        # self.canvas = FigureCanvas(self.pl.fig)

        self.canvas = FigureCanvas(self.pl.fig)

        # self.setStyleSheet("background-color: white;");
        # canvas into last column, span all rows
        self.mainGridLayout.addWidget(self.canvas, 0,
                                      self.mainGridLayout.columnCount(),
                                      self.mainGridLayout.rowCount(), 1)
        self.canvas.setSizePolicy(QtWidgets.QSizePolicy.Expanding,
                                  QtWidgets.QSizePolicy.Expanding)
        # this is the Navigation widget
        # it takes the Canvas widget and a parent
        #self.toolbar = NavigationToolbar(self.canvas, self)

        # set up widgets
        self.btnAddNexusTrial.clicked.connect(self._open_nexus_trial)
        self.btnPlot.clicked.connect(self.draw_canvas)
        self.btnQuit.clicked.connect(self.close)
        self.btnSelectAllCycles.clicked.connect(self._select_all_cycles)
        self.btnAddC3DTrial.clicked.connect(self.load_dialog)
        self.btnSavePDF.clicked.connect(self._write_pdf)
        self.btnDeleteTrial.clicked.connect(self.rm_c3d)
        self.cbLayout.addItems(sorted(cfg.layouts.__dict__.keys()))
        self._set_status('Ready')

    def rm_c3d(self):
        self.listC3D.takeItem(self.listC3D.row(self.listC3D.currentItem()))

    def _set_status(self, msg):
        self.statusbar.showMessage(msg)

    @staticmethod
    def _describe_cycles(cycles, fp_info=True):
        sidestr = {'R': 'Right', 'L': 'Left'}
        counter = {'R': 0, 'L': 0}
        for cyc in cycles:
            counter[cyc.context] += 1
            desc = '%s %d' % (sidestr[cyc.context], counter[cyc.context])
            if fp_info:
                desc += ' (on forceplate)' if cyc.on_forceplate else ''
            yield desc
            
    def _update_cycles_list(self):
        """ Update displayed list of gait cycles according to loaded trials.
        If multiple trials are loaded, cycles will be intersected (i.e. only
        cycles that are present for all trials will be available for
        selection) """
        if len(self.trials) == 1:
            cycles = self.trials[0].cycles
            for cycle, desc in zip(cycles, self._describe_cycles(cycles)):
                item = QtWidgets.QListWidgetItem(desc, self.listCycles)
                item.setFlags(item.flags() | QtCore.Qt.ItemIsUserCheckable)
                item.setCheckState(QtCore.Qt.Unchecked)
                item.setData(QtCore.Qt.UserRole, cycle)

    def _cycles_to_plot(self):
        """ Return gait cycles that the user has selected for plotting """
        for i in range(self.listCycles.count()):
            item = self.listCycles.item(i)
            if item.checkState():
                yield item.data(QtCore.Qt.UserRole)
                
    def _select_all_cycles(self):
        for i in range(self.listCycles.count()):
            item = self.listCycles.item(i)
            item.setCheckState(QtCore.Qt.Checked)

    def _open_nexus_trial(self):
        self.pl.open_nexus_trial()
        self.trials.append(self.pl.trial)
        self._update_cycles_list()
        self._set_status('Loaded Nexus trial')
    
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
            self.listCycles.addItems(self.describe_cycles(tr.cycles))

    def message_dialog(self, msg):
        """ Show message with an 'OK' button. """
        dlg = QtWidgets.QMessageBox()
        dlg.setWindowTitle('Message')
        dlg.setText(msg)
        dlg.addButton(QtWidgets.QPushButton('Ok'),
                      QtWidgets.QMessageBox.YesRole)
        dlg.exec_()

    def draw_canvas(self):
        cycles = list(self._cycles_to_plot())
        if not cycles:
            self.message_dialog('No cycles selected for plotting')
        else:
            self.pl.layout = cfg.layouts.__dict__[self.cbLayout.currentText()]
            match_pig_kinetics = self.xbKineticsFpOnly.checkState()
            self.pl.plot_trial(model_cycles=cycles, emg_cycles=cycles,
                               match_pig_kinetics=match_pig_kinetics,
                               maintitle='')
            self.canvas.draw()
            self.btnSavePDF.setEnabled(True)

    def _write_pdf(self):
        """ Bring up save dialog and save data. """
        # TODO: set default PDF name?
        # TODO: where to write (in case of multiple session dirs)
        fout = QtWidgets.QFileDialog.getSaveFileName(self,
                                                     'Save PDF',
                                                     self.trials[0].sessionpath,
                                                     '*.pdf')
        fname = fout[0]
        if fname:
            fname = unicode(fname)
            self.pl.set_title(self.pl.title_with_eclipse_info())
            self.canvas.print_figure(fname)
            self.pl.set_title('')
            self.canvas.draw()


if __name__ == '__main__':
   
    logging.basicConfig(level=logging.DEBUG)

    app = QtWidgets.QApplication(sys.argv)
    win = PlotterWindow()
    win.show()

    sys.exit(app.exec_())