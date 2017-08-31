# -*- coding: utf-8 -*-
"""
Created on Tue Feb 07 10:05:28 2017

@author: HUS20664877
"""

from __future__ import print_function
from PyQt5 import QtGui, QtCore, uic, QtWidgets
from PyQt5.QtCore import QRunnable, QThreadPool, pyqtSignal, QObject
from pkg_resources import resource_filename
import sys
from gaitutils import nexus
from gaitutils import cfg
import nexus_emgplot
import nexus_kinetics_emgplot
import nexus_emg_consistency
import nexus_kin_consistency
import nexus_autoprocess_current
import nexus_autoprocess_trials
import nexus_kinallplot
import nexus_tardieu
import nexus_trials_velocity

try:
    from nexus_scripts import nexus_customplot
    have_custom = True
except ImportError:
    have_custom = False
import logging


class QtHandler(logging.Handler):

    def __init__(self):
        logging.Handler.__init__(self)

    def emit(self, record):
        record = self.format(record)
        if record:
            XStream.stdout().write('%s\n' % record)


class XStream(QtCore.QObject):
    _stdout = None
    _stderr = None
    messageWritten = QtCore.pyqtSignal(str)

    def flush(self):
        pass

    def fileno(self):
        return -1

    def write(self, msg):
        if not self.signalsBlocked():
            self.messageWritten.emit(unicode(msg))

    @staticmethod
    def stdout():
        if not XStream._stdout:
            XStream._stdout = XStream()
            sys.stdout = XStream._stdout  # also capture stdout
        return XStream._stdout

    @staticmethod
    def stderr():
        if not XStream._stderr:
            XStream._stderr = XStream()
            sys.stderr = XStream._stderr  # ... and stderr
        return XStream._stderr


class AutoprocDialog(QtWidgets.QDialog):

    def __init__(self):
        super(self.__class__, self).__init__()
        # load user interface made with designer
        uifile = resource_filename(__name__, 'autoproc_dialog.ui')
        uic.loadUi(uifile, self)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)
        """ Collect config widgets into a dict """
        self.cfg_widgets = dict()
        for page in [self.tabWidget.widget(n) for n in
                     range(self.tabWidget.count())]:
            pname = page.objectName()
            self.cfg_widgets[pname] = dict()
            for w in page.findChildren(QtWidgets.QWidget):
                wname = unicode(w.objectName())
                if wname[:4] == 'cfg_':  # config widgets are specially named
                    self.cfg_widgets[pname][wname] = w
        self.update_widgets()

    def update_widgets(self):
        """ Update config widgets according to current cfg """
        for section in self.cfg_widgets.keys():
            for wname, widget in self.cfg_widgets[section].items():
                item = wname[4:]
                cfgval = getattr(getattr(cfg, section), item)
                if str(cfgval) != str(self.getval(widget)):
                    self.setval(widget, cfgval)  # set using native type

    def getval(self, widget):
        """ Universal value getter that takes any type of config widget.
        Returns native types. """
        if isinstance(widget, QtWidgets.QSpinBox) or isinstance(widget, QtWidgets.QDoubleSpinBox):
            return widget.value()
        elif isinstance(widget, QtWidgets.QCheckBox):
            return bool(widget.checkState())
        elif isinstance(widget, QtWidgets.QComboBox):
            return unicode(widget.currentText())
        elif isinstance(widget, QtWidgets.QLineEdit):
            return unicode(widget.text())
        else:
            raise Exception('Unhandled type of config widget')

    def setval(self, widget, val):
        """ Universal value setter that takes any type of config widget.
        val is a native type. """
        print('%s -> %s of %s' % (widget, val, type(val)))
        if isinstance(widget, QtWidgets.QSpinBox) or isinstance(widget, QtWidgets.QDoubleSpinBox):
            widget.setValue(val)
        elif isinstance(widget, QtWidgets.QCheckBox):
            widget.setCheckState(2 if val else 0)
        elif isinstance(widget, QtWidgets.QComboBox):
            idx = widget.findText(val)
            if idx >= 0:
                widget.setCurrentIndex(idx)
            else:
                raise ValueError('Tried to set combobox to invalid value.')
        elif isinstance(widget, QtWidgets.QLineEdit):
            widget.setText(str(val))
        else:
            raise Exception('Unhandled type of config widget')

    def update_cfg(self):
        """ Update cfg according to current dialog settings """
        global cfg
        for section in self.cfg_widgets.keys():
            for wname, widget in self.cfg_widgets[section].items():
                item = wname[4:]
                widgetval = str(self.getval(widget))
                cfgval = str(getattr(getattr(cfg, section), item))  # FIXME
                if widgetval != cfgval:
                    print('changing %s:%s = %s (was %s))' % (section, wname,
                                                            widgetval, cfgval))
                    cfg[section][item] = widgetval


