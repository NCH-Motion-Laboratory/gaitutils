# -*- coding: utf-8 -*-
"""
PyQt dialogs etc.

@author: Jussi (jnu@iki.fi)
"""

from PyQt5 import uic, QtWidgets
from PyQt5.QtWidgets import QDialogButtonBox
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from pkg_resources import resource_filename
import os.path as op
import ast
import io
from collections import defaultdict
import logging

from .. import nexus
from ..envutils import GaitDataError
import configdot
from ..config import _handle_cfg_defaults, cfg_user_fn, cfg, cfg_types

logger = logging.getLogger(__name__)


def qt_matplotlib_window(fig):
    """Show matplotlib figure fig in new Qt window. Window is returned"""
    _mpl_win = QtWidgets.QDialog()
    # _mpl_win.setGeometry(100, 100, 1500, 1000)
    _mpl_win._canvas = FigureCanvas(fig)
    _mpl_win._canvas.setSizePolicy(
        QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding
    )
    _mpl_win._canvas.updateGeometry()  # not sure if this does anything
    toolbar = NavigationToolbar(_mpl_win._canvas, _mpl_win)
    layout = QtWidgets.QVBoxLayout()
    layout.addWidget(toolbar)
    layout.addWidget(_mpl_win._canvas)
    layout.setSpacing(0)
    _mpl_win.setLayout(layout)
    _mpl_win._canvas.draw()
    _mpl_win.show()
    return _mpl_win


def qt_message_dialog(msg):
    """Show message with 'OK' button"""
    dlg = QtWidgets.QMessageBox()
    dlg.setWindowTitle('Message')
    dlg.setText(msg)
    dlg.addButton(QtWidgets.QPushButton('Ok'), QtWidgets.QMessageBox.YesRole)
    dlg.exec_()


def qt_yesno_dialog(msg):
    """Show message with Yes and No buttons, return role accordingly"""
    dlg = QtWidgets.QMessageBox()
    dlg.setWindowTitle('Confirm')
    dlg.setText(msg)
    dlg.addButton(QtWidgets.QPushButton('Yes'), QtWidgets.QMessageBox.YesRole)
    dlg.addButton(QtWidgets.QPushButton('No'), QtWidgets.QMessageBox.NoRole)
    dlg.exec_()
    return dlg.buttonRole(dlg.clickedButton())


def qt_dir_chooser():
    """Selector dialog to select dir (or multiple dirs). Always returns a list
    (empty if dialog was canceled)"""
    # native dialog - single dir only
    dir = QtWidgets.QFileDialog.getExistingDirectory(None, 'Select session')
    return [dir] if dir else list()
    # non-native dialog - multiple dirs. a bit messy, currently not in use
    file_dialog = QtWidgets.QFileDialog()
    file_dialog.setFileMode(QtWidgets.QFileDialog.DirectoryOnly)
    file_dialog.setOption(QtWidgets.QFileDialog.DontUseNativeDialog, True)
    file_view = file_dialog.findChild(QtWidgets.QListView, 'listView')
    if file_view:
        file_view.setSelectionMode(QtWidgets.QAbstractItemView.MultiSelection)
    f_tree_view = file_dialog.findChild(QtWidgets.QTreeView)
    if f_tree_view:
        f_tree_view.setSelectionMode(QtWidgets.QAbstractItemView.MultiSelection)
    return file_dialog.selectedFiles() if file_dialog.exec_() else []


class QCompoundEditorDict(QtWidgets.QDialog):
    """Compound editor for dicts"""

    def __init__(self, data, parent=None):
        super(QCompoundEditorDict, self).__init__(parent=parent)
        root_layout = QtWidgets.QVBoxLayout()
        self.datable = QtWidgets.QTableWidget()
        self.data = data
        # create the button box
        self.buttonbox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        insertbutton = QtWidgets.QPushButton('Insert')
        deletebutton = QtWidgets.QPushButton('Delete')
        self.buttonbox.addButton(insertbutton, QDialogButtonBox.ActionRole)
        self.buttonbox.addButton(deletebutton, QDialogButtonBox.ActionRole)
        insertbutton.clicked.connect(self._insert_item)
        deletebutton.clicked.connect(self._delete_item)
        self.buttonbox.accepted.connect(self.accept)
        self.buttonbox.rejected.connect(self.reject)
        self.datable = QtWidgets.QTableWidget()
        self._init_table()
        root_layout.addWidget(self.datable)
        root_layout.addWidget(self.buttonbox)
        self.datable.resizeColumnsToContents()
        self.datable.setSelectionBehavior(QtWidgets.QTableView.SelectRows)
        self.setLayout(root_layout)
        self.setWindowTitle('Edit config item')
        if not data:
            self._insert_item()

    def _init_table(self):
        """Init table for dict data"""
        self.datable.setColumnCount(2)
        self.datable.setHorizontalHeaderLabels(['Key', 'Value'])
        for k, (key, val) in enumerate(self.data.items()):
            key_txt, val_txt = repr(key), repr(val)
            self.datable.insertRow(k)
            self.datable.setItem(k, 0, QtWidgets.QTableWidgetItem(key_txt))
            self.datable.setItem(k, 1, QtWidgets.QTableWidgetItem(val_txt))

    def _insert_item(self):
        """Insert a new dict/list item at current position and start editing it"""
        pos = self.datable.currentRow()
        self.datable.insertRow(pos + 1)
        newitem = QtWidgets.QTableWidgetItem()
        self.datable.setItem(pos + 1, 0, newitem)
        self.datable.editItem(newitem)

    def _delete_item(self):
        """Delete dict/list item at current position"""
        pos = self.datable.currentRow()
        self.datable.removeRow(pos)

    def _collect_column(self, col):
        """Collect data from column col"""
        items = (self.datable.item(row, col) for row in range(self.datable.rowCount()))
        items = (it for it in items if it is not None)
        return (it.text() for it in items)

    def accept(self):
        """Do some sanity checks, close dialog if ok"""
        keys, vals = self._collect_column(0), self._collect_column(1)
        _text_data = {k: v for k, v in zip(keys, vals)}
        # keys and vals are now strings (hopefully) representing valid Python expressions
        # return a dict with the actual evaluated expressions
        _result = dict()
        for row, (key_txt, val_txt) in enumerate(_text_data.items(), 1):
            try:
                key = ast.literal_eval(key_txt)
                _result[key] = ast.literal_eval(val_txt)
            except (SyntaxError, ValueError):
                qt_message_dialog(
                    'Invalid input for item %s: %s on row %d\n'
                    'Inputs must be valid Python expressions (e.g. strings must be quoted).\n'
                    'Please fix before closing or cancel dialog'
                    % (key_txt, val_txt, row)
                )
                return
        self.data = _result
        self.done(QtWidgets.QDialog.Accepted)


class QCompoundEditorList(QCompoundEditorDict):
    """Compound editor for lists"""

    def _init_table(self):
        """Init table for list data"""
        self.datable.setColumnCount(1)
        self.datable.setHorizontalHeaderLabels(['Value'])
        for k, val in enumerate(self.data):
            val_txt = repr(val)
            self.datable.insertRow(k)
            self.datable.setItem(k, 0, QtWidgets.QTableWidgetItem(val_txt))

    def accept(self):
        """Do some sanity checks, close dialog if ok"""
        # list elements are now strings (hopefully) representing valid Python expressions
        # return a list with the actual evaluated expressions
        _text_data = list(self._collect_column(0))
        _result = list()
        for row, item_txt in enumerate(_text_data, 1):
            try:
                item = ast.literal_eval(item_txt)
                _result.append(item)
            except (SyntaxError, ValueError):
                qt_message_dialog(
                    'Invalid input for item %s on row %d.\n'
                    'Inputs must be valid Python expressions (e.g. strings must be quoted).\n'
                    'Please fix before closing or cancel dialog' % (item_txt, row)
                )
                return
        self.data = _result
        self.done(QtWidgets.QDialog.Accepted)


class OptionsDialog(QtWidgets.QDialog):
    """Dialog for changing gaitutils options"""

    def _create_tab(self, section, secname):
        """Create a tab for the tab widget, according to config items"""
        tab = QtWidgets.QWidget()
        lout = QtWidgets.QFormLayout()
        tab.setLayout(lout)
        # get items sorted by comment
        items = sorted(
            (item for (itname, item) in section),
            key=lambda it: configdot.get_description(it),
        )
        # loop through config items and insert appropriate input widget for each
        for item in items:
            _save_widget = True
            desc = configdot.get_description(item)
            if not desc:
                raise RuntimeError('Config item %s missing a description' % item)
            vartype = cfg_types[secname][item.name].value
            raise ValueError(vartype['type'])
            if isinstance(item.value, bool):  # use simple checkbox for boolean items
                input_widget = QtWidgets.QCheckBox()
                input_widget.setChecked(item.value)
            elif isinstance(item.value, list) or isinstance(item.value, dict):
                # launch the compound editor for complex types (list and dict)
                input_widget = QtWidgets.QPushButton()
                input_widget.setText('Edit...')
                # lambda needs to consume the extra value from connect(), hence x
                input_widget.clicked.connect(
                    lambda x, it=item: self._edit_with_compound_editor(it)
                )
                # do not register compound editor buttons as cfg widgets, since the compound editor
                # callback updates cfg by itsel
                _save_widget = False
            else:
                # for any other types, use a line edit with the literal value
                input_widget = QtWidgets.QLineEdit()
                input_widget.setText(item.literal_value)
                input_widget.setCursorPosition(0)  # show beginning of line
            lout.addRow(desc, input_widget)
            if _save_widget:
                self._input_widgets[secname][item.name] = input_widget
        return tab

    def __init__(self, parent, default_tab=0):
        super(self.__class__, self).__init__(parent)
        _main_layout = QtWidgets.QVBoxLayout(self)
        self._input_widgets = defaultdict(lambda: dict())

        # build button box
        std_buttons = QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        self.buttonBox = QtWidgets.QDialogButtonBox(std_buttons)
        loadButton = QtWidgets.QPushButton('Load...')
        saveButton = QtWidgets.QPushButton('Save...')
        self.buttonBox.addButton(loadButton, QtWidgets.QDialogButtonBox.ActionRole)
        self.buttonBox.addButton(saveButton, QtWidgets.QDialogButtonBox.ActionRole)
        loadButton.clicked.connect(self.load_config_dialog)
        saveButton.clicked.connect(self.save_config_dialog)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)

        # build tabs according to cfg
        self.tabWidget = QtWidgets.QTabWidget()
        secs = sorted(((secname, sec) for secname, sec in cfg), key=lambda tup: tup[0])
        for secname, sec in secs:
            desc = configdot.get_description(sec) or secname
            tab = self._create_tab(sec, secname)
            self.tabWidget.addTab(tab, desc)

        _main_layout.addWidget(self.tabWidget)
        helptext = QtWidgets.QLabel()
        helptext.setText(
            'Changes into options will stay in effect until the program is restarted. To make changes\n'
            'permanent and automatically loaded on startup, save them into\n%s'
            % cfg_user_fn
        )
        _main_layout.addWidget(helptext)
        _main_layout.addWidget(self.buttonBox)
        self.setLayout(_main_layout)
        self.setWindowTitle('Edit configuration')

    def _edit_with_compound_editor(self, item):
        """Opens a compound editor for selected config item"""
        val = item.value
        editor = QCompoundEditorDict if isinstance(val, dict) else QCompoundEditorList
        dlg = editor(val)
        if dlg.exec_():
            item.value = dlg.data

    def load_config_dialog(self):
        """Bring up load dialog and load selected file"""
        fout = QtWidgets.QFileDialog.getOpenFileName(
            self, 'Load config file', op.expanduser('~'), 'Config files (*.cfg)'
        )
        fname = fout[0]
        if fname:
            try:
                cfg_new = configdot.parse_config(fname)
                configdot.update_config(
                    cfg,
                    cfg_new,
                    create_new_sections=False,
                    create_new_items=['layouts'],
                    update_comments=False,
                )
            except ValueError:
                qt_message_dialog('Could not parse %s' % fname)
            else:
                self._update_inputs()

    def save_config_dialog(self):
        """Bring up save dialog and save data"""
        wname, txt = self._update_cfg()
        if wname is not None:
            qt_message_dialog(
                'Invalid input for item %s: %s\n'
                'Please fix before saving' % (wname, txt)
            )
        else:
            fout = QtWidgets.QFileDialog.getSaveFileName(
                self, 'Save config file', op.expanduser('~'), 'Config files (*.cfg)'
            )
            fname = fout[0]
            if fname:
                with io.open(fname, 'w', encoding='utf8') as f:
                    txt = configdot.dump_config(cfg)
                    f.writelines(txt)

    def _update_inputs(self):
        """Update value-visible input widgets according to current cfg"""
        for secname, sec in cfg:
            for itemname, item in sec:
                if itemname not in self._input_widgets[secname]:
                    continue
                _widget = self._input_widgets[secname][itemname]
                val = item.literal_value
                if isinstance(_widget, QtWidgets.QLineEdit):
                    _widget.setText(val)
                    _widget.setCursorPosition(0)
                elif isinstance(_widget, QtWidgets.QCheckBox):
                    _widget.setChecked(item.value)

    def _update_cfg(self):
        """Update cfg according to input widgets"""
        for secname, sec in cfg:
            for itemname, item in sec:
                if itemname not in self._input_widgets[secname]:
                    continue
                _widget = self._input_widgets[secname][itemname]
                if isinstance(_widget, QtWidgets.QLineEdit):
                    try:
                        item.value = ast.literal_eval(_widget.text())
                    except (SyntaxError, ValueError):
                        return itemname, _widget.text()
                elif isinstance(_widget, QtWidgets.QCheckBox):
                    item.value = _widget.isChecked()
                else:
                    raise RuntimeError('Invalid input widget class, how come?')
        _handle_cfg_defaults(cfg)
        return None, None

    def accept(self):
        """Update config and close dialog, if widget inputs are ok. Otherwise show error dialog"""
        wname, txt = self._update_cfg()
        if wname is not None:
            qt_message_dialog(
                'Invalid input for item %s: %s\n'
                'Please fix before closing or cancel dialog' % (wname, txt)
            )
        else:
            self.done(QtWidgets.QDialog.Accepted)  # or call superclass accept


