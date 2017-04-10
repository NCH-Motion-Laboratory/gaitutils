# -*- coding: utf-8 -*-
"""
Created on Tue Feb 07 10:05:28 2017

@author: HUS20664877
"""

from __future__ import print_function
from PyQt5 import QtGui, QtCore, uic, QtWidgets
import sys
import nexus_emgplot
import nexus_kinetics_emgplot
import nexus_emg_consistency
import nexus_kin_consistency
import nexus_autoprocess_current
import nexus_autoprocess_trials
import nexus_kinallplot
import sys
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
        uifile = 'gaitmenu.ui'
        uic.loadUi(uifile, self)

        self.btnEMG.clicked.connect(nexus_emgplot.do_plot)
        self.btnKinEMG.clicked.connect(nexus_kinetics_emgplot.do_plot)
        self.btnKinall.clicked.connect(nexus_kinallplot.do_plot)
        self.btnEMGCons.clicked.connect(nexus_emg_consistency.do_plot)
        self.btnKinCons.clicked.connect(nexus_kin_consistency.do_plot)
        self.btnAutoprocTrial.clicked.connect(nexus_autoprocess_current.
                                              autoproc_single)
        self.btnAutoprocSession.clicked.connect(nexus_autoprocess_trials.
                                                autoproc_session)
        XStream.stdout().messageWritten.connect(self.txtOutput.insertPlainText)
        XStream.stderr().messageWritten.connect(self.txtOutput.insertPlainText)


def main():

    app = QtWidgets.QApplication(sys.argv)

    logger = logging.getLogger()
    handler = QtHandler()
    handler.setFormatter(logging.Formatter("%(name)s: %(levelname)s: %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)

    gaitmenu = Gaitmenu()

    gaitmenu.show()
    logger.debug('starting')
    app.exec_()


if __name__ == '__main__':
    main()
