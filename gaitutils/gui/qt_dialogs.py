# -*- coding: utf-8 -*-
"""
Created on Fri Mar  1 11:11:33 2019

@author: hus20664877
"""

from PyQt5 import QtCore, uic, QtWidgets
from pkg_resources import resource_filename
import os.path as op
import ast

from .. import nexus, GaitDataError, cfg


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


class OptionsDialog(QtWidgets.QDialog):
    """ Display a tabbed dialog for changing gaitutils options """

    def __init__(self, parent, default_tab=0):
        super(self.__class__, self).__init__(parent)
        # load user interface made with designer
        uifile = resource_filename('gaitutils', 'gui/options_dialog.ui')
        uic.loadUi(uifile, self)
        #self.setAttribute(QtCore.Qt.WA_DeleteOnClose)

        # add some buttons to the standard button box
        loadButton = QtWidgets.QPushButton('Load...')
        self.buttonBox.addButton(loadButton,
                                 QtWidgets.QDialogButtonBox.ActionRole)
        loadButton.clicked.connect(self.load_config_dialog)
        saveButton = QtWidgets.QPushButton('Save...')
        self.buttonBox.addButton(saveButton,
                                 QtWidgets.QDialogButtonBox.ActionRole)
        saveButton.clicked.connect(self.save_config_dialog)

        # show page
        self.tabWidget.setCurrentIndex(default_tab)

        """ Collect config widgets into a dict of dict. First key is tab
        (same as config category, e.g. autoproc), second key is widget name """
        self.cfg_widgets = dict()
        for page in [self.tabWidget.widget(n) for n in
                     range(self.tabWidget.count())]:
            pname = page.objectName()
            self.cfg_widgets[pname] = dict()
            for w in page.findChildren(QtWidgets.QWidget):
                wname = w.objectName()
                if wname[:4] == 'cfg_':  # config widgets are specially named
                    self.cfg_widgets[pname][wname] = w
        self._update_widgets()
        self.homedir = op.expanduser('~')

    def load_config_dialog(self):
        """ Bring up load dialog and load selected file. """
        global cfg
        fout = QtWidgets.QFileDialog.getOpenFileName(self,
                                                     'Load config file',
                                                     self.homedir,
                                                     'Config files (*.cfg)')
        # TODO : filedialog set filter -> PyQt5.QtCore.QDir.Hidden?
        fname = fout[0]
        if fname:
            # TODO: check for errors on config read
            # cfg.load_default()  TODO: load defaults before loading cfg file?
            cfg.read(fname)
            self._update_widgets()

    def save_config_dialog(self):
        """ Bring up save dialog and save data. """
        global cfg
        res, txt = self._check_widget_inputs()
        if not res:
            qt_message_dialog('Invalid input: %s\nPlease fix before saving'
                              % txt)
        else:
            fout = QtWidgets.QFileDialog.getSaveFileName(self,
                                                         'Save config file',
                                                         self.homedir,
                                                         'Config files '
                                                         '(*.cfg)')
            fname = fout[0]
            if fname:
                self.update_cfg()
                cfg.write_file(fname)

    def _update_widgets(self):
        """ Update config widgets according to current cfg """
        for section in self.cfg_widgets:
            for wname, widget in self.cfg_widgets[section].items():
                item = wname[4:]
                cfgval = getattr(getattr(cfg, section), item)
                if str(cfgval) != str(self._getval(widget)):
                    self._setval(widget, cfgval)  # set using native type
                if isinstance(widget, QtWidgets.QLineEdit):
                    widget.setCursorPosition(0)  # show beginning of line

    def _check_widget_inputs(self):
        """ Check widget inputs. Currently only QLineEdits are checked for
        eval - ability """
        for section in self.cfg_widgets:
            for widget in self.cfg_widgets[section].values():
                if isinstance(widget, QtWidgets.QLineEdit):
                    txt = widget.text()
                    try:
                        ast.literal_eval(txt)
                    except (SyntaxError, ValueError):
                        return (False, txt)
        return (True, '')

    def _getval(self, widget):
        """ Universal value getter that takes any type of config widget.
        Returns native types, except QLineEdit input is auto-evaluated """
        if (isinstance(widget, QtWidgets.QSpinBox) or
           isinstance(widget, QtWidgets.QDoubleSpinBox)):
            return widget.value()
        elif isinstance(widget, QtWidgets.QCheckBox):
            return bool(widget.checkState())
        elif isinstance(widget, QtWidgets.QComboBox):
            # convert to str to avoid writing out unicode repr() into config
            # files unnecessarily
            return str(widget.currentText())
        elif isinstance(widget, QtWidgets.QLineEdit):
            # Directly eval lineEdit contents. This means that string vars
            # must be quoted in the lineEdit.
            txt = widget.text()
            return ast.literal_eval(txt) if txt else None
        else:
            raise Exception('Unhandled type of config widget')

    def _setval(self, widget, val):
        """ Universal value setter that takes any type of config widget.
        val must match widget type, except for QLineEdit that can take
        any type, which will be converted to its repr """
        if (isinstance(widget, QtWidgets.QSpinBox) or
           isinstance(widget, QtWidgets.QDoubleSpinBox)):
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
            widget.setText(repr(val))
        else:
            raise Exception('Unhandled type of config widget')

    def update_cfg(self):
        """ Update cfg according to current dialog settings """
        global cfg
        for section in self.cfg_widgets.keys():
            for wname, widget in self.cfg_widgets[section].items():
                item = wname[4:]
                widgetval = self._getval(widget)
                cfgval = getattr(getattr(cfg, section), item)
                if widgetval != cfgval:
                    cfg[section][item] = repr(widgetval)

    def accept(self):
        """ Update config and close dialog, if widget inputs are ok. Otherwise
        show an error dialog """
        res, txt = self._check_widget_inputs()
        if res:
            self.update_cfg()
            self.done(QtWidgets.QDialog.Accepted)  # or call superclass accept
        else:
            qt_message_dialog("Invalid input: %s" % txt)


