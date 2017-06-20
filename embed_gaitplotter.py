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
        # don't pass this arg to superclass __init__
        checkable = kwargs.pop('checkable')
        super(NiceListWidgetItem, self).__init__(*args, **kwargs)
        if checkable:
            self.setFlags(self.flags() | QtCore.Qt.ItemIsUserCheckable)

    @property
    def mydata(self):
        return super(NiceListWidgetItem, self).data(QtCore.Qt.UserRole)

    @mydata.setter
    def mydata(self, _data):
        if _data is not None:
            super(NiceListWidgetItem, self).setData(QtCore.Qt.UserRole, _data)

    @property
    def checkstate(self):
        return super(NiceListWidgetItem, self).checkState()

    @checkstate.setter
    def checkstate(self, checked):
        state = QtCore.Qt.Checked if checked else QtCore.Qt.Unchecked
        super(NiceListWidgetItem, self).setCheckState(state)


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
    def checked_items(self):
        """ Yield checked items """
        return (item for item in self.items if item.checkstate)

    def check_all(self):
        """ Check all items """
        for item in self.items:
            item.checkstate = True

    def check_none(self):
        """ Uncheck all items """
        for item in self.items:
            item.checkstate = False

    def add_item(self, txt, data=None, checkable=False, checked=False):
        """ Add checkable item with data """
        item = NiceListWidgetItem(txt, self, checkable=checkable)
        item.mydata = data
        if checkable:
            item.checkstate = checked

    def rm_current_item(self):
        self.takeItem(self.row(self.currentItem()))


class PlotterWindow(QtWidgets.QMainWindow):

    def __init__(self, parent=None):
        super(PlotterWindow, self).__init__(parent)

        uifile = 'plotter_gui.ui'
        uic.loadUi(uifile, self)

        self.pl = Plotter(interactive=False)
        self.canvas = FigureCanvas(self.pl.fig)
        self.canvas.setSizePolicy(QtWidgets.QSizePolicy.Expanding,
                                  QtWidgets.QSizePolicy.Expanding)
        # self.setStyleSheet("background-color: white;");
        # canvas into last column, span all rows
        self.mainGridLayout.addWidget(self.canvas, 0,
                                      self.mainGridLayout.columnCount(),
                                      self.mainGridLayout.rowCount(), 1)

        # this is the Navigation widget
        # it takes the Canvas widget and a parent
        #self.toolbar = NavigationToolbar(self.canvas, self)

        self.listTrials.itemClicked.connect(self._trial_selected)
        # set up widgets
        self.btnAddNexusTrial.clicked.connect(self._open_nexus_trial)
        self.btnPlot.clicked.connect(self._plot_trials)
        self.btnQuit.clicked.connect(self.close)
        self.btnSelectAllCycles.clicked.connect(self.listTrialCycles.check_all)
        self.btnSelectForceplateCycles.clicked.connect(self._select_forceplate_cycles)
        self.btnSelect1stCycles.clicked.connect(self._select_1st_cycles)
        self.btnPickCycles.clicked.connect(self._pick_cycles)
        self.btnAddC3DTrial.clicked.connect(self.load_dialog)
        self.btnSavePDF.clicked.connect(self._write_pdf)
        self.btnDeleteTrial.clicked.connect(self.rm_trial)
        self.cbLayout.addItems(sorted(cfg.layouts.__dict__.keys()))
        self._set_status('Ready')

    def rm_trial(self):
        if self.listTrials.currentItem():
            self.listTrials.rm_current_item()
            self.listTrialCycles.clear()

    def _set_status(self, msg):
        self.statusbar.showMessage(msg)

    def _trial_selected(self, item):
        """ User clicked on trial """
        trial = item.mydata
        self._update_trial_cycles_list(trial)

    def _update_trial_cycles_list(self, trial):
        """ Show cycles of given trial in the trial cycle list """
        cycles = trial.cycles
        self.listTrialCycles.clear()
        for cycle in cycles:
            self.listTrialCycles.add_item(cycle.name, data=cycle,
                                          checkable=True)

    def _select_forceplate_cycles(self):
        """ Select all forceplate cycles in the trial cycles list """
        self.listTrialCycles.check_none()
        for item in self.listTrialCycles.items:
            if item.mydata.on_forceplate:
                item.checkstate = True

    def _select_1st_cycles(self):
        """ Select 1st L/R cycles in the trial cycles list """
        self.listTrialCycles.check_none()
        for item in self.listTrialCycles.items:
            if item.mydata.index == 1:
                item.checkstate = True

    def _pick_cycles(self):
        """ Add selected cycles to overall list """
        old_cycles = (item.mydata for item in self.listCyclesToPlot.items)
        new_cycles = (item.mydata for item in
                      self.listTrialCycles.checked_items)
        for cycle in set(new_cycles) - set(old_cycles):
            name = '%s: %s' % (cycle.trial.trialname, cycle.name)
            self.listCyclesToPlot.add_item(name, data=cycle)

    def _open_nexus_trial(self):
        self._open_trial(nexus.viconnexus())

    def _open_trial(self, source):
        tr = Trial(source)
        trials = (item.mydata for item in self.listTrials.items)
        if tr.trialname in [trial.trialname for trial in trials]:
            return  # trial already loaded (based on name) TODO: clashes?
        self._update_trial_cycles_list(tr)
        self.listTrials.add_item(tr.trialname, data=tr)
        self._set_status('Loaded trial %s' % tr.trialname)

    def _plot_trials(self):
        """ Plot user-picked trials """
        self.pl.fig.clear()
        cycles = (cycle.mydata for cycle in self.listCyclesToPlot.items)
        if not cycles:
            self.message_dialog('No cycles selected for plotting')
        else:
            self.pl.layout = cfg.layouts.__dict__[self.cbLayout.currentText()]
            match_pig_kinetics = self.xbKineticsFpOnly.checkState()
            for cyc in cycles:
                self.pl.plot_trial(trial=cyc.trial, model_cycles=[cyc],
                                   emg_cycles=[cyc],
                                   match_pig_kinetics=match_pig_kinetics,
                                   maintitle='', superpose=True)
            self.canvas.draw()
            self.btnSavePDF.setEnabled(True)  # can create pdf now

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