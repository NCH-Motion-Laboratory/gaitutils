# -*- coding: utf-8 -*-
"""
Created on Tue Jan 26 15:31:11 2016

gaitutils common GUI functionality

@author: Jussi (jnu@iki.fi)
"""

from PyQt5 import QtWidgets, QtCore
import ctypes
import sys


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


def qt_dir_chooser():
    """Selector dialog to select dir (or multiple dirs)."""
    # native dialog - single dir only
    return [QtWidgets.QFileDialog.getExistingDirectory(None, 'Select session')]
    # non-native dialog - multiple dirs. a bit messy, currently not in use
    file_dialog = QtWidgets.QFileDialog()
    file_dialog.setFileMode(QtWidgets.QFileDialog.DirectoryOnly)
    file_dialog.setOption(QtWidgets.QFileDialog.DontUseNativeDialog,
                          True)
    file_view = file_dialog.findChild(QtWidgets.QListView, 'listView')
    if file_view:
        file_view.setSelectionMode(QtWidgets.QAbstractItemView.
                                   MultiSelection)
    f_tree_view = file_dialog.findChild(QtWidgets.QTreeView)
    if f_tree_view:
        f_tree_view.setSelectionMode(QtWidgets.QAbstractItemView.
                                     MultiSelection)
    return file_dialog.selectedFiles() if file_dialog.exec_() else []


# non-qt dialogs - Windows specific
def error_exit(message):
    """ Custom error handler """
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