class ChooseSessionsDialog(QtWidgets.QDialog):
    """Display a dialog for picking sessions"""

    def __init__(self, min_sessions=1, max_sessions=3):
        super(self.__class__, self).__init__()
        # load user interface made with designer
        uifile = resource_filename('gaitutils', 'gui/web_report_sessions.ui')
        uic.loadUi(uifile, self)
        #self.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        self.btnBrowseSession.clicked.connect(self.add_session)
        self.btnAddNexusSession.clicked.connect(lambda: self.
                                                add_session(from_nexus=True))
        self.btnClearAll.clicked.connect(self.listSessions.clear)
        self.btnClearCurrent.clicked.connect(self.listSessions.rm_current_item)
        self.max_sessions = max_sessions
        self.min_sessions = min_sessions

    def add_session(self, from_nexus=False):
        if len(self.sessions) == self.max_sessions:
            qt_message_dialog('You can specify maximum of %d sessions' %
                              self.max_sessions)
            return
        if from_nexus:
            try:
                dirs = [nexus.get_sessionpath()]
            except GaitDataError as e:
                qt_message_dialog(_exception_msg(e))
                return
        else:
            dirs = qt_dir_chooser()
        if dirs:
            for dir_ in dirs:
                if dir_ in self.sessions:
                    qt_message_dialog('Session %s already loaded' % dir_)
                elif dir_:
                    self.listSessions.add_item(dir_, data=dir_)

    @property
    def sessions(self):
        return [item.userdata for item in self.listSessions.items]

    def accept(self):
        if len(self.sessions) < self.min_sessions:
            qt_message_dialog('Please select at least %d session%s' %
                              (self.min_sessions,
                               's' if self.min_sessions > 1 else ''))
        else:
            self.done(QtWidgets.QDialog.Accepted)

