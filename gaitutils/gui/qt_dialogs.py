# -*- coding: utf-8 -*-
"""
PyQt dialogs etc.

@author: Jussi (jnu@iki.fi)
"""

from PyQt5 import uic, QtWidgets
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from pkg_resources import resource_filename
import os.path as op
import ast
import io
from collections import defaultdict
import logging

from .qt_dictedit_proto import QCompoundEditorDict, QCompoundEditorList
from .. import nexus, GaitDataError, cfg
from ulstools import configdot
from ..config import _handle_cfg_defaults, cfg_user_fn

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
        for item in items:
            desc = configdot.get_description(item)
            if isinstance(item.value, bool):  # use simple checkbox for booleans
                input_widget = QtWidgets.QCheckBox()
                input_widget.setChecked(item.value)
            elif isinstance(item.value, list) or isinstance(item.value, dict):
                # launch the editor for complex types (list and dict)
                input_widget = QtWidgets.QPushButton()
                input_widget.setText('Edit...')
                # lambda needs to consume the extra value from connect(), hence x
                input_widget.clicked.connect(lambda x, it=item: self._edit_with_compound_editor(it))
            else:
                # for anything else, use a line edit with the literal value
                input_widget = QtWidgets.QLineEdit()
                input_widget.setText(item.literal_value)
                input_widget.setCursorPosition(0)  # show beginning of line
            lout.addRow(desc, input_widget)
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


class ChooseSessionsDialogWeb(ChooseSessionsDialog):
    """Web report sessions dialog"""

    def __init__(self, min_sessions=1, max_sessions=3):
        QtWidgets.QDialog.__init__(self)
        # load user interface made with designer
        uifile = resource_filename('gaitutils', 'gui/web_report_sessions.ui')
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


#    def accept(self):
#        self.recreate_plots = self.xbRecreatePlots.checkState()
#        super(ChooseSessionsDialogWeb, self).accept()