class Gaitmenu(QtWidgets.QMainWindow):

    def __init__(self):
        super(self.__class__, self).__init__()
        # load user interface made with designer
        uifile = resource_filename(__name__, 'nexus_menu.ui')
        uic.loadUi(uifile, self)
        """ Stuff that shows matplotlib plots cannot be run in directly in
        worker threads. To put plotting stuff into a worker thread, need to:
        -make the plotting function return a figure (and not invoke the qt
        event loop)
        -put the plotting function into a worker thread
        -call plotting function
        -create a qt dialog and canvas in GUI thread
        -draw resulting figure onto canvas
        So far this has not been done since the plotting functions return
        rather quickly.
        Running the plotting functions directly from the GUI thread is also a
        bit ugly since the Qt event loop gets called twice, but this does not
        seem to do any harm.
        _execute runs the given function and handles exceptions. Passing
        thread=True runs it in a separate worker thread, enabling GUI updates
        (e.g. logging dialog) which can be nice.
        """
        
        self._button_connect_task(self.btnEMG, nexus_emgplot.do_plot)
        self._button_connect_task(self.btnKinEMG,
                                  nexus_kinetics_emgplot.do_plot)
        self._button_connect_task(self.btnKinall, nexus_kinallplot.do_plot)
        self._button_connect_task(self.btnTardieu, self._tardieu)
        if have_custom:
            self._button_connect_task(self.btnCustom, nexus_customplot.do_plot)
        else:
            self.btnCustom.clicked.connect(self._no_custom)
        self._button_connect_task(self.btnTrialVelocity,
                                  nexus_trials_velocity.do_plot)
        self._button_connect_task(self.btnEMGCons,
                                  nexus_emg_consistency.do_plot)
        self._button_connect_task(self.btnKinCons,
                                  nexus_kin_consistency.do_plot)
        self._button_connect_task(self.btnAutoprocTrial,
                                  nexus_autoprocess_current.autoproc_single,
                                  thread=True)
        self._button_connect_task(self.btnAutoprocSession,
                                  nexus_autoprocess_trials.autoproc_session,
                                  thread=True)
        self.btnAutoprocDialog.clicked.connect(self.autoproc_dialog)
        self.btnQuit.clicked.connect(self.close)

        # collect operation widgets
        self.opWidgets = list()
        for widget in self.__dict__:
            if ((widget[:3] == 'btn' or widget[:4] == 'rbtn') and
               widget != 'btnQuit'):
                self.opWidgets.append(widget)

        XStream.stdout().messageWritten.connect(self._log_message)
        XStream.stderr().messageWritten.connect(self._log_message)

        self.threadpool = QThreadPool()
        logging.debug('started threadpool with max %d threads' %
                      self.threadpool.maxThreadCount())

    def _button_connect_task(self, button, fun, thread=False):
        """ Helper to connect button with task function. Use lambda to consume
        unused events argument. If thread=True, launch in a separate worker
        thread. """
        button.clicked.connect(lambda ev: self._execute(fun, thread=thread))

    def message_dialog(self, msg):
        """ Show message with an 'OK' button. """
        dlg = QtWidgets.QMessageBox()
        dlg.setWindowTitle('Message')
        dlg.setText(msg)
        dlg.addButton(QtWidgets.QPushButton('Ok'),
                      QtWidgets.QMessageBox.YesRole)
        dlg.exec_()

    def autoproc_dialog(self):
        """ Show the autoprocessing options dialog """
        dlg = AutoprocDialog()
        ret = dlg.exec_()
        if ret:
            dlg.update_cfg()

    def _log_message(self, msg):
        c = self.txtOutput.textCursor()
        c.movePosition(QtGui.QTextCursor.End)
        self.txtOutput.setTextCursor(c)
        self.txtOutput.insertPlainText(msg)
        self.txtOutput.ensureCursorVisible()

    def _no_custom(self):
        self.message_dialog('No custom plot defined. Please create '
                            'nexus_scripts/nexus_customplot.py')

    def _exception(self, e):
        logging.debug('caught exception while running task')
        self.message_dialog('%s' % str(e))

    def _disable_op_buttons(self):
        """ Disable all operation buttons """
        for widget in self.opWidgets:
                self.__dict__[widget].setEnabled(False)

    def _enable_op_buttons(self):
        """ Disable all operation buttons """
        for widget in self.opWidgets:
                self.__dict__[widget].setEnabled(True)

    def _tardieu(self):
        if self.rbtnR.isChecked():
            nexus_tardieu.do_plot('R')
        else:
            nexus_tardieu.do_plot('L')

    def _finished(self):
        self._enable_op_buttons()

    def _execute(self, fun, thread=False):
        """ Run some function. If thread==True, run in a separate worker
        thread. """
        self._disable_op_buttons()
        if thread:
            self._run_in_worker_thread(fun)
        else:
            try:
                fun()
            except Exception as e:
                self._exception(e)
            finally:
                self._enable_op_buttons()

    def _run_in_worker_thread(self, fun):
        """ Run function in a separate thread """
        self.runner = Runner(fun)
        self.runner.signals.finished.connect(self._finished)
        self.runner.signals.error.connect(lambda e: self._exception(e))
        self.threadpool.start(self.runner)


class RunnerSignals(QObject):
    """ Need a separate class since QRunnable cannot emit signals """

    finished = pyqtSignal()
    error = pyqtSignal(Exception)


class Runner(QRunnable):

    def __init__(self, fun):
        super(Runner, self).__init__()
        self.fun = fun
        self.signals = RunnerSignals()

    def run(self):
        try:
            self.fun()
        except Exception as e:
            self.signals.error.emit(e)
        finally:
            self.signals.finished.emit()


def main():

    app = QtWidgets.QApplication(sys.argv)

    logger = logging.getLogger()
    handler = QtHandler()
    # handler = logging.StreamHandler()   # to sys.stdout

    handler.setFormatter(logging.
                         Formatter("%(name)s: %(levelname)s: %(message)s"))
    handler.setFormatter(logging.Formatter("%(name)s: %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)

    gaitmenu = Gaitmenu()
    gaitmenu.show()

    nexus_status = 'Vicon Nexus is %srunning' % ('' if nexus.pid() else 'not ')
    logger.debug(nexus_status)
    app.exec_()


if __name__ == '__main__':
    main()
