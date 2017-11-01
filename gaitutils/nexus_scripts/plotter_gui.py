# -*- coding: utf-8 -*-
"""
Embed gaitplotter figure canvas into PyQt5 GUI
WIP


@author: Jussi (jnu@iki.fi)
"""

import logging
import sys
import traceback
from pkg_resources import resource_filename
from PyQt5 import QtGui, QtWidgets, uic, QtCore
from matplotlib.backends.backend_qt5agg import (FigureCanvasQTAgg as
                                                FigureCanvas)
from matplotlib.backends.backend_qt5agg import (NavigationToolbar2QT as
                                                NavigationToolbar)

from gaitutils import (Plotter, Trial, nexus, layouts, cfg, GaitDataError,
                       stats, models)


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
    def userdata(self):
        return super(NiceListWidgetItem, self).data(QtCore.Qt.UserRole)

    @userdata.setter
    def userdata(self, _data):
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
        """ Add checkable item with data. Select new item. """
        item = NiceListWidgetItem(txt, self, checkable=checkable)
        item.userdata = data
        if checkable:
            item.checkstate = checked
        self.setCurrentItem(item)

    def rm_current_item(self):
        self.takeItem(self.row(self.currentItem()))


class Dialog(QtWidgets.QDialog):

    def __init__(self, parent=None):
        super(Dialog, self).__init__(parent)
        uifile = 'dialog.ui'
        uic.loadUi(uifile, self)


class PlotterWindow(QtWidgets.QMainWindow):

    def __init__(self, parent=None):
        super(PlotterWindow, self).__init__(parent)

        uifile = resource_filename(__name__, 'plotter_gui.ui')
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
        # self.listTrials.setSelectionMode(QtWidgets.QAbstractItemView.MultiSelection)
        self.listTrials.itemClicked.connect(self._trial_selected)
        # set up widgets
        # buttons
        self.btnAddNexusTrial.clicked.connect(self._open_nexus_trial)
        self.btnPlot.clicked.connect(self._plot_trials)
        self.btnSelectAllCycles.clicked.connect(self.listTrialCycles.check_all)
        self.btnSelectForceplateCycles.clicked.connect(self.
                                                       _select_forceplate_cycles)
        self.btnSelect1stCycles.clicked.connect(self._select_1st_cycles)
        self.btnPickCycles.clicked.connect(self._pick_cycles)
        self.btnAverageSelected.clicked.connect(self._average_selected)
        self.btnAddC3DTrial.clicked.connect(self.load_dialog)
        self.btnSavePDF.clicked.connect(self._write_pdf)
        self.btnClearTrials.clicked.connect(self._clear_trials)
        self.btnClearCyclesToPlot.clicked.connect(self.listCyclesToPlot.clear)
        # menu actions
        self.actionQuit.triggered.connect(self.close)
        self.actionNormal_data.triggered.connect(self._dialog)
        # add predefined plot layouts to combobox
        self.cbLayout.addItems(sorted(cfg.options('layouts')))

        self._set_status('Ready')

    def _dialog(self):
        d = Dialog()
        d.exec_()

    def _load_normaldata(self):
        fname = QtWidgets.QFileDialog.getOpenFileName(self,
                                                      'Open normal data', '',
                                                      'XLSX files (*.xlsx);;'
                                                      'GCD files (*.gcd);; ')
        fname = fname[0]
        if fname:
            # store the filename as user data - could just use the name
            self.listNormalData.add_item(fname, data=fname)

    def _rm_normaldata(self):
        if self.listNormalData.currentItem():
            self.listNormalData.rm_current_item()

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

    def _average_selected(self):
        """ Make AvgTrial from selected trials """
        # only add cycles that were not already added
        trials = [item.userdata for item in self.listTrials.checked_items]
        avgtr = stats.AvgTrial(trials, models.models_all)
        self.listTrials.add_item('Average trial', data=avgtr)
        self._update_trial_cycles_list(avgtr)

    def _open_nexus_trial(self):
        try:
            vicon = nexus.viconnexus()
            self._open_trial(vicon)
        except GaitDataError:
            self.message_dialog('Vicon Nexus is not running')


    def _open_trial(self, source):
        tr = Trial(source)
        trials = (item.userdata for item in self.listTrials.items)
        # check if trial already loaded (based on name)
        # TODO: might use smarter detection
        if tr.trialname in [trial.trialname for trial in trials]:
            return
        self.listTrials.add_item(tr.trialname, data=tr, checkable=True)
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
            self.message_dialog('No cycles selected for plotting')
            return
        # gather the cycles and key by trial
        for cycle in cycles:
            if cycle.trial not in plot_cycles:
                plot_cycles[cycle.trial] = []
            plot_cycles[cycle.trial].append(cycle)
        # set options and create the plot
        self.pl.layout = cfg.layouts.__getattr__(self.cbLayout.currentText())
        match_pig_kinetics = self.xbKineticsFpOnly.checkState()
#        normaldata_files = [item.userdata for item in
#                            self.listNormalData.items]
        for trial, cycs in plot_cycles.items():
            try:
                self.pl.plot_trial(trial=trial, model_cycles=cycs,
                                   emg_cycles=cycs,
                                   match_pig_kinetics=match_pig_kinetics,
                                   maintitle='', superpose=True)
            except GaitDataError as e:
                self.message_dialog('Error: %s' % str(e))
                self.pl.fig.clear()  # fig may have been partially drawn
        self.canvas.draw()
        self.btnSavePDF.setEnabled(True)  # can create pdf now
        # this is a lazy default for sessionpath (pick path from one trial)
        # it is used as the default PDF output dir.
        self._sessionpath = trial.sessionpath

    def load_dialog(self):
        """ Bring up load dialog and load selected c3d file. """
        fnames = QtWidgets.QFileDialog.getOpenFileNames(self, 'Open C3D file',
                                                        '*.c3d')[0]
        if fnames:
            for fname in fnames:
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
                self.message_dialog('Error writing PDF file, check that file '
                                    'is not open')
            # reset title for onscreen and redraw canvas
            self.pl.set_title('')
            self.pl.fig.set_size_inches(old_size)  # needed?
            self.canvas.draw()


if __name__ == '__main__':

    logging.basicConfig(level=logging.DEBUG)

    app = QtWidgets.QApplication(sys.argv)
    win = PlotterWindow()

    def my_excepthook(type, value, tback):
        """ Custom exception handler for fatal (unhandled) exceptions:
        report to user via GUI and terminate. """
        tb_full = u''.join(traceback.format_exception(type, value, tback))
        win.message_dialog('Unhandled exception: %s' % tb_full)
        # dump traceback to file
        # try:
        #    with io.open(Config.traceback_file, 'w', encoding='utf-8') as f:
        #        f.write(tb_full)
        # here is a danger of infinitely looping the exception hook,
        # so try to catch any exceptions...
        # except Exception:
        #    print('Cannot dump traceback!')
        sys.__excepthook__(type, value, tback)
        app.quit()

    sys.excepthook = my_excepthook

    win.show()
    sys.exit(app.exec_())