class ChooseSessionsDialog(QtWidgets.QDialog):
    """A dialog for picking report sessions"""

    def __init__(self, min_sessions=1, max_sessions=3):
        QtWidgets.QDialog.__init__(self)
        # load user interface made with designer
        uifile = resource_filename('gaitutils', 'gui/sessions.ui')
        uic.loadUi(uifile, self)
        # self.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        self.btnBrowseSession.clicked.connect(self.add_session)
        self.btnAddNexusSession.clicked.connect(
            lambda: self.add_session(from_nexus=True)
        )
        self.btnClearAll.clicked.connect(self.listSessions.clear)
        self.btnClearCurrent.clicked.connect(self.listSessions.rm_current_item)
        self.max_sessions = max_sessions
        self.min_sessions = min_sessions

    def add_session(self, from_nexus=False):
        if len(self.sessions) == self.max_sessions:
            qt_message_dialog(
                'You can specify maximum of %d sessions' % self.max_sessions
            )
            return
        if from_nexus:
            try:
                dirs = [nexus.get_sessionpath()]
            except GaitDataError:
                qt_message_dialog('Cannot get session path from Nexus')
                return
        else:
            dirs = qt_dir_chooser()
        dirs = [op.normpath(d) for d in dirs]
        for dir_ in dirs:
            if dir_ in self.sessions:
                qt_message_dialog('Session %s already loaded' % dir_)
            else:
                self.listSessions.add_item(dir_, data=dir_)

    @property
    def sessions(self):
        return [item.userdata for item in self.listSessions.items]

    def accept(self):
        if len(self.sessions) < self.min_sessions:
            qt_message_dialog(
                'Please select at least %d session%s'
                % (self.min_sessions, 's' if self.min_sessions > 1 else '')
            )
        else:
            self.done(QtWidgets.QDialog.Accepted)
