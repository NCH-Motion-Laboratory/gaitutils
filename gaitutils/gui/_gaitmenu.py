#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
PyQt graphical interface to gaitutils

@author: Jussi (jnu@iki.fi)
"""

from __future__ import print_function
from builtins import str
from PyQt5 import QtGui, QtCore, uic, QtWidgets
from PyQt5.QtCore import QRunnable, QThreadPool, pyqtSignal, QObject
from pkg_resources import resource_filename
from functools import partial
import sys
import os.path as op
import os
import subprocess
import time
import requests
import logging
import traceback
import plotly

from .qt_dialogs import (OptionsDialog, qt_message_dialog, qt_yesno_dialog,
                         ChooseSessionsDialog, qt_matplotlib_window)
from .qt_widgets import QtHandler, ProgressBar, ProgressSignals, XStream
from ..numutils import check_hetu
from ..videos import _collect_session_videos, convert_videos
from .. import (GaitDataError, nexus, cfg, report, sessionutils,
                envutils)
from . import _tardieu
from ..autoprocess import (autoproc_session, autoproc_trial, automark_trial,
                           copy_session_videos)
from ..viz.plots import (plot_nexus_trial, plot_sessions,
                         plot_trial_timedep_velocities,
                         plot_trial_velocities, plot_session_average)
from ..viz.timedist import do_session_average_plot                         


logger = logging.getLogger(__name__)


def _exception(e):
    logger.debug('caught exception when running task')
    qt_message_dialog(_exception_msg(e))


def _exception_msg(e):
    """Return text representation of exception e"""
    # for our own error class, we know that a neat message is there
    if isinstance(e, GaitDataError):
        err_msg = e.message
    else:  # otherwise, we have no idea, so use generic repr()
        err_msg = repr(e)
    return 'There was an error running the operation. Details:\n%s' % err_msg


class PdfReportDialog(QtWidgets.QDialog):
    """Ask for patient/session info and report options"""

    def __init__(self, info, prompt='Hello', parent=None):
        super(self.__class__, self).__init__()
        uifile = resource_filename('gaitutils', 'gui/pdf_report_dialog.ui')
        uic.loadUi(uifile, self)
        #self.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        self.prompt.setText(prompt)
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
        # get all the report page selections
        self.pages = dict()
        for w in self.findChildren(QtWidgets.QWidget):
            wname = w.objectName()
            if wname[:2] == 'cb':
                self.pages[wname[2:]] = w.checkState()
        if self.fullname and check_hetu(self.hetu):
            self.done(QtWidgets.QDialog.Accepted)  # or call superclass accept
        else:
            qt_message_dialog('Please enter a valid name and hetu')


class WebReportInfoDialog(QtWidgets.QDialog):
    """Ask for patient info"""

    def __init__(self, info, parent=None, check_info=True):
        super(self.__class__, self).__init__()
        uifile = resource_filename('gaitutils', 'gui/web_report_info.ui')
        uic.loadUi(uifile, self)
        #self.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        self.check_info = check_info
        if info is not None:
            if info['fullname'] is not None:
                self.lnFullName.setText(info['fullname'])
            if info['hetu'] is not None:
                self.lnHetu.setText(info['hetu'])
            if info['report_notes'] is not None:
                self.txtNotes.setPlainText(info['report_notes'])

    def accept(self):
        """ Update config and close dialog, if widget inputs are ok. Otherwise
        show an error dialog """
        self.hetu = self.lnHetu.text().strip()
        self.fullname = self.lnFullName.text().strip()
        self.report_notes = str(self.txtNotes.toPlainText()).strip()
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
    GaitMenu instance as a parent (uses _execute() and other parent methods)"""

    def __init__(self, parent):
        super(self.__class__, self).__init__(parent)
        self.parent = parent
        # load user interface made with designer
        uifile = resource_filename('gaitutils', 'gui/web_report_dialog.ui')
        uic.loadUi(uifile, self)
        self.btnCreateReport.clicked.connect(self._create_web_report)
        self.btnDeleteReport.clicked.connect(self._delete_current_report)
        self.btnDeleteAllReports.clicked.connect(self._delete_all_reports)
        self.btnViewReport.clicked.connect(self._view_current_report)
        # add double click action to browse current report
        (self.listActiveReports.itemDoubleClicked.
         connect(lambda item: self._browse_localhost(item.userdata)))
        # these require active reports to be enabled
        self.reportWidgets = [self.btnDeleteReport, self.btnDeleteAllReports,
                              self.btnViewReport]
        self._set_report_button_status()
        self._browser_procs = list()

    def _create_web_report(self):
        """Collect sessions, create the dash app, start it and launch a
        web browser on localhost on the correct port"""

        if self.listActiveReports.count() == cfg.web_report.max_reports:
            qt_message_dialog('Maximum number of active web reports active. '
                              'Please delete some reports first.')
            return

        dlg = ChooseSessionsDialog()
        if not dlg.exec_():
            return

        sessions = dlg.sessions
        report_name = report._report_name(sessions)
        existing_names = [item.text for item in self.listActiveReports.items]
        if report_name in existing_names:
            qt_message_dialog('There is already a report for %s' %
                              report_name)
            return

        session_infos, info = sessionutils._merge_session_info(sessions)
        if info is None:
            qt_message_dialog('Patient files do not match. Sessions may be '
                              'from different patients. Continuing without '
                              'patient info.')
            info = sessionutils.default_info()
        else:
            dlg_info = WebReportInfoDialog(info, check_info=False)
            if dlg_info.exec_():
                new_info = dict(hetu=dlg_info.hetu, fullname=dlg_info.fullname,
                                report_notes=dlg_info.report_notes)
                info.update(new_info)

                # update info files (except session specific keys)
                for session in sessions:
                    update_dict = dict(report_notes=dlg_info.report_notes,
                                       fullname=dlg_info.fullname,
                                       hetu=dlg_info.hetu)
                    session_infos[session].update(update_dict)
                    sessionutils.save_info(session, session_infos[session])
            else:
                return

        self.prog = ProgressBar('Creating web report...')
        self.prog.update('Collecting session information...', 0)
        signals = ProgressSignals()
        signals.progress.connect(lambda text, p: self.prog.update(text, p))

        # for comparison between sessions, get representative trials only
        tags = (cfg.eclipse.repr_tags if len(sessions) > 1 else
                cfg.eclipse.tags)

        # collect all video files for conversion
        # includes tagged dynamic, video-only tagged, and static trials
        vidfiles = list()
        for session in sessions:
            vids = _collect_session_videos(session, tags=tags)
            vidfiles.extend(vids)

        if not convert_videos(vidfiles, check_only=True):
            self.parent._convert_vidfiles(vidfiles, signals)

        # launch the report creation thread
        self.parent._execute(report.dash_report, thread=True, block_ui=True,
                             finished_func=self._web_report_finished,
                             result_func=self._web_report_ready,
                             info=info, sessions=sessions, tags=tags,
                             signals=signals)

    @property
    def active_reports(self):
        """Return number of active web reports"""
        return self.listActiveReports.count()

    def shutdown(self):
        """Try to shutdown browser processes and web servers"""
        for proc in self._browser_procs:
            proc.kill()
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
        self._browse_localhost(port)

    def _set_report_button_status(self):
        """Enable report buttons if reports exist, otherwise disable them"""
        n_reports = self.active_reports
        for widget in self.reportWidgets:
            widget.setEnabled(True if n_reports else False)

    def _web_report_finished(self):
        """Web report creation thread has finished"""
        self.prog.reset()  # closes the progress bar in case of errors
        self.parent._enable_op_buttons()

    def _web_report_ready(self, app):
        """Gets called when web report creation is successful. Open report in
        browser"""
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
        self.parent._execute(app.server.run, thread=True, block_ui=False,
                             debug=False, port=port, threaded=True)
        # double clicking on the list item will browse to corresponding port
        self.listActiveReports.add_item(app._gaitutils_report_name, data=port)
        # enable delete buttons etc.
        self._set_report_button_status()
        self._browse_localhost(port)

    def _browse_localhost(self, port):
        """Open configured browser on localhost:port"""
        url = '127.0.0.1:%d' % port
        try:
            proc = subprocess.Popen([cfg.general.browser_path, url])
            self._browser_procs.append(proc)
            logger.debug('new browser pid %d' % proc.pid)
        except Exception:
            qt_message_dialog('Cannot start configured web browser: %s'
                              % cfg.general.browser_path)


class Gaitmenu(QtWidgets.QMainWindow):

    def __init__(self):
        super(self.__class__, self).__init__()
        # load user interface made with designer
        uifile = resource_filename('gaitutils', 'gui/gaitmenu.ui')
        uic.loadUi(uifile, self)

        if not cfg.general.allow_multiple_menu_instances:
            sname = op.split(__file__)[1]
            nprocs = envutils._count_script_instances(sname)
            if nprocs >= 2:
                qt_message_dialog('Another instance of the menu seems to be '
                                  'running. Please use that instance or '
                                  'stop it before starting a new one.')
                sys.exit()

        if cfg.general.git_autoupdate:
            if envutils._git_autoupdate():
                qt_message_dialog('The package was automatically updated. '
                                  'Restarting...')
                os.execv(sys.executable, ['python'] + sys.argv)

        self._web_report_dialog = WebReportDialog(self)

        # modal dialogs etc. (simple signal->slot connection)
        self.actionCreate_PDF_report.triggered.connect(self._create_pdf_report)
        self.actionWeb_reports.triggered.connect(self._web_report_dialog.show)
        self.actionQuit.triggered.connect(self.close)
        self.actionOpts.triggered.connect(self._options_dialog)
        self.actionTardieu_analysis.triggered.connect(self._tardieu)
        self.actionAutoprocess_session.triggered.connect(self._autoproc_session)
        self.btnPlotNexusTrial.clicked.connect(self._plot_nexus_trial)
        self.btnPlotNexusSession.clicked.connect(self._plot_nexus_session)
        self.btnPlotNexusAverage.clicked.connect(self._plot_nexus_average)

        # consistency menu
        self._widget_connect_task(self.actionTrial_median_velocities,
                                  self._plot_trial_median_velocities)
        self._widget_connect_task(self.actionTrial_timedep_velocities,
                                  self._plot_trial_timedep_velocities)
        self._widget_connect_task(self.actionTime_distance_average,
                                  self._plot_timedist_average)
        
        # processing menu
        self._widget_connect_task(self.actionAutoprocess_single_trial,
                                  autoproc_trial,
                                  thread=True)
        self._widget_connect_task(self.actionAutomark_events,
                                  automark_trial,
                                  thread=True)
        self._widget_connect_task(self.actionRun_postprocessing_pipelines,
                                  self._postprocess_session)
        self._widget_connect_task(self.actionConvert_session_videos_to_web_format,
                                  self._convert_session_videos)
        self._widget_connect_task(self.actionCopy_session_videos_to_desktop,
                                  copy_session_videos)

        # set backend radio buttons according to choice in cfg
        self.rb_map = {'plotly': self.rbPlotly,
                       'matplotlib': self.rbMatplotlib}
        rb_active = self.rb_map[cfg.plot.backend]
        rb_active.setChecked(True)

        # add predefined plot layouts to combobox
        cb_items = sorted(cfg.layouts.menu_layouts.keys())
        self.cbNexusTrialLayout.addItems(cb_items)
        # set default option to PiG lower body (if it's on the list)
        try:
            default_index = cb_items.index('PiG lower body kinematics+'
                                           'kinetics')
        except ValueError:
            default_index = 0
        self.cbNexusTrialLayout.setCurrentIndex(default_index)

        XStream.stdout().messageWritten.connect(self._log_message)
        XStream.stderr().messageWritten.connect(self._log_message)
        logger.debug('interpreter: %s' % sys.executable)
        self.threadpool = QThreadPool()
        # we need a thread for each web server plus one worker thread
        self.threadpool.setMaxThreadCount(cfg.web_report.max_reports + 1)
        # keep refs to tardieu+mpl windows so they don't get garbage collected
        self._tardieuwin = None
        self._mpl_windows = list()

    def _get_plotting_backend_ui(self):
        """Return backend as selected in main menu"""
        for backend, rb in self.rb_map.items():
            if rb.isChecked():
                return backend

    def _autoproc_session(self):
        """Wrapper to run autoprocess for Nexus session"""
        try:
            sessionpath = nexus.get_sessionpath()
        except GaitDataError as e:
            _exception(e)
            return
        c3ds = sessionutils.get_c3ds(sessionpath, trial_type='DYNAMIC',
                                     check_if_exists=True)
        if c3ds:
            reply = qt_yesno_dialog('Some of the dynamic trials have been '
                                    'processed already. Are you sure you want '
                                    'to run autoprocessing?')
            if reply == QtWidgets.QMessageBox.NoRole:
                return

        self._execute(autoproc_session,
                      thread=True,
                      finished_func=self._enable_op_buttons)

    def _plot_timedist_average(self):
        """Plot time-distance average"""
        session = nexus.get_sessionpath()
        # we need to force backend here, since plotly is not yet supported
        result_func = lambda fig: self._show_plots(fig, backend='matplotlib')
        self._execute(do_session_average_plot, thread=True,
                      finished_func=self._enable_op_buttons,
                      result_func=result_func,
                      session=session)

    def _plot_trial_median_velocities(self):
        """Trial velocity plot from current Nexus session"""
        session = nexus.get_sessionpath()
        backend = self._get_plotting_backend_ui()
        self._execute(plot_trial_velocities, thread=True,
                      finished_func=self._enable_op_buttons,
                      result_func=self._show_plots,
                      session=session, backend=backend)

    def _plot_trial_timedep_velocities(self):
        """Trial velocity plot from current Nexus session"""
        session = nexus.get_sessionpath()
        backend = self._get_plotting_backend_ui()
        self._execute(plot_trial_timedep_velocities, thread=True,
                      finished_func=self._enable_op_buttons,
                      result_func=self._show_plots,
                      session=session, backend=backend)

    def _plot_nexus_average(self):
        """Plot average from current Nexus session"""
        lout_desc = self.cbNexusTrialLayout.currentText()
        lout_name = cfg.layouts.menu_layouts[lout_desc]
        backend = self._get_plotting_backend_ui()
        session = nexus.get_sessionpath()
        self._execute(plot_session_average, thread=True,
                      finished_func=self._enable_op_buttons,
                      result_func=self._show_plots,
                      session=session,
                      layout_name=lout_name, 
                      backend=backend)

    def _plot_nexus_trial(self):
        """Plot the current Nexus trial according to UI choices"""
        lout_desc = self.cbNexusTrialLayout.currentText()
        lout_name = cfg.layouts.menu_layouts[lout_desc]
        cycs = 'unnormalized' if self.xbPlotUnnorm.checkState() else None
        model_cycles = emg_cycles = cycs
        backend = self._get_plotting_backend_ui()
        from_c3d = self.xbPlotFromC3D.checkState()
        self._execute(plot_nexus_trial, thread=True,
                      finished_func=self._enable_op_buttons,
                      result_func=self._show_plots,
                      layout_name=lout_name, model_cycles=model_cycles,
                      emg_cycles=emg_cycles, from_c3d=from_c3d,
                      backend=backend)

    def _plot_nexus_session(self):
        """Plot the current Nexus session according to UI choices"""
        lout_desc = self.cbNexusTrialLayout.currentText()
        lout_name = cfg.layouts.menu_layouts[lout_desc]
        backend = self._get_plotting_backend_ui()
        sessions = [nexus.get_sessionpath()]
        cycs = 'unnormalized' if self.xbPlotUnnorm.checkState() else None
        model_cycles = emg_cycles = cycs
        self._execute(plot_sessions, thread=True,
                      finished_func=self._enable_op_buttons,
                      result_func=self._show_plots,
                      sessions=sessions,
                      style_by='context',
                      color_by='trial',
                      layout_name=lout_name, model_cycles=model_cycles,
                      emg_cycles=emg_cycles, backend=backend)

    def _show_plots(self, fig, backend=None):
        """Shows fig"""
        if backend is None:
            backend = self._get_plotting_backend_ui()
        if backend == 'matplotlib':
            _mpl_win = qt_matplotlib_window(fig)
            self._mpl_windows.append(_mpl_win)
        elif backend == 'plotly':
            plotly.offline.plot(fig)

    def _widget_connect_task(self, widget, fun, thread=False):
        """Helper to connect widget with task. Use lambda to consume unused
        events argument. If thread=True, launch in a separate worker thread."""
        # by default, just enable UI buttons when thread finishes
        finished_func = self._enable_op_buttons if thread else None
        if isinstance(widget, QtWidgets.QPushButton):
            sig = widget.clicked
        elif isinstance(widget, QtWidgets.QAction):
            sig = widget.triggered
        else:
            raise ValueError('Invalid widget type')
        sig.connect(lambda ev: self._execute(fun, thread=thread,
                                             finished_func=finished_func))

    def _convert_vidfiles(self, vidfiles, signals):
        """Convert given list of video files to web format. Uses non-blocking
        Popen() calls"""
        self._disable_op_buttons()
        procs = self._execute(convert_videos, thread=False,
                              block_ui=False, vidfiles=vidfiles)
        if not procs:
            return

        completed = False
        while not completed:
            n_complete = len([p for p in procs if p.poll() is not None])
            prog_txt = ('Converting videos: %d of %d files done'
                        % (n_complete, len(procs)))
            prog_p = 100 * n_complete / float(len(procs))
            signals.progress.emit(prog_txt, prog_p)
            time.sleep(.25)
            completed = n_complete == len(procs)
        self._enable_op_buttons()

    def _convert_session_videos(self):
        """Convert current Nexus session videos to web format."""
        try:
            session = nexus.get_sessionpath()
        except GaitDataError as e:
            qt_message_dialog(_exception_msg(e))
            return
        try:
            vidfiles = _collect_session_videos(session,
                                               tags=cfg.eclipse.tags)
        except GaitDataError as e:
            qt_message_dialog(_exception_msg(e))
            return
        if not vidfiles:
            qt_message_dialog('Cannot find any video files for session %s'
                              % session)
            return
        if convert_videos(vidfiles, check_only=True):
            qt_message_dialog('It looks like the session videos have already '
                              'been converted.')
            return
        prog = ProgressBar('')
        signals = ProgressSignals()
        signals.progress.connect(lambda text, p: prog.update(text, p))
        self._convert_vidfiles(vidfiles, signals)

    def _postprocess_session(self):
        """Run additional postprocessing pipelines for tagged trials"""
        try:
            session = nexus.get_sessionpath()
        except GaitDataError as e:
            qt_message_dialog(_exception_msg(e))
            return
        # XXX: run for tagged + static - maybe this should be configurable
        trials = sessionutils.get_c3ds(session, tags=cfg.eclipse.tags,
                                       trial_type='dynamic')
        trials += sessionutils.get_c3ds(session, trial_type='static')
        if trials and cfg.autoproc.postproc_pipelines:
            logger.debug('running postprocessing for %s' % trials)
            prog = ProgressBar('')
            vicon = nexus.viconnexus()
            prog.update('Running postprocessing pipelines: %s for %d '
                        'trials' % (cfg.autoproc.postproc_pipelines,
                                    len(trials)), 0)
            for k, tr in enumerate(trials):
                trbase = op.splitext(tr)[0]
                vicon.OpenTrial(trbase, cfg.autoproc.nexus_timeout)
                nexus.run_pipelines(vicon, cfg.autoproc.postproc_pipelines)
                prog.update('Running postprocessing pipelines: %s for %d '
                            'trials' % (cfg.autoproc.postproc_pipelines,
                                        len(trials)), 100*k/len(trials))
        elif not trials:
            qt_message_dialog('No trials in session to run postprocessing for')

    def closeEvent(self, event):
        """ Confirm and close application. """
        if self._web_report_dialog.active_reports:
            reply = qt_yesno_dialog('There are active web reports which '
                                    'will be closed. Are you sure you '
                                    'want to quit?')
            if reply == QtWidgets.QMessageBox.YesRole:
                self._web_report_dialog.shutdown()
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()

    def _options_dialog(self):
        """Show the options dialog"""
        dlg = OptionsDialog(self)
        dlg.exec_()

    def _create_pdf_report(self):
        """Create comparison or single session pdf report"""

        dlg = ChooseSessionsDialog()
        if not dlg.exec_():
            return
        sessions = dlg.sessions
        comparison = len(sessions) > 1
        if comparison:
            qt_message_dialog('PDF comparison report not supported right now')
            return

        session_infos, info = sessionutils._merge_session_info(sessions)
        if info is None:
            qt_message_dialog('Patient files do not match. Sessions may be '
                              'from different patients. Continuing without '
                              'patient info.')
            info = sessionutils.default_info()
        else:
            prompt_ = 'Please give additional subject information:'
            dlg_info = PdfReportDialog(info, prompt=prompt_)
            if not dlg_info.exec_():
                return
            new_info = dict(hetu=dlg_info.hetu, fullname=dlg_info.fullname,
                            report_notes=dlg_info.session_description)
            info.update(new_info)

            # update info files according to user input
            for session in sessions:
                update_dict = dict(fullname=dlg_info.fullname,
                                   hetu=dlg_info.hetu)
                session_infos[session].update(update_dict)
                sessionutils.save_info(session, session_infos[session])

        # create the report
        if comparison:
            self._execute(nexus_make_comparison_report.do_plot,
                          thread=True,
                          finished_func=self._enable_op_buttons,
                          sessions=sessions)
        else:
            self._execute(nexus_make_pdf_report.do_plot, thread=True,
                          finished_func=self._enable_op_buttons,
                          sessionpath=sessions[0], info=info,
                          pages=dlg_info.pages)

    def _log_message(self, msg):
        c = self.txtOutput.textCursor()
        c.movePosition(QtGui.QTextCursor.End)
        self.txtOutput.setTextCursor(c)
        self.txtOutput.insertPlainText(msg)
        self.txtOutput.ensureCursorVisible()


    def _disable_op_buttons(self):
        """ Disable all operation buttons """
        QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
        self.setEnabled(False)  # disables whole main window
        # update display immediately in case thread gets blocked
        QtWidgets.QApplication.processEvents()

    def _enable_op_buttons(self):
        """Enable all operation buttons and restore cursor."""
        QtWidgets.QApplication.restoreOverrideCursor()
        self.setEnabled(True)

    def _tardieu(self):
        """Open the Tardieu window if it is not currently open"""
        if self._tardieuwin is None or not self._tardieuwin.isVisible():
            self._tardieuwin = _tardieu.TardieuWindow()
            self._tardieuwin.show()

    def _execute(self, fun, thread=False, block_ui=True, finished_func=None,
                 result_func=None, **kwargs):
        """Run function fun with args kwargs. If thread==True, run in a
        separate worker thread. If block_ui==True, disable ui until worker
        thread is finished.
        If not thread:
        Returns function return value.
        If thread:
        finished_func will be called when thread is finished. result_func
        will be called with the function return value as its single argument,
        unless an exception is raised during thread execution."""
        fun_ = partial(fun, **kwargs)
        if block_ui:
            self._disable_op_buttons()
        if thread:
            self.runner = Runner(fun_)
            if finished_func:
                self.runner.signals.finished.connect(finished_func)
            if result_func:
                self.runner.signals.result.connect(lambda r: result_func(r))
            self.runner.signals.error.connect(lambda e: _exception(e))
            self.threadpool.start(self.runner)
        else:
            try:
                retval = fun_()
            except Exception as e:
                retval = None
                _exception(e)
            finally:
                if block_ui:
                    self._enable_op_buttons()
                return retval


