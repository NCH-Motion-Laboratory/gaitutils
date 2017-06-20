# -*- coding: utf-8 -*-
"""
Embed gaitplotter figure canvas into PyQt5 GUI
WIP

TODO:
     WIP
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
from gaitutils import Plotter, Trial, nexus, layouts, cfg
import logging

logger = logging.getLogger(__name__)


class NiceListWidgetItem(QtWidgets.QListWidgetItem):
    """ Make list items more pythonic - otherwise would have to do horrible and
    bug-prone things like checkState() """

    def __init__(self, *args, **kwargs):
        super(NiceListWidgetItem, self).__init__(*args, **kwargs)

    @property
    def data(self):
        return super(NiceListWidgetItem, self).data(QtCore.Qt.UserRole)

    @data.setter
    def data(self, _data):
        if _data is not None:
            super(NiceListWidgetItem, self).setData(_data, QtCore.Qt.UserRole)

    @property
    def checkState(self):
        return super(NiceListWidgetItem, self).checkState()


class NiceListWidget(QtWidgets.QListWidget):
    """ Adds some convenience to QListWidget """

    def __init__(self, parent=None):
        super(NiceListWidget, self).__init__(parent)

    @property
    def items(self):
        """ Yield all items """
        for i in range(self.count()):
            yield self.item(i)

    @property
    def items_data(self):
        """ Yield data from all items """
        return (item.data(QtCore.Qt.UserRole) for item in self.items)

    @property
    def checked(self):
        """ Yield checked items """
        return (item for item in self.items if item.checkState)

    @property
    def checked_data(self):
        """ Yield data from checked items """
        for item in self.checked:
            yield item.data(QtCore.Qt.UserRole)

    def check_all(self):
        """ Check all items """
        for item in self.items:
            item.setCheckState(QtCore.Qt.Checked)

    def check_none(self):
        """ Check all items """
        for item in self.items:
            item.setCheckState(QtCore.Qt.Unchecked)

    def add_item(self, txt, data=None, checkable=False, checked=False):
        """ Add checkable item with data """
        item = NiceListWidgetItem(txt, self)
        if checkable:
            item.setFlags(item.flags() | QtCore.Qt.ItemIsUserCheckable)
            item.setCheckState(QtCore.Qt.Checked if checked else
                               QtCore.Qt.Unchecked)
            item.data = data

    def rm_current_item(self):
        self.takeItem(self.row(self.currentItem()))


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

        self.listTrials.itemClicked.connect(self._trial_selected)
        # set up widgets
        self.btnAddNexusTrial.clicked.connect(self._open_nexus_trial)
        self.btnPlot.clicked.connect(self.draw_canvas)
        self.btnQuit.clicked.connect(self.close)
        self.btnSelectAllCycles.clicked.connect(self.listTrialCycles.check_all)
        self.btnSelectForceplateCycles.clicked.connect(self._select_forceplate_cycles)
        self.btnSelect1stCycles.clicked.connect(self._select_1st_cycles)
        self.btnPickCycles.clicked.connect(self._pick_cycles)
        self.btnAddC3DTrial.clicked.connect(self.load_dialog)
        self.btnSavePDF.clicked.connect(self._write_pdf)
        self.btnDeleteTrial.clicked.connect(self.rm_c3d)
        self.cbLayout.addItems(sorted(cfg.layouts.__dict__.keys()))
        self._set_status('Ready')

    def rm_c3d(self):
        self.listC3D.rm_current_item()

    def _set_status(self, msg):
        self.statusbar.showMessage(msg)

    @staticmethod
    def _describe_cycles(cycles, verbose=True, fp_info=True, trialname=False):
        sidestrs = {'R': 'Right', 'L': 'Left'}
        counter = {'R': 0, 'L': 0}
        for cyc in cycles:
            counter[cyc.context] += 1
            sidestr = sidestrs[cyc.context] if verbose else cyc.context
            desc = '%s %d' % (sidestr, counter[cyc.context])
            if fp_info:
                desc += ' (on forceplate)' if cyc.on_forceplate else ''
            if trialname:
                desc = '%s: %s' % (cyc.trial.trialname, desc)
            yield desc

    def _trial_selected(self, item):
        """ User clicked on trial """
        trial = item.data(QtCore.Qt.UserRole)
        self._update_trial_cycles_list(trial)

    def _update_trial_cycles_list(self, trial):
        """ Show cycles of given trial in the trial cycle list """
        cycles = trial.cycles
        self.listTrialCycles.clear()
        for cycle, desc in zip(cycles, self._describe_cycles(cycles)):
            self.listTrialCycles.add_item(desc, data=cycle, checkable=True)

    def _select_forceplate_cycles(self):
        """ Select all forceplate cycles in the trial cycles list """
        self.listTrialCycles.check_none()
        for item in self.listTrialCycles.items:
            if item.data(QtCore.Qt.UserRole).on_forceplate:
                item.setCheckState(QtCore.Qt.Checked)

    def _select_1st_cycles(self):
        """ Select 1st L/R cycles in the trial cycles list """
        self.listTrialCycles.check_none()
        descriptions = self._describe_cycles(self.listTrialCycles.items_data,
                                             fp_info=False)
        for desc, item in zip(descriptions, self.listTrialCycles.items):
            if desc[-1] == '1':
                item.setCheckState(QtCore.Qt.Checked)

    def _pick_cycles(self):
        cycles = self.listTrialCycles.checked_data
        items = self.listTrialCycles.checked
        logger.debug(list(items))
        for cycle in cycles:
            self.listCyclesToPlot.add_item(cycle.name, data=cycle)

    def _open_nexus_trial(self):
        self._open_trial(nexus.viconnexus())

    def _open_trial(self, source):
        tr = Trial(source)
        if tr.trialname in [trial.trialname for trial in self.trials]:
            return  # trial already loaded (based on name) TODO: clashes?
        self.trials.append(tr)
        self._update_trial_cycles_list(tr)
        self.listTrials.add_item(tr.trialname, data=tr)
        self._set_status('Loaded trial %s' % tr.trialname)

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
            self._open_trial(fname)

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
            self.btnSavePDF.setEnabled(True)  # can create pdf now

    def _write_pdf(self):
        """ Bring up save dialog and save data. """
        # TODO: set default PDF name?
        # TODO: where to write (in case of multiple session dirs)
        fout = QtWidgets.QFileDialog.getSaveFileName(self,
                                                     'Save PDF',
                                                     self.trials[0].
                                                     sessionpath,
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