# -*- coding: utf-8 -*-
"""
Created on Tue Feb 07 10:05:28 2017

@author: HUS20664877
"""

from PyQt4 import QtGui, QtCore, uic
import sys
import nexus_emgplot
import nexus_kinetics_emgplot
import nexus_emg_consistency
import nexus_kin_consistency
import nexus_autoprocess_current
import nexus_autoprocess_trials



class Gaitmenu(QtGui.QMainWindow):

    def __init__(self):
        super(self.__class__, self).__init__()
        # load user interface made with designer
        uifile = 'gaitmenu.ui'
        uic.loadUi(uifile, self)

        self.btnEMG.clicked.connect(nexus_emgplot.do_plot)
        self.btnKinEMG.clicked.connect(nexus_kinetics_emgplot.do_plot)
        self.btnEMGCons.clicked.connect(nexus_emg_consistency.do_plot)
        self.btnKinCons.clicked.connect(nexus_kin_consistency.do_plot)
        self.btnAutoprocTrial.clicked.connect(nexus_autoprocess_current.
                                              autoproc_single)
        self.btnAutoprocSession.clicked.connect(nexus_autoprocess_trials.
                                                autoproc_session)


def main():

    app = QtGui.QApplication(sys.argv)
    gaitmenu = Gaitmenu()

    gaitmenu.show()
    app.exec_()


if __name__ == '__main__':
    main()