class RunnerSignals(QObject):
    """Need a separate class since QRunnable cannot emit signals"""
    finished = pyqtSignal()
    result = pyqtSignal(object)
    error = pyqtSignal(Exception)


class Runner(QRunnable):
    """Encapsulates threaded functions for QThreadPool"""

    def __init__(self, fun):
        super(Runner, self).__init__()
        self.fun = fun
        self.signals = RunnerSignals()

    def run(self):
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
        qt_message_dialog('Oops! An unhandled exception was generated. '
                          'The application will be closed.\n\n %s' % tb_full)
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

    sys.excepthook = my_excepthook

    logger = logging.getLogger()
    handler = QtHandler()  # log to Qt logging widget
    # handler = logging.StreamHandler()   # log to sys.stdout

    handler.setFormatter(logging.
                         Formatter("%(name)s: %(levelname)s: %(message)s"))
    handler.setFormatter(logging.Formatter("%(name)s: %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)

    # quiet down some noisy loggers
    logging.getLogger('PyQt5.uic').setLevel(logging.WARNING)
    logging.getLogger('matplotlib.font_manager').setLevel(logging.WARNING)
    logging.getLogger('matplotlib.backends.backend_pdf').setLevel(logging.WARNING)
    logging.getLogger('werkzeug').setLevel(logging.WARNING)

    gaitmenu = Gaitmenu()
    gaitmenu.show()

    nexus_status = 'Vicon Nexus is %srunning' % ('' if nexus.pid() else 'not ')
    logger.debug(nexus_status)
    app.exec_()
