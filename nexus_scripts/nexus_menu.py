# -*- coding: utf-8 -*-
"""
Created on Tue Feb 07 10:05:28 2017

@author: HUS20664877
"""

from __future__ import print_function
from PyQt5 import QtGui, QtCore, uic, QtWidgets
from PyQt5.QtCore import QRunnable, QThreadPool
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
        self.btnEMG.clicked.connect(lambda ev: nexus_emgplot.do_plot())
        self.btnKinEMG.clicked.connect(lambda ev: nexus_kinetics_emgplot.do_plot())
        self.btnKinall.clicked.connect(lambda ev: nexus_kinallplot.do_plot())
        self.btnTardieu.clicked.connect(lambda ev: self._tardieu())
        if have_custom:
            self.btnCustom.clicked.connect(lambda ev: nexus_customplot.do_plot())
        else:
            self.btnCustom.clicked.connect(self._no_custom)
        self.btnTrialVelocity.clicked.connect(lambda ev: nexus_trials_velocity.do_plot())
        self.btnEMGCons.clicked.connect(lambda ev: nexus_emg_consistency.do_plot())
        self.btnKinCons.clicked.connect(lambda ev: self.run_in_worker_thread(nexus_kin_consistency.do_plot))
        self.btnAutoprocTrial.clicked.connect(lambda ev: nexus_autoprocess_current.
                                              autoproc_single())
        self.btnAutoprocSession.clicked.connect(lambda ev: self.run_in_worker_thread(nexus_autoprocess_trials.autoproc_session))
        
        self.btnQuit.clicked.connect(self.close)
        XStream.stdout().messageWritten.connect(self.txtOutput.insertPlainText)
        XStream.stderr().messageWritten.connect(self.txtOutput.insertPlainText)
        
        self.threadpool = QThreadPool()
        

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
        
    def _tardieu(self):
        if self.rbtnR.isChecked():
            nexus_tardieu.do_plot('R')
        else:
            nexus_tardieu.do_plot('L')


    def run_in_worker_thread(self, fun):
        runner = Runner()
        runner.fun = fun
        self.threadpool.start(runner)
    

class Runner(QRunnable):
    

    def run(self):
        self.fun()
        
        
    
            


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

    def my_excepthook(type, value, tback):
        """ Custom exception handler for fatal (unhandled) exceptions:
        report to user via GUI and terminate. """
        tb_full = u''.join(traceback.format_exception(type, value, tback))
        gaitmenu.message_dialog('%s' % value)
        sys.__excepthook__(type, value, tback)
        #app.quit()

    sys.excepthook = my_excepthook

    gaitmenu.show()
    nexus_status = 'Vicon Nexus is %srunning' % ('' if nexus.pid() else 'not ')
    logger.debug(nexus_status)
    app.exec_()


if __name__ == '__main__':
    main()
