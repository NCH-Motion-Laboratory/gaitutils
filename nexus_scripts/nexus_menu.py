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
import nexus_emgplot
import nexus_kinetics_emgplot
import nexus_emg_consistency
import nexus_kin_consistency
import nexus_autoprocess_current
import nexus_autoprocess_trials
import nexus_kinallplot
import nexus_tardieu
import nexus_copy_trial_videos
import nexus_trials_velocity

try:
    from nexus_scripts import nexus_customplot
    have_custom = True
except ImportError:
    have_custom = False
import sys
import logging
import traceback

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
            sys.stdout = XStream._stdout
        return XStream._stdout

    @staticmethod
    def stderr():
        if not XStream._stderr:
            XStream._stderr = XStream()
            sys.stderr = XStream._stderr
        return XStream._stderr


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
        bit ugly since the mpl event loop gets called twice, but this does not
        seem to do any harm.
        _execute runs the given function and handles exceptions. Passing
        thread=True runs it in a separate worker thread, enabling GUI updates
        (e.g. logging dialog) which can be nice.
        """
        self.btnEMG.clicked.connect(lambda ev: self._execute(nexus_emgplot.do_plot))
        self.btnKinEMG.clicked.connect(lambda ev: self._execute(nexus_kinetics_emgplot.do_plot))
        self.btnKinall.clicked.connect(lambda ev: self._execute(nexus_kinallplot.do_plot))
        self.btnTardieu.clicked.connect(lambda ev: self._execute(self._tardieu))
        if have_custom:
            self.btnCustom.clicked.connect(lambda ev: self._execute(nexus_customplot.do_plot))
        else:
            self.btnCustom.clicked.connect(self._no_custom)
        self.btnCopyVideos.clicked.connect(lambda ev: self._execute(nexus_copy_trial_videos.do_copy, thread=True))
        self.btnTrialVelocity.clicked.connect(lambda ev: self._execute(nexus_trials_velocity.do_plot))
        self.btnEMGCons.clicked.connect(lambda ev: self._execute(nexus_emg_consistency.do_plot))
        self.btnKinCons.clicked.connect(lambda ev: self._execute(nexus_kin_consistency.do_plot))
        self.btnAutoprocTrial.clicked.connect(lambda ev: self._execute(nexus_autoprocess_current.autoproc_single, thread=True))
        self.btnAutoprocSession.clicked.connect(lambda ev: self._execute(nexus_autoprocess_trials.autoproc_session, thread=True))
        self.btnQuit.clicked.connect(self.close)

        # collect operation widgets
        self.opWidgets = list()
        for widget in self.__dict__:
            if (widget[:3] == 'btn' or widget[:4] == 'rbtn') and widget != 'btnQuit':
                self.opWidgets.append(widget)
        
        XStream.stdout().messageWritten.connect(self.txtOutput.insertPlainText)
        XStream.stderr().messageWritten.connect(self.txtOutput.insertPlainText)
        
        self.threadpool = QThreadPool()
        logging.debug('started threadpool with max %d threads' %
                      self.threadpool.maxThreadCount())
        

    def message_dialog(self, msg):
        """ Show message with an 'OK' button. """
        dlg = QtWidgets.QMessageBox()
        dlg.setWindowTitle('Message')
        dlg.setText(msg)
        dlg.addButton(QtWidgets.QPushButton('Ok'),
                      QtWidgets.QMessageBox.YesRole)
        dlg.exec_()

    def _no_custom(self):
        self.message_dialog('No custom plot defined. Please create '
                            'nexus_scripts/nexus_customplot.py')

    def _exception(self, e):
        logging.debug('Caught exception while running task')
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
