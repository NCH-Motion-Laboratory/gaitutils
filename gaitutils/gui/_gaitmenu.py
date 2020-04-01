#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
PyQt graphical interface to gaitutils

@author: Jussi (jnu@iki.fi)
"""

from __future__ import print_function
from __future__ import division

from builtins import str
from PyQt5 import QtGui, QtCore, uic, QtWidgets
from PyQt5.QtCore import QRunnable, QThreadPool, pyqtSignal, QObject
from pkg_resources import resource_filename
from functools import partial
import sys
import os.path as op
import os
import time
import requests
import logging
import traceback
import ulstools
from ulstools import configdot

from .qt_dialogs import (
    OptionsDialog,
    qt_message_dialog,
    qt_yesno_dialog,
    ChooseSessionsDialog,
    qt_matplotlib_window,
    qt_dir_chooser,
)
from .qt_widgets import QtHandler, ProgressBar, ProgressSignals, XStream
from ulstools.num import check_hetu
from ..normaldata import read_default_normaldata
from ..videos import _collect_session_videos, convert_videos
from .. import GaitDataError, nexus, cfg, sessionutils, envutils, c3d, stats, trial
from . import _tardieu
from ..autoprocess import (
    autoproc_session,
    autoproc_trial,
    automark_trial,
    copy_session_videos,
)
from ..viz.plots import (
    plot_trials,
    plot_trial_timedep_velocities,
    plot_trial_velocities,
)
from ..viz.timedist import do_session_average_plot
from ..viz.plot_misc import _browse_localhost, _show_plotly_fig
from ..report import web, pdf

logger = logging.getLogger(__name__)

# setting this disables our internal handling of uncaught exceptions (so that the debugger
# can catch them) and also enables VSCode debugging of PyQt threads that we launch
DEBUG_MODE = False
if DEBUG_MODE:
    import ptvsd


def _get_nexus_sessionpath():
    """Get Nexus sessionpath, handle exceptions for use outside _run_in_thread"""
    try:
        return nexus.get_sessionpath()
    except GaitDataError as e:
        _report_exception(e)
        return None


def _report_exception(e, title=None):
    """Report an exception via Qt dialog. Show title and exception message"""
    logger.debug('caught exception when running task')
    if title is None:
        title = 'There was an error running the operation. Details:'
    e_msg = _exception_msg(e)
    msg = '%s\n%s' % (title, e_msg)
    qt_message_dialog(msg)


def _exception_msg(e):
    """Return text representation of exception e"""
    # for our own error class, we know that a neat message is there
    # otherwise, we have no idea, so use generic repr()
    # XXX: some exception classes (e.g. IOError) repr doesn't print all relevant information
    # (e.g. the file name), however it looks like the safest choice (str() has its own issues)
    # this can probably be improved for Py3
    return e.message if isinstance(e, GaitDataError) else repr(e)


class PdfReportDialog(QtWidgets.QDialog):
    """Ask for patient/session info and report options"""

    def __init__(self, info, comparison=False, parent=None):
        super(self.__class__, self).__init__()
        self.comparison = comparison
        ui_filename = (
            'pdf_report_dialog_comparison.ui' if comparison else 'pdf_report_dialog.ui'
        )
        uifile = resource_filename('gaitutils', 'gui/%s' % ui_filename)
        uic.loadUi(uifile, self)
        # self.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        if info is not None:
            if info['fullname'] is not None:
                self.lnFullName.setText(info['fullname'])
            if info['hetu'] is not None:
                self.lnHetu.setText(info['hetu'])
            if info['session_description'] is not None:
                self.lnDescription.setText(info['session_description'])

    def accept(self):
        """ Update config and close dialog, if widget inputs are ok. Otherwise
        show an error dialog """
        self.hetu = self.lnHetu.text()
        self.fullname = self.lnFullName.text()
        self.session_description = self.lnDescription.text()
        # take the page selections and write them into a dict (keys are named after the
        # selection widgets)
        self.pages = dict()
        for w in self.findChildren(QtWidgets.QWidget):
            wname = w.objectName()
            if wname[:2] == 'cb':
                self.pages[wname[2:]] = w.checkState()
        # require patient name if it's not a comparison report (which might compare different
        # patients); hetu needs to be valid if it's entered
        if (self.comparison or self.fullname) and (
            check_hetu(self.hetu) or not self.hetu
        ):
            self.done(QtWidgets.QDialog.Accepted)  # or call superclass accept
        else:
            qt_message_dialog(
                'Please enter a name. If hetu (Finnish SSN) is entered, it needs to be valid.'
            )


class WebReportInfoDialog(QtWidgets.QDialog):
    """Ask for patient info"""

    def __init__(self, info, parent=None, check_info=True):
        super(self.__class__, self).__init__()
        uifile = resource_filename('gaitutils', 'gui/web_report_info.ui')
        uic.loadUi(uifile, self)
        # self.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        self.check_info = check_info
        if info is not None:
            if info['fullname'] is not None:
                self.lnFullName.setText(info['fullname'])
            if info['hetu'] is not None:
                self.lnHetu.setText(info['hetu'])

    def accept(self):
        """ Update config and close dialog, if widget inputs are ok. Otherwise
        show an error dialog """
        self.recreate_plots = self.xbRecreatePlots.checkState()
        self.force_convert_videos = self.xbForceConvertVideos.checkState()
        self.video_only = self.xbVideoOnly.checkState()
        self.hetu = self.lnHetu.text().strip()
        self.fullname = self.lnFullName.text().strip()
        if self.check_info:
            ok = self.fullname and check_hetu(self.hetu)
        else:
            ok = not self.hetu or check_hetu(self.hetu)
        if ok:
            self.done(QtWidgets.QDialog.Accepted)  # or call superclass accept
        else:
            msg = 'Please enter a valid name and hetu'
            if not self.check_info:
                msg += ' (or leave empty)'
            qt_message_dialog(msg)


class WebReportDialog(QtWidgets.QDialog):
    """Dialog for managing web reports. In current implementation, this needs a
    GaitMenu instance as a parent (uses _run_in_thread() and other parent methods)"""

    def __init__(self, parent):
        super(self.__class__, self).__init__(parent)
        self.parent = parent
        # load user interface made with designer
        uifile = resource_filename('gaitutils', 'gui/web_report_dialog.ui')
        uic.loadUi(uifile, self)
        self.btnCreateReport.clicked.connect(lambda ev: self._create_web_report())
        self.btnDeleteReport.clicked.connect(self._delete_current_report)
        self.btnDeleteAllReports.clicked.connect(self._delete_all_reports)
        self.btnViewReport.clicked.connect(self._view_current_report)
        # add double click action to browse current report
        (
            self.listActiveReports.itemDoubleClicked.connect(
                lambda item: _browse_localhost(port=item.userdata)
            )
        )
        # these require active reports to be enabled
        self.reportWidgets = [
            self.btnDeleteReport,
            self.btnDeleteAllReports,
            self.btnViewReport,
        ]
        self._set_report_button_status()

    def _create_web_report(self, sessions=None):
        """Collect sessions, create the dash app, start it and launch a
        web browser on localhost on the correct port"""

        if self.listActiveReports.count() == cfg.web_report.max_reports:
            qt_message_dialog(
                'Maximum number of active web reports active. '
                'Please delete some reports first.'
            )
            return

        if sessions is None:
            dlg = ChooseSessionsDialog()
            if not dlg.exec_():
                return
            sessions = dlg.sessions
        report_name = web._report_name(sessions)
        existing_names = [item.text for item in self.listActiveReports.items]
        if report_name in existing_names:
            qt_message_dialog('There is already a report for %s' % report_name)
            return

        # gather patient info files and merge them
        session_infos, info = sessionutils._merge_session_info(sessions)
        if info is None:
            qt_message_dialog(
                'Patient files do not match. Sessions may be '
                'from different patients. Continuing with default '
                'patient info.'
            )
            info = sessionutils.default_info()

        # ask user for info updates
        # dialog will be prepopulated with the values gathered above
        dlg_info = WebReportInfoDialog(info, check_info=False)
        if dlg_info.exec_():
            new_info = dict(hetu=dlg_info.hetu, fullname=dlg_info.fullname,)
            recreate_plots = dlg_info.recreate_plots
            force_convert_videos = dlg_info.force_convert_videos
            video_only = dlg_info.video_only
            info.update(new_info)

            # update info files in all sessions according to the user input
            # exclude the session specific keys
            for session in sessions:
                update_dict = dict(fullname=dlg_info.fullname, hetu=dlg_info.hetu,)
                session_infos[session].update(update_dict)
                sessionutils.save_info(session, session_infos[session])
        else:
            return

        # give progress bar to parent so that parent can close it
        self.parent.prog = ProgressBar('Creating web report...')
        self.parent.prog.update('Collecting session information...', 0)
        signals = ProgressSignals()
        signals.progress.connect(lambda text, p: self.parent.prog.update(text, p))
        self.parent.prog._canceled.connect(signals.cancel)

        # for comparison between sessions, get representative trials only
        tags = cfg.eclipse.repr_tags if len(sessions) > 1 else cfg.eclipse.tags

        # collect all video files for conversion
        # includes tagged dynamic, video-only tagged, and static trials
        vidfiles = list()
        for session in sessions:
            vids = _collect_session_videos(session, tags=tags)
            vidfiles.extend(vids)

        if force_convert_videos or not convert_videos(vidfiles, check_only=True):
            self.parent._convert_vidfiles(vidfiles, signals)

        # launch the report creation thread
        self.parent._run_in_thread(
            web.dash_report,
            block_ui=True,
            finished_func=self.parent._enable_main_ui,
            result_func=self._web_report_ready,
            info=info,
            sessions=sessions,
            tags=tags,
            signals=signals,
            recreate_plots=recreate_plots,
            video_only=video_only,
        )

    @property
    def active_reports(self):
        """Return number of active web reports"""
        return self.listActiveReports.count()

    def shutdown(self):
        """Try to shutdown web servers"""
        # cannot use generator here since the loop changes the items
        for item in list(self.listActiveReports.items):
            self._delete_report(item)

    def _delete_report(self, item):
        """Shut down server for given list item, remove item"""
        port = item.userdata
        # compose url for shutdown request - see report.py
        url = 'http://127.0.0.1:%d/shutdown' % port
        # we have to make sure that localhost is not proxied
        proxies = {"http": None, "https": None}
        logger.debug('requesting server shutdown for port %d' % port)
        requests.get(url, proxies=proxies)
        self.listActiveReports.rm_current_item()

    def _delete_current_report(self):
        """Shut down server for current item, remove item"""
        item = self.listActiveReports.currentItem()
        if item is None:
            return
        msg = 'Are you sure you want to delete the report for %s?' % item.text
        reply = qt_yesno_dialog(msg)
        if reply == QtWidgets.QMessageBox.YesRole:
            self._delete_report(item)
        self._set_report_button_status()

    def _delete_all_reports(self):
        """Delete all web reports"""
        if self.listActiveReports.count() == 0:
            return
        msg = 'Are you sure you want to delete all reports?'
        reply = qt_yesno_dialog(msg)
        if reply != QtWidgets.QMessageBox.YesRole:
            return
        # cannot use generator here since the loop changes the items
        for item in list(self.listActiveReports.items):
            self._delete_report(item)
        self._set_report_button_status()

    def _view_current_report(self):
        """Open current report in browser"""
        item = self.listActiveReports.currentItem()
        if item is None:
            return
        port = item.userdata
        _browse_localhost(port=port)

    def _set_report_button_status(self):
        """Enable report buttons if reports exist, otherwise disable them"""
        n_reports = self.active_reports
        for widget in self.reportWidgets:
            widget.setEnabled(True if n_reports else False)

    def _web_report_ready(self, app):
        """Gets called when web report creation is successful. Open report in
        browser"""
        if app is None:
            # this should only happen when the report was cancelled, so we
            # exit quietly
            return
        # figure out first free TCP port
        ports_taken = [item.userdata for item in self.listActiveReports.items]
        port = cfg.web_report.tcp_port
        while port in ports_taken:  # find first port not taken by us
            port += 1
        """
        Web servers need to go into separate threads/processes so that the rest
        of the app can continue running. It's hard to use processes because of
        problems with multiprocessing/pickle, so the Qt threadpool is used to
        launch the servers. However since each running server occupies a
        thread, this means that we need to increase the threadpool max threads
        limit; otherwise new servers will get queued by the threadpool and will
        not run.
        Serving is a bit flaky in py2 (multiple requests cause exceptions)
        """
        self.parent._run_in_thread(
            app.server.run, block_ui=False, debug=False, port=port, threaded=True
        )
        # double clicking on the list item will browse to corresponding port
        self.listActiveReports.add_item(app._gaitutils_report_name, data=port)
        # enable delete buttons etc.
        self._set_report_button_status()
        _browse_localhost(port=port)


class AddSessionDialog(QtWidgets.QDialog):
    """Dialog for adding trials to trials list"""

    def __init__(self, parent):
        QtWidgets.QDialog.__init__(self)
        uifile = resource_filename('gaitutils', 'gui/add_session_dialog.ui')
        uic.loadUi(uifile, self)

    def accept(self):
        self.c3ds = list()
        tags = cfg.eclipse.tags if self.rbAddTaggedTrials.isChecked() else None
        # get session
        if self.rbUseCurrentNexusSession.isChecked():
            session = _get_nexus_sessionpath()
        else:
            sessions = qt_dir_chooser()
            session = sessions[0] if sessions else None
        if session:
            self.c3ds = sessionutils.get_c3ds(session, tags=tags, trial_type='dynamic')
            if self.c3ds:
                self.done(QtWidgets.QDialog.Accepted)
            else:
                qt_message_dialog('No trials found for session %s' % session)


class Gaitmenu(QtWidgets.QMainWindow):
    def __init__(self):
        super(self.__class__, self).__init__()
        # load user interface made with designer
        uifile = resource_filename('gaitutils', 'gui/gaitmenu.ui')
        uic.loadUi(uifile, self)

        # disable editing of log widget text
        self.txtOutput.setReadOnly(True)

        if (
            not cfg.general.allow_multiple_menu_instances
            and ulstools.env.already_running('gaitmenu')
        ):
            qt_message_dialog(
                'Another instance of the menu seems to be '
                'running. Please use that instance or '
                'stop it before starting a new one.'
            )
            sys.exit()

        if cfg.general.git_autoupdate:
            if envutils._git_autoupdate():
                qt_message_dialog(
                    'The package was automatically updated. Restarting...'
                )
                os.execv(sys.executable, ['python'] + sys.argv)

        self._web_report_dialog = WebReportDialog(self)

        # connect ui widgets
        self.btnAddSession.clicked.connect(self._add_session_dialog)
        self.btnAddTrials.clicked.connect(self._add_trials_dialog)
        self.btnAddNexusTrial.clicked.connect(self._add_nexus_trial)
        self.btnSelectAll.clicked.connect(self._select_all_trials)
        self.btnClearSelected.clicked.connect(self._remove_selected_trials)
        self.btnPlotTrials.clicked.connect(self._plot_selected_trials)
        self.btnAveragePlot.clicked.connect(self._average_trials)
        self.actionCreate_PDF_report.triggered.connect(
            lambda ev: self._create_pdf_report()
        )
        self.actionWeb_reports.triggered.connect(self._web_report_dialog.show)
        self.actionQuit.triggered.connect(self.close)
        self.actionOpts.triggered.connect(self._options_dialog)
        self.actionTardieu_analysis.triggered.connect(self._tardieu)
        self.actionAutoprocess_session.triggered.connect(self._autoproc_session)
        self.actionAutoprocess_single_trial.triggered.connect(self._autoproc_trial)
        self.actionPDF_report_from_Nexus_session.triggered.connect(
            self._create_pdf_report_nexus
        )
        self.actionWeb_report_from_Nexus_session.triggered.connect(
            self._create_web_report_nexus
        )
        self.actionRun_postprocessing_pipelines.triggered.connect(
            self._postprocess_session
        )
        self.actionTrial_median_velocities.triggered.connect(
            self._plot_trial_median_velocities
        )
        self.actionTrial_timedep_velocities.triggered.connect(
            self._plot_trial_timedep_velocities
        )
        self.actionConvert_session_videos_to_web_format.triggered.connect(
            self._convert_session_videos
        )
        self.actionTime_distance_average.triggered.connect(self._plot_timedist_average)
        # XXX: these get run in the main thread
        self.actionCopy_session_videos_to_desktop.triggered.connect(copy_session_videos)
        self.actionAutomark_events.triggered.connect(self._automark_trial)
        # trials table settings
        # force "item selected" style, otherwise it will depend on focus; set font size
        table_sheet = "QTableView{ selection-background-color: rgba(0, 0, 255, 50%); font-size: 8pt; }"
        self.tableTrials.setStyleSheet(table_sheet)
        self.tableTrials.cellDoubleClicked.connect(self._cell_doubleclicked)

        # set up radio buttons
        self.rb_map_backend = {'plotly': self.rbPlotly, 'matplotlib': self.rbMatplotlib}
        rb_backend_active = self.rb_map_backend[cfg.plot.backend]
        rb_backend_active.setChecked(True)

        def _colorstylevar_changed(self):
            logger.debug('callback')

        # set up color/style comboboxes
        self.cbColorStyleVar.currentIndexChanged.connect(self._colorstylevar_changed)
        # this callback only needs to fire when user activates the combobox
        self.cbColorStyleBy.activated.connect(self._colorstyleby_changed)
        # dynamically create combobox entries according to cfg
        for vartype, col_choice in cfg.plot.color_by.items():
            self.cbColorStyleVar.addItem(
                'Set %s trace color by:' % vartype, userData=('color', vartype)
            )
        for vartype, sty_choice in cfg.plot.style_by.items():
            self.cbColorStyleVar.addItem(
                'Set %s trace style by:' % vartype, userData=('style', vartype)
            )

        # add plot layouts to layout combobox
        cb_items = sorted(
            configdot.get_description(lo) or loname for loname, lo in cfg['layouts']
        )
        self.cbLayout.addItems(cb_items)
        # set default option to PiG lower body (if it's on the list)
        try:
            default_index = cb_items.index('PiG lower body kinematics')
        except ValueError:
            default_index = 0
        self.cbLayout.setCurrentIndex(default_index)
        # map descriptions to layout names
        self.layouts_map = {
            (configdot.get_description(lo) or loname): loname
            for loname, lo in cfg['layouts']
        }

        XStream.stdout().messageWritten.connect(self._log_message)
        XStream.stderr().messageWritten.connect(self._log_message)
        self.threadpool = QThreadPool()
        # we need a thread for each web server plus one worker thread
        self.threadpool.setMaxThreadCount(cfg.web_report.max_reports + 1)
        # keep refs to tardieu+mpl windows so they don't get garbage collected
        self._tardieuwin = None
        self._mpl_windows = list()
        # progress bar
        self.prog = None

    def _colorstylevar_changed(self, _idx):
        """Callback for color/style variable selection combobox"""
        # get current style/color choice and show it in the other combobox
        mode, vartype = self.cbColorStyleVar.currentData()
        cfg_item = {'color': cfg.plot.color_by, 'style': cfg.plot.style_by}[mode]
        choice = cfg_item[vartype]
        if choice is None:
            choice = 'none'
        idx = self.cbColorStyleBy.findText(choice)
        self.cbColorStyleBy.setCurrentIndex(idx)
        # don't allow styling for EMG variables
        enabled = not (vartype == 'emg' and mode == 'style')
        self.cbColorStyleBy.setEnabled(enabled)

    def _colorstyleby_changed(self, _idx):
        """Callback for color/style selection combobox"""
        mode, vartype = self.cbColorStyleVar.currentData()
        # set the appropriate cfg item according to choice
        cfg_item = {'color': cfg.plot.color_by, 'style': cfg.plot.style_by}[mode]
        colorstyleby_choice = self.cbColorStyleBy.currentText()
        # Py2: convert unicode choices to str
        # (unicode prefix looks weird in Options interface)
        if sys.version_info.major == 2:
            colorstyleby_choice = str(colorstyleby_choice)
        if colorstyleby_choice == 'none':
            colorstyleby_choice = None
        cfg_item[vartype] = colorstyleby_choice

    def _get_plotting_backend_ui(self):
        """Get backend selection from UI"""
        for backend, rb in self.rb_map_backend.items():
            if rb.isChecked():
                return backend

    def _get_trial_sel(self):
        """Get trials selection from UI"""
        for trial_sel, rb in self.rb_map_trials.items():
            if rb.isChecked():
                return trial_sel

    def _automark_trial(self):
        session = _get_nexus_sessionpath()
        if session is None:
            return
        self._run_in_thread(automark_trial, finished_func=self._enable_main_ui)

    def _autoproc_session(self):
        """Wrapper to run autoprocess for Nexus session"""
        session = _get_nexus_sessionpath()
        if session is None:
            return
        c3ds = sessionutils.get_c3ds(session, trial_type='DYNAMIC')
        if c3ds:
            reply = qt_yesno_dialog(
                'Some of the dynamic trials have been '
                'processed already. Are you sure you want '
                'to run autoprocessing?'
            )
            if reply == QtWidgets.QMessageBox.NoRole:
                return

        self.prog = ProgressBar('Running autoprocessing...')
        signals = ProgressSignals()
        signals.progress.connect(lambda text, p: self.prog.update(text, p))
        self.prog._canceled.connect(signals.cancel)

        self._run_in_thread(
            autoproc_session, finished_func=self._enable_main_ui, signals=signals
        )

    def _autoproc_trial(self):
        """Wrapper to run autoprocess for Nexus trial"""

        self.prog = ProgressBar('Running autoprocessing...')
        signals = ProgressSignals()
        signals.progress.connect(lambda text, p: self.prog.update(text, p))
        self.prog._canceled.connect(signals.cancel)

        self._run_in_thread(
            autoproc_trial, finished_func=self._enable_main_ui, signals=signals
        )

    def _plot_timedist_average(self):
        """Plot time-distance average"""
        session = _get_nexus_sessionpath()
        if session is None:
            return
        backend = self._get_plotting_backend_ui()
        self._run_in_thread(
            do_session_average_plot,
            finished_func=self._enable_main_ui,
            result_func=self._show_plots,
            session=session,
            backend=backend,
        )

    def _plot_trial_median_velocities(self):
        """Trial velocity plot from current Nexus session"""
        session = _get_nexus_sessionpath()
        if session is None:
            return
        backend = self._get_plotting_backend_ui()
        self._run_in_thread(
            plot_trial_velocities,
            finished_func=self._enable_main_ui,
            result_func=self._show_plots,
            session=session,
            backend=backend,
        )

    def _plot_trial_timedep_velocities(self):
        """Trial velocity plot from current Nexus session"""
        session = _get_nexus_sessionpath()
        if session is None:
            return
        backend = self._get_plotting_backend_ui()
        self._run_in_thread(
            plot_trial_timedep_velocities,
            finished_func=self._enable_main_ui,
            result_func=self._show_plots,
            session=session,
            backend=backend,
        )

    def _add_trial_to_table(self, tr):
        """Adds a trial to the trials table"""
        nrows = self.tableTrials.rowCount()
        self.tableTrials.insertRow(nrows)
        texts = (
            tr.trialname,
            tr.eclipse_data['DESCRIPTION'],
            tr.eclipse_data['NOTES'],
            tr.sessionpath,
        )
        for k, txt in enumerate(texts):
            item_ = QtWidgets.QTableWidgetItem(txt)
            if k == 0:
                # actual Trial instances are stored as userdata of
                # QTableWidgetItems on each rows 1st column; thus
                # we don't have to keep separate references to them
                item_.setData(QtCore.Qt.UserRole, tr)
            self.tableTrials.setItem(nrows, k, item_)

    def _add_c3dfiles(self, c3dfiles):
        """Add given c3d files to trials list"""
        c3dfiles = (op.normpath(fn) for fn in c3dfiles)
        self._disable_main_ui()  # in case it takes a while
        for c3dfile in c3dfiles:
            try:
                tr = trial.Trial(c3dfile)
            except GaitDataError as e:
                title = 'Could not load trial %s. Details:' % op.split(c3dfile)[-1]
                _report_exception(e, title=title)
            else:
                self._add_trial_to_table(tr)
                self.tableTrials.resizeColumnsToContents()
            finally:
                self._enable_main_ui()

    def _add_nexus_trial(self):
        """Add directly from Nexus"""
        try:
            tr = trial.nexus_trial(from_c3d=cfg.trial.load_from_c3d)
        except GaitDataError as e:
            _report_exception(e)
        else:
            self._add_trial_to_table(tr)
            self.tableTrials.resizeColumnsToContents()

    def _add_session_dialog(self):
        """Show the add session dialog and add trials to list"""
        dlg = AddSessionDialog(self)
        if dlg.exec_():
            self._add_c3dfiles(dlg.c3ds)

    def _add_trials_dialog(self):
        """Add individual trials to list"""
        fout = QtWidgets.QFileDialog.getOpenFileNames(
            self, 'Load C3D files', None, 'C3D files (*.c3d)'
        )
        if fout[0]:
            self._add_c3dfiles(fout[0])

    def _select_all_trials(self):
        """Select all trials"""
        self.tableTrials.selectAll()

    @property
    def _selected_rows(self):
        """Return indices of selected rows"""
        return list(set(idx.row() for idx in self.tableTrials.selectedIndexes()))

    def _cell_doubleclicked(self, row, col):
        """Plot trial on double click"""
        tr = self.tableTrials.item(row, 0).data(QtCore.Qt.UserRole)
        self._plot_trials([tr])

    @property
    def _selected_trials(self):
        """Return list of trials that are currently selected"""
        sel_items = (self.tableTrials.item(row, 0) for row in self._selected_rows)
        return list(item.data(QtCore.Qt.UserRole) for item in sel_items)

    def _remove_selected_trials(self):
        """Remove selected trials from list"""
        while self._selected_rows:
            # this relies on _selected_rows dynamically changing after removals
            row = self._selected_rows[0]
            self.tableTrials.removeRow(row)

    def _plot_selected_trials(self):
        if not self._selected_rows:
            return
        if any(tr.is_static for tr in self._selected_trials):
            qt_message_dialog(
                'One or more trials are static, plotting all trials as unnormalized'
            )
            self._plot_trials(self._selected_trials, normalized=False)
        else:
            self._plot_trials(self._selected_trials)

    def _plot_trials(self, trials, normalized=True):
        """Plot specified trials, or selected trials from menu"""
        have_avgtrials = any(isinstance(tr, stats.AvgTrial) for tr in trials)
        if not normalized or self.xbPlotUnnorm.checkState():
            if have_avgtrials:
                qt_message_dialog('Cannot plot average trials as unnormalized')
                return
            cycles = 'unnormalized'
        else:
            cycles = None
        model_normaldata = read_default_normaldata()
        layout_desc = self.cbLayout.currentText()
        layout_name = self.layouts_map[layout_desc]
        backend = self._get_plotting_backend_ui()

        if self.xbEMGRMS.checkState():
            emg_mode = 'rms'
        elif have_avgtrials and 'EMG' in layout_name.upper():
            qt_message_dialog('Averaged EMG can only be plotted in RMS mode')
            return
        else:
            emg_mode = None

        backend = self._get_plotting_backend_ui()
        # FIXME: hardcoded legend type
        self._run_in_thread(
            plot_trials,
            finished_func=self._enable_main_ui,
            result_func=self._show_plots,
            trials=trials,
            layout_name=layout_name,
            backend=backend,
            cycles=cycles,
            emg_mode=emg_mode,
            legend_type='short_name_with_tag_and_cycle',
            model_normaldata=model_normaldata,
            auto_adjust_emg_layout=False,
        )

    def _average_trials(self):
        """Average trials from list, add resulting averaged trial to list"""
        if len(self._selected_rows) < 2:
            qt_message_dialog('Need at least 2 trials for averaging')
            return
        if any(isinstance(tr, stats.AvgTrial) for tr in self._selected_trials):
            qt_message_dialog('Cannot include averaged trials in average')
            return
        reject_outliers = cfg.trial.outlier_rejection_threshold
        self._run_in_thread(
            stats.AvgTrial.from_trials,
            finished_func=self._enable_main_ui,
            result_func=self._add_trial_to_table,
            trials=self._selected_trials,
            reject_outliers=reject_outliers,
        )

    def _create_web_report_nexus(self):
        """Create web report based on current Nexus session"""
        session = _get_nexus_sessionpath()
        if session:
            self._web_report_dialog._create_web_report(sessions=[session])

    def _show_plots(self, fig, backend=None):
        """Shows fig"""
        if backend is None:
            backend = self._get_plotting_backend_ui()
        if backend == 'matplotlib':
            _mpl_win = qt_matplotlib_window(fig)
            self._mpl_windows.append(_mpl_win)
        elif backend == 'plotly':
            _show_plotly_fig(fig)

    def _convert_vidfiles(self, vidfiles, signals):
        """Convert given list of video files"""
        # get the converter processes
        procs = convert_videos(vidfiles=vidfiles)
        if not procs:
            logger.warning('video converter processes could not be started')
            return
        completed = False
        # wait in sleep loop until all converter processes have finished
        while not completed:
            if signals.canceled:
                logger.debug('canceled, killing video converter processes')
                for p in procs:
                    p.kill()
                break
            n_complete = len([p for p in procs if p.poll() is not None])
            prog_txt = 'Converting videos: %d of %d files done' % (
                n_complete,
                len(procs),
            )
            prog_p = 100 * n_complete / float(len(procs))
            signals.progress.emit(prog_txt, prog_p)
            time.sleep(0.1)
            completed = n_complete == len(procs)

    def _convert_session_videos(self):
        """Convert Nexus session videos to web format"""
        session = _get_nexus_sessionpath()
        if session is None:
            return
        try:
            vidfiles = _collect_session_videos(session, tags=cfg.eclipse.tags)
        except GaitDataError as e:
            qt_message_dialog(_exception_msg(e))
            return
        if not vidfiles:
            qt_message_dialog('Cannot find any video files for session %s' % session)
            return
        if convert_videos(vidfiles, check_only=True):
            reply = qt_yesno_dialog(
                'It looks like the session videos have already been converted. Redo?'
            )
            if reply == QtWidgets.QMessageBox.NoRole:
                return
        self._disable_main_ui()
        self.prog = ProgressBar('Converting session videos...')
        signals = ProgressSignals()
        signals.progress.connect(lambda text, p: self.prog.update(text, p))
        self.prog._canceled.connect(signals.cancel)
        self._convert_vidfiles(vidfiles, signals)
        self._enable_main_ui()

    def _postprocess_session(self):
        """Run additional postprocessing pipelines for tagged trials"""

        def _run_postprocessing():
            """Helper function that will be run in a separate thread"""
            nexus.close_trial()
            for k, tr in enumerate(trials, 1):
                trbase = op.splitext(tr)[0]
                vicon.OpenTrial(trbase, cfg.autoproc.nexus_timeout)
                nexus.run_pipelines_multiprocessing(cfg.autoproc.postproc_pipelines)
                prog_txt = 'Running postprocessing pipelines: %s for %d trials' % (
                    cfg.autoproc.postproc_pipelines,
                    len(trials),
                )
                prog_p = 100 * k / float(len(trials))
                signals.progress.emit(prog_txt, prog_p)
                if signals.canceled:
                    logger.debug('postprocessing pipelines were canceled')
                    return

        session = _get_nexus_sessionpath()
        if session is None:
            return
        # XXX: run for tagged + static - maybe this should be configurable
        trials = sessionutils.get_enfs(
            session, tags=cfg.eclipse.tags, trial_type='dynamic'
        )
        trials += sessionutils.get_enfs(session, trial_type='static')
        # the c3ds don't actually need to exist, the conversion is just for
        # the purpose of feeding correct trial names to Nexus
        trials = [sessionutils.enf_to_trialfile(fn, '.c3d') for fn in trials]
        if trials and cfg.autoproc.postproc_pipelines:
            logger.debug('running postprocessing for %s' % trials)
            vicon = nexus.viconnexus()
            self.prog = ProgressBar('Running postprocessing pipelines...')
            self.prog.update(
                'Running postprocessing pipelines: %s for %d '
                'trials' % (cfg.autoproc.postproc_pipelines, len(trials)),
                0,
            )
            signals = ProgressSignals()
            signals.progress.connect(lambda text, p: self.prog.update(text, p))
            self.prog._canceled.connect(signals.cancel)
            self._run_in_thread(
                _run_postprocessing, block_ui=True, finished_func=self._enable_main_ui
            )
        elif not trials:
            qt_message_dialog('No trials in session to run postprocessing for')
        elif not cfg.autoproc.postproc_pipelines:
            qt_message_dialog('No postprocessing pipelines defined')

    def closeEvent(self, event):
        """ Confirm and close application. """

        if self._web_report_dialog.active_reports:
            reply = qt_yesno_dialog(
                'There are active web reports which '
                'will be closed. Are you sure you '
                'want to quit?'
            )
            if reply == QtWidgets.QMessageBox.YesRole:
                self._web_report_dialog.shutdown()
                self._close_mpl_windows()
                event.accept()
            else:
                event.ignore()
        else:
            self._close_mpl_windows()
            event.accept()

    def _close_mpl_windows(self):
        for win in self._mpl_windows:
            win.close()

    def _options_dialog(self):
        """Show the options dialog"""
        dlg = OptionsDialog(self)
        dlg.exec_()

    def _create_pdf_report_nexus(self):
        session = _get_nexus_sessionpath()
        if session is None:
            return
        self._create_pdf_report([session])

    def _create_pdf_report(self, sessions=None):
        """Create comparison or single session pdf report"""

        if sessions is None:
            dlg = ChooseSessionsDialog()
            if not dlg.exec_():
                return
            sessions = dlg.sessions
        comparison = len(sessions) > 1

        # gather patient info files and merge them
        session_infos, info = sessionutils._merge_session_info(sessions)
        if info is None:  # merge failed
            qt_message_dialog(
                'Patient files do not match. Sessions may be '
                'from different patients. Continuing with default '
                'patient info.'
            )
            info = sessionutils.default_info()

        if comparison:
            # compose a default description for comparison reports
            # we use the session_description field to pass this on to dialog and
            # report creation function
            descs = [_info['session_description'] for _info in session_infos.values()]
            if all(descs):  # use session descriptions if they exist
                info['session_description'] = ' vs. '.join(descs)
            else:  # we don't have description for every session - use dir names instead
                _session_dirs = (op.split(_session)[-1] for _session in sessions)
                info['session_description'] = ' vs. '.join(_session_dirs)

        # get inputs from user
        dlg_info = PdfReportDialog(info, comparison=comparison)
        if dlg_info.exec_():  # dialog was accepted
            new_info = dict(hetu=dlg_info.hetu, fullname=dlg_info.fullname,)
            info.update(new_info)

            # update info files in session dirs (except session specific keys)
            for session in sessions:
                update_dict = dict(fullname=dlg_info.fullname, hetu=dlg_info.hetu,)
                # for single session reports, update also the session description
                if not comparison:
                    update_dict['session_description'] = info['session_description']
                session_infos[session].update(update_dict)
                sessionutils.save_info(session, session_infos[session])
        else:
            return

        # create the report
        kwargs = {
            'info': info,
            'pages': dlg_info.pages,
            'finished_func': self._enable_main_ui,
            'result_func': qt_message_dialog,  # show a message on success
        }
        if comparison:
            fun = pdf.create_comparison_report
            kwargs['sessionpaths'] = sessions
        else:
            fun = pdf.create_report
            kwargs['sessionpath'] = sessions[0]
        self._run_in_thread(fun, **kwargs)

    def _log_message(self, msg):
        """Logs a message to the log widget"""
        c = self.txtOutput.textCursor()
        c.movePosition(QtGui.QTextCursor.End)
        self.txtOutput.setTextCursor(c)
        self.txtOutput.insertPlainText(msg)
        self.txtOutput.ensureCursorVisible()

    def _disable_main_ui(self):
        """ Disable all operation buttons """
        QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
        self.setEnabled(False)  # disables whole main window
        # update display immediately in case thread gets blocked
        QtWidgets.QApplication.processEvents()

    def _enable_main_ui(self):
        """Enable all operation buttons, close progress bar if any and restore cursor."""
        if self.prog is not None:
            self.prog.reset()
        QtWidgets.QApplication.restoreOverrideCursor()
        self.setEnabled(True)

    def _tardieu(self):
        """Open the Tardieu window if it is not currently open"""
        if self._tardieuwin is None or not self._tardieuwin.isVisible():
            self._tardieuwin = _tardieu.TardieuWindow()
            self._tardieuwin.show()

    def _run_in_thread(
        self, fun, block_ui=True, finished_func=None, result_func=None, **kwargs
    ):
        """Run function fun with args kwargs in a worker thread.
        If block_ui==True, disable main ui until worker thread is finished.
        finished_func will be called when thread is finished. result_func
        will be called with the function return value as its single argument,
        unless an exception is raised during thread execution."""
        fun_ = partial(fun, **kwargs)
        if block_ui:
            self._disable_main_ui()
        self.runner = Runner(fun_)
        if finished_func:
            self.runner.signals.finished.connect(finished_func)
        if result_func:
            self.runner.signals.result.connect(lambda r: result_func(r))
        self.runner.signals.error.connect(lambda e: _report_exception(e))
        self.threadpool.start(self.runner)


class RunnerSignals(QObject):
    """Need a separate class since QRunnable cannot emit signals"""

    finished = pyqtSignal()  # thread finished
    result = pyqtSignal(object)  # successful completion - return value
    error = pyqtSignal(Exception)  # exception raised during run


class Runner(QRunnable):
    """Encapsulates threaded functions for QThreadPool"""

    def __init__(self, fun):
        super(Runner, self).__init__()
        self.fun = fun
        self.signals = RunnerSignals()

    def run(self):
        if DEBUG_MODE:  # do not handle exceptions, so that debugger can catch them
            # the ptvsd call is currently needed to debug 'native threads'
            # (apparently PyQt threads are such)
            ptvsd.debug_this_thread()
            retval = self.fun()
            self.signals.result.emit(retval)
            self.signals.finished.emit()
        else:  # the regular version - catch all exceptions and report via gui
            try:
                retval = self.fun()
            except Exception as e:
                self.signals.error.emit(e)
            else:
                self.signals.result.emit(retval)
            finally:
                self.signals.finished.emit()


def main():

    app = QtWidgets.QApplication(sys.argv)

    def my_excepthook(type_, value, tback):
        """ Custom handler for unhandled exceptions:
        report to user via GUI and terminate. """
        tb_full = u''.join(traceback.format_exception(type_, value, tback))
        qt_message_dialog(
            'Oops! An unhandled exception was generated. '
            'The application will be closed.\n\n %s' % tb_full
        )
        # dump traceback to file
        # try:
        #    with io.open(Config.traceback_file, 'w', encoding='utf-8') as f:
        #        f.write(tb_full)
        # here is a danger of infinitely looping the exception hook,
        # so try to catch any exceptions...
        # except Exception:
        #    print('Cannot dump traceback!')
        sys.__excepthook__(type_, value, tback)
        app.quit()

    if not DEBUG_MODE:
        # for normal use, install our own handler for uncaught exceptions
        sys.excepthook = my_excepthook

    # add the Qt logging handler to root logger
    # it shows log messages in our QTextEdit widget
    root_logger = logging.getLogger()
    handler = QtHandler()
    handler.setFormatter(logging.Formatter("%(name)s: %(message)s"))
    root_logger.addHandler(handler)
    root_logger.setLevel(logging.DEBUG)

    # quiet down some noisy loggers
    logging.getLogger('matplotlib').setLevel(logging.WARNING)
    logging.getLogger('PyQt5.uic').setLevel(logging.WARNING)
    logging.getLogger('werkzeug').setLevel(logging.WARNING)

    gaitmenu = Gaitmenu()
    gaitmenu.show()
    logger.debug('Python interpreter: %s' % sys.executable)
    logger.debug('Python version: %s' % sys.version)
    if not c3d.BTK_IMPORTED:
        logger.warning('cannot find btk module; unable to read .c3d files')
    nexus_status = 'Vicon Nexus is %srunning' % ('' if nexus._nexus_pid() else 'not ')
    logger.debug(nexus_status)
    app.exec_()
