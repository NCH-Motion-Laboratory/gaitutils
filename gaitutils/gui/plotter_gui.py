#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Embed gaitplotter figure canvas into PyQt5 GUI
WIP


@author: Jussi (jnu@iki.fi)
"""

from builtins import str
import logging
import sys
import traceback
from pkg_resources import resource_filename
from PyQt5 import QtWidgets, uic, QtCore
from matplotlib.backends.backend_qt5agg import (FigureCanvasQTAgg as
                                                FigureCanvas)
from matplotlib.backends.backend_qt5agg import (NavigationToolbar2QT as
                                                NavigationToolbar)

from .. import (Plotter, Trial, nexus, layouts, cfg, GaitDataError,
                stats)
from .qt_dialogs import qt_message_dialog, OptionsDialog

logger = logging.getLogger(__name__)


def _trial_namestr(trial):
    return u'%s  %s  %s' % (trial.trialname, trial.eclipse_data['DESCRIPTION'],
                            trial.eclipse_data['NOTES'])


class AveragerDialog(QtWidgets.QDialog):

    def __init__(self, parent=None):
        super(self.__class__, self).__init__()
        uifile = resource_filename('gaitutils', 'gui/averager.ui')
        uic.loadUi(uifile, self)

        self.btnAddNexusTrial.clicked.connect(self._open_nexus_trial)
        self.btnAddC3DTrial.clicked.connect(self.load_dialog)
        self.btnDoAverage.clicked.connect(self.accept)
        self.btnCancel.clicked.connect(self.reject)

    def _open_nexus_trial(self):
        try:
            vicon = nexus.viconnexus()
            self._open_trial(vicon)
        except GaitDataError:
            qt_message_dialog('Vicon Nexus is not running')

    def _open_trial(self, source):
        tr = Trial(source)
        trials = (item.userdata for item in self.listTrials.items)
        # check if trial already loaded (based on name)
        # TODO: might use smarter detection
        if tr.trialname in [trial.trialname for trial in trials]:
            return
        self.listTrials.add_item(_trial_namestr(tr), data=tr)

    def accept(self):
        """ Do the averaging """
        trials = [item.userdata for item in self.listTrials.items]
        fp_cycles_only = self.xpFpCyclesOnly.checkState()
        self.avg = stats.AvgTrial(trials, fp_cycles_only=fp_cycles_only)
        qt_message_dialog('Averaging OK')
        self.done(QtWidgets.QDialog.Accepted)  # or call superclass accept

    def load_dialog(self):
        """ Bring up load dialog and load selected c3d file. """
        fnames = QtWidgets.QFileDialog.getOpenFileNames(self, 'Open C3D files',
                                                        '*.c3d')[0]
        if fnames:
            for fname in fnames:
                self._open_trial(fname)


class PlotterWindow(QtWidgets.QMainWindow):

    def __init__(self, parent=None):
        super(PlotterWindow, self).__init__(parent)

        uifile = resource_filename('gaitutils', 'gui/plotter_gui.ui')
        uic.loadUi(uifile, self)

        self.pl = Plotter(interactive=False)
        self.canvas = FigureCanvas(self.pl.fig)
        self.canvas.setSizePolicy(QtWidgets.QSizePolicy.Expanding,
                                  QtWidgets.QSizePolicy.Expanding)

        # these are needed for mpl callbacks to work (?)
        self.canvas.setFocusPolicy(QtCore.Qt.ClickFocus)
        self.canvas.setFocus()

        # self.setStyleSheet("background-color: white;");
        # add canvas into last column, span all rows
        self.mainGridLayout.addWidget(self.canvas, 0,
                                      self.mainGridLayout.columnCount(),
                                      self.mainGridLayout.rowCount(), 1)

        # this is the Navigation widget
        # it takes the Canvas widget and a parent
        #self.toolbar = NavigationToolbar(self.canvas, self)
        # can use this to enable selection of multiple items:
        # self.listTrials.setSelectionMode(QtWidgets.QAbstractItemView.MultiSelection)
        self.listTrials.itemPressed.connect(self._trial_selected)
        # set up widgets
        # buttons
        self.btnAddNexusTrial.clicked.connect(self._open_nexus_trial)
        self.btnPlot.clicked.connect(self._plot_trials)
        self.btnSelectAllCycles.clicked.connect(self.listTrialCycles.check_all)
        self.btnSelectForceplateCycles.clicked.connect(self.
                                                       _select_forceplate_cycles)
        self.btnSelect1stCycles.clicked.connect(self._select_1st_cycles)
        self.btnPickCycles.clicked.connect(self._pick_cycles)
        #self.btnAverageSelected.clicked.connect(self._average_selected)
        self.btnAddC3DTrial.clicked.connect(self.load_dialog)
        self.btnSavePDF.clicked.connect(self._write_pdf)
        self.btnClearTrials.clicked.connect(self._clear_trials)
        self.btnClearCyclesToPlot.clicked.connect(self.listCyclesToPlot.clear)
        self.btnOptions.clicked.connect(self._options_dialog)
        self.btnOpenNormalData.clicked.connect(self._load_normaldata)
        # menu actions
        self.actionQuit.triggered.connect(self.close)
        self.actionAverage.triggered.connect(self._averager_dialog)

        # add predefined plot layouts to combobox
        self.cbLayout.addItems(sorted(cfg.options('layouts')))

        # add normal data files
        self.cbNormalData.addItems(sorted(cfg.general.normaldata_files))

        self.canvas.mpl_connect('button_press_event', self._onclick)
        self._set_status('Ready')

    def resizeEvent(self, event):
        pass
        # adjust layout on resize
        # this does not work super well - slow and can crash
        # self.pl.tight_layout()

    def _onclick(self, event):
        logger.debug('click on %s' % event.inaxes)

    def _options_dialog(self):
        """ Show the autoprocessing options dialog """
        dlg = OptionsDialog(default_tab=1)
        dlg.exec_()

    def _averager_dialog(self):
        """ Show the autoprocessing options dialog """
        dlg = AveragerDialog()
        if dlg.exec_():
            self.listTrials.add_item('Average trial', dlg.avg)
            self._update_trial_cycles_list(dlg.avg)

    def _load_normaldata(self):
        fname = QtWidgets.QFileDialog.getOpenFileName(self,
                                                      'Open normal data', '',
                                                      'XLSX files (*.xlsx);;'
                                                      'GCD files (*.gcd);; ')
        fname = fname[0]
        if fname:
            idx = self.cbNormalData.findText(fname)
            # add file into box if it's not yet there
            if idx == -1:
                self.cbNormalData.addItem(fname)
            # select it in any case
            idx = self.cbNormalData.findText(fname)
            self.cbNormalData.setCurrentIndex(idx)

    def rm_trial(self):
        if self.listTrials.currentItem():
            self.listTrials.rm_current_item()
            self.listTrialCycles.clear()

    def _set_status(self, msg):
        self.statusbar.showMessage(msg)

    def _trial_selected(self, item):
        """ User clicked on trial """
        trial = item.userdata
        self._update_trial_cycles_list(trial)

    def _update_trial_cycles_list(self, trial):
        """ Show cycles of given trial in the trial cycle list """
        cycles = trial.cycles
        self.listTrialCycles.clear()
        for cycle in cycles:
            self.listTrialCycles.add_item(cycle.name, data=cycle,
                                          checkable=True)

    def _clear_trials(self):
        self.listTrials.clear()
        self.listTrialCycles.clear()

    def _select_forceplate_cycles(self):
        """ Select all forceplate cycles in the trial cycles list """
        self.listTrialCycles.check_none()
        for item in self.listTrialCycles.items:
            if item.userdata.on_forceplate:
                item.checkstate = True

    def _select_1st_cycles(self):
        """ Select 1st L/R cycles in the trial cycles list """
        self.listTrialCycles.check_none()
        for item in self.listTrialCycles.items:
            if item.userdata.index == 1:
                item.checkstate = True

    def _pick_cycles(self):
        """ Add selected cycles to overall list """
        # only add cycles that were not already added
        present_cycles = (item.userdata for item in
                          self.listCyclesToPlot.items)
        new_cycles = (item.userdata for item in
                      self.listTrialCycles.checked_items)
        for cycle in set(new_cycles) - set(present_cycles):
            name = '%s: %s' % (cycle.trial.trialname, cycle.name)
            self.listCyclesToPlot.add_item(name, data=cycle)

    def _open_nexus_trial(self):
        try:
            vicon = nexus.viconnexus()
            self._open_trial(vicon)
        except GaitDataError:
            qt_message_dialog('Vicon Nexus is not running')

    def _open_trial(self, source):
        tr = Trial(source)
        trials = (item.userdata for item in self.listTrials.items)
        # check if trial already loaded (based on name)
        # TODO: might use smarter detection
        if tr.trialname in [trial.trialname for trial in trials]:
            return
        self.listTrials.add_item(_trial_namestr(tr), data=tr)
        self._update_trial_cycles_list(tr)
        self._set_status('Loaded trial %s' % tr.trialname)

    def _plot_trials(self):
        """ Plot user-picked trials """
        # Holds cycles to plot, keyed by trial. This will make for less calls
        # to plot_trial() as we only need to call once per trial.
        plot_cycles = dict()
        self.pl.fig.clear()

        cycles = [item.userdata for item in self.listCyclesToPlot.items]
        if not cycles:
            qt_message_dialog('No cycles selected for plotting')
            return

        # gather the cycles and key by trial
        for cycle in cycles:
            if cycle.trial not in plot_cycles:
                plot_cycles[cycle.trial] = []
            plot_cycles[cycle.trial].append(cycle)

        # set options and create the plot
        lout = cfg.layouts.__getattr__(self.cbLayout.currentText())
        # remove legends - they do not make sense here
        lout = layouts.filter_layout(lout, 'legend', None)
        self.pl.layout = lout
        match_pig_kinetics = self.xbKineticsFpOnly.checkState()

        if self.xbNormalData.checkState():
            plot_model_normaldata = True
            try:
                fn = self.cbNormalData.currentText()
                self.pl.add_normaldata(fn)
            except (ValueError, GaitDataError):
                qt_message_dialog('Error reading normal data from %s' % fn)
                return
        else:
            plot_model_normaldata = False

        for trial, cycs in plot_cycles.items():
            try:
                self.pl.plot_trial(trial=trial, model_cycles=cycs,
                                   emg_cycles=cycs,
                                   match_pig_kinetics=match_pig_kinetics,
                                   maintitle='', superpose=True,
                                   model_stddev=trial.stddev_data,
                                   plot_model_normaldata=plot_model_normaldata)
            except GaitDataError as e:
                qt_message_dialog('Error: %s' % str(e))
                self.pl.fig.clear()  # fig may have been partially drawn
                return

        self.canvas.draw()
        self.btnSavePDF.setEnabled(True)  # can create pdf now
        # this is a lazy default for sessionpath (pick path from one trial)
        # it is used as the default PDF output dir.
        self._sessionpath = trial.sessionpath

    def load_dialog(self):
        """ Bring up load dialog and load selected c3d file. """
        fnames = QtWidgets.QFileDialog.getOpenFileNames(self, 'Open C3D files',
                                                        '*.c3d')[0]
        if fnames:
            for fname in fnames:
                self._open_trial(fname)

    def _write_pdf(self):
        """ Bring up save dialog and save data. """
        fname = QtWidgets.QFileDialog.getSaveFileName(self,
                                                      'Save PDF',
                                                      self._sessionpath,
                                                      '*.pdf')[0]
        if fname:
            # TODO: need to figure out logic for the title
            self.pl.set_title('Just a test')
            old_size = self.pl.fig.get_size_inches()
            self.pl.fig.set_size_inches([8.27, 11.69])
            try:
                self.canvas.print_figure(fname)
            except IOError:
                qt_message_dialog('Error writing PDF file, check that file '
                                  'is not open')
            # reset title for onscreen and redraw canvas
            self.pl.set_title('')
            self.pl.fig.set_size_inches(old_size)  # needed?
            self.canvas.draw()


def main():

    logging.basicConfig(level=logging.DEBUG)
    # uiparser logger makes too much noise
    logging.getLogger('PyQt5.uic').setLevel(logging.WARNING)

    app = QtWidgets.QApplication(sys.argv)
    win = PlotterWindow()

    def my_excepthook(type_, value, tback):
        """ Custom exception handler for fatal (unhandled) exceptions:
        report to user via GUI and terminate. """
        tb_full = u''.join(traceback.format_exception(type_, value, tback))
        qt_message_dialog('Unhandled exception: %s' % tb_full)
        # dump traceback to file
        # try:
        #    with io.open(Config.traceback_file, 'w', encoding='utf-8') as f:
        #        f.write(tb_full)
        # here is a danger of infinitely looping the exception hook,
        # so try to catch any exceptions...
        # except Exception:
        #    print('Cannot dump traceback!')
        sys.__excepthook__(type_, value, tback)
        app.quit()

    sys.excepthook = my_excepthook

    win.show()
    sys.exit(app.exec_())
