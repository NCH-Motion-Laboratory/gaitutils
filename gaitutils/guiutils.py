# -*- coding: utf-8 -*-
"""
Created on Tue Jan 26 15:31:11 2016

Misc functions for Gaitplotter (OS dialogs etc)

@author: Jussi (jnu@iki.fi)
"""

from PyQt5 import QtWidgets
import ctypes
import sys


# FIXME: this should go into common GUI module
def qt_message_dialog(msg):
    """ Show message with an 'OK' button. """
    dlg = QtWidgets.QMessageBox()
    dlg.setWindowTitle('Message')
    dlg.setText(msg)
    dlg.addButton(QtWidgets.QPushButton('Ok'),
                  QtWidgets.QMessageBox.YesRole)
    dlg.exec_()


def qt_yesno_dialog(msg):
    """ Show message with 'Yes' and 'No buttons, return role accordingly """
    dlg = QtWidgets.QMessageBox()
    dlg.setWindowTitle('Confirm')
    dlg.setText(msg)
    dlg.addButton(QtWidgets.QPushButton('Yes'),
                  QtWidgets.QMessageBox.YesRole)
    dlg.addButton(QtWidgets.QPushButton('No'),
                  QtWidgets.QMessageBox.NoRole)
    dlg.exec_()
    return dlg.buttonRole(dlg.clickedButton())


def error_exit(message):
    """ Custom error handler """
    # graphical error dialog - Windows specific
    # casts to str are needed, since MessageBoxA does not like Unicode
    ctypes.windll.user32.MessageBoxA(0, str(message),
                                     "Error in Nexus Python script", 0)
    sys.exit()


def messagebox(message, title=None):
    """ Custom notification handler """
    if title is None:
        title = "Message from Nexus Python script"
    ctypes.windll.user32.MessageBoxA(0, str(message), title, 0)


def yesno_box(message):
    """ Yes/no dialog with message """
    return ctypes.windll.user32.MessageBoxA(0,
                                            str(message), "Question", 1) == 1
