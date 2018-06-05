# -*- coding: utf-8 -*-
"""
Show a Qt menu for running various Nexus tasks.

@author: Jussi (jnu@iki.fi)
"""

from __future__ import print_function
from PyQt5 import QtGui, QtCore, uic, QtWidgets
from PyQt5.QtCore import QRunnable, QThreadPool, pyqtSignal, QObject
from pkg_resources import resource_filename
from functools import partial
import sys
import ast
import os.path as op
import os
import subprocess
import time

from gaitutils.numutils import check_hetu
from gaitutils.guiutils import (qt_message_dialog, qt_yesno_dialog,
                                qt_dir_chooser)
from gaitutils import (GaitDataError, nexus, cfg, report, nexus_emgplot,
                       nexus_musclelen_plot, nexus_kinetics_emgplot,
                       nexus_emg_consistency, nexus_kin_consistency,
                       nexus_musclelen_consistency, nexus_autoprocess_trial,
                       nexus_autoprocess_session, nexus_kinallplot,
                       nexus_tardieu, nexus_copy_trial_videos,
                       nexus_trials_velocity, nexus_make_pdf_report,
                       nexus_make_comparison_report, nexus_kin_average,
                       nexus_automark_trial, nexus_time_distance_vars,
                       sessionutils)

try:
    from gaitutils import nexus_customplot
    have_custom = True
except ImportError:
    have_custom = False
import logging

logger = logging.getLogger(__name__)


def _browse_localhost(port):
    """Open configured browser on localhost:port"""
    url = '127.0.0.1:%d' % port
    try:
        subprocess.Popen([cfg.general.browser_path, url])
    except Exception:
        qt_message_dialog('Cannot start configured web browser: %s'
                          % cfg.general.browser_path)


class PdfReportDialog(QtWidgets.QDialog):
    """Ask for patient/session info and report options"""

    def __init__(self, info, prompt='Hello', parent=None):
        super(self.__class__, self).__init__()
        uifile = resource_filename(__name__, 'pdf_report_dialog.ui')
        uic.loadUi(uifile, self)
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

    def __init__(self, info, parent=None):
        super(self.__class__, self).__init__()
        uifile = resource_filename(__name__, 'web_report_info.ui')
        uic.loadUi(uifile, self)
        if info is not None:
            if info['fullname'] is not None:
                self.lnFullName.setText(info['fullname'])
            if info['hetu'] is not None:
                self.lnHetu.setText(info['hetu'])
            if info['notes'] is not None:
                self.txtNotes.setPlainText(info['notes'])

    def accept(self):
        """ Update config and close dialog, if widget inputs are ok. Otherwise
        show an error dialog """
        self.hetu = self.lnHetu.text()
        self.fullname = self.lnFullName.text()
        self.notes = unicode(self.txtNotes.toPlainText()).strip()
        if self.fullname and check_hetu(self.hetu):
            self.done(QtWidgets.QDialog.Accepted)  # or call superclass accept
        else:
            qt_message_dialog('Please enter a valid name and hetu')


class ComparisonDialog(QtWidgets.QDialog):
    """ Display a dialog for the comparison report
    FIXME: adapt web report gui """

    def __init__(self):
        super(self.__class__, self).__init__()
        # load user interface made with designer
        uifile = resource_filename(__name__, 'comparison_dialog.ui')
        uic.loadUi(uifile, self)
        self.btnBrowseSession.clicked.connect(self.add_session)
        self.btnAddNexusSession.clicked.connect(lambda: self.
                                                add_session(from_nexus=True))
        self.btnClear.clicked.connect(self.clear_sessions)
        self.MAX_SESSIONS = 2  # FIXME: why only 2
        self.sessions = list()

    def add_session(self, from_nexus=False):
        if len(self.sessions) == self.MAX_SESSIONS:
            qt_message_dialog('You can specify maximum of %d sessions' %
                              self.MAX_SESSIONS)
            return
        if from_nexus:
            dir = nexus.get_sessionpath()
        else:
            dir = QtWidgets.QFileDialog.getExistingDirectory(self,
                                                             'Select session')
        if dir and dir not in self.sessions:
            self.sessions.append(dir)
            self.update_session_list()

    def clear_sessions(self):
        self.sessions = list()  # sorry no .clear()
        self.update_session_list()

    def update_session_list(self):
        self.lblSessions.setText(u'\n'.join(self.sessions))

    def accept(self):
        if len(self.sessions) < 2:
            qt_message_dialog('Please select at least 2 sessions to compare')
        else:
            self.done(QtWidgets.QDialog.Accepted)


class WebReportSessionsDialog(QtWidgets.QDialog):
    """ Display a dialog for creating the web report """

    def __init__(self):
        super(self.__class__, self).__init__()
        # load user interface made with designer
        uifile = resource_filename(__name__, 'web_report_sessions.ui')
        uic.loadUi(uifile, self)
        self.btnBrowseSession.clicked.connect(self.add_session)
        self.btnAddNexusSession.clicked.connect(lambda: self.
                                                add_session(from_nexus=True))
        self.btnClearAll.clicked.connect(self.listSessions.clear)
        self.btnClearCurrent.clicked.connect(self.listSessions.rm_current_item)
        self.MAX_SESSIONS = 3

    def add_session(self, from_nexus=False):
        if len(self.sessions) == self.MAX_SESSIONS:
            qt_message_dialog('You can specify maximum of %d sessions' %
                              self.MAX_SESSIONS)
            return
        if from_nexus:
            try:
                dirs = [nexus.get_sessionpath()]
            except GaitDataError as e:
                qt_message_dialog(str(e))
                return
        else:
            dirs = qt_dir_chooser()
        if dirs:
            for dir in dirs:
                if dir in self.sessions:
                    qt_message_dialog('Session %s already loaded' % dir)
                else:
                    self.listSessions.add_item(dir, data=dir)

    @property
    def sessions(self):
        return [item.userdata for item in self.listSessions.items]

    def accept(self):
        if not self.sessions:
            qt_message_dialog('Please select at least one session')
        else:
            self.done(QtWidgets.QDialog.Accepted)


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
            sys.stdout = XStream._stdout  # also capture stdout
        return XStream._stdout

    @staticmethod
    def stderr():
        if not XStream._stderr:
            XStream._stderr = XStream()
            sys.stderr = XStream._stderr  # ... and stderr
        return XStream._stderr


class OptionsDialog(QtWidgets.QDialog):
    """ Display a tabbed dialog for changing gaitutils options """

    def __init__(self, default_tab=0):
        super(self.__class__, self).__init__()
        # load user interface made with designer
        uifile = resource_filename(__name__, 'options_dialog.ui')
        uic.loadUi(uifile, self)

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
        self.homedir = os.path.expanduser('~')

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


class Gaitmenu(QtWidgets.QMainWindow):

    def __init__(self):
        super(self.__class__, self).__init__()
        # load user interface made with designer
        uifile = resource_filename(__name__, 'nexus_menu.ui')
        uic.loadUi(uifile, self)
        """ Stuff that shows matplotlib plots cannot be run in directly in
        worker threads. To put plotting stuff into a worker thread, need to:
        -make the plotting function return a figure (and not invoke the qt
        event loop)
        -put the plotting function into a worker thread
        -call plotting function
        -create a qt dialog and canvas in GUI thread
        -draw resulting figure onto canvas
        So far this has not been done since the plotting functions return
        rather quickly.
        Running the plotting functions directly from the GUI thread is also a
        bit ugly since the Qt event loop gets called twice, but this does not
        seem to do any harm.
        """
        self._button_connect_task(self.btnCopyVideos,
                                  nexus_copy_trial_videos.do_copy, thread=True)
        self._button_connect_task(self.btnEMG, nexus_emgplot.do_plot)
        self._button_connect_task(self.btnMuscleLen,
                                  nexus_musclelen_plot.do_plot)
        self._button_connect_task(self.btnKinEMG,
                                  nexus_kinetics_emgplot.do_plot)
        self._button_connect_task(self.btnKinall, nexus_kinallplot.do_plot)
        self._button_connect_task(self.btnTardieu, self._tardieu)

        if have_custom:
            self._button_connect_task(self.btnCustom, nexus_customplot.do_plot)
        else:
            self.btnCustom.clicked.connect(self._no_custom)

        self._button_connect_task(self.btnTrialVelocity,
                                  nexus_trials_velocity.do_plot)
        self._button_connect_task(self.btnEMGCons,
                                  nexus_emg_consistency.do_plot)
        self._button_connect_task(self.btnKinCons,
                                  nexus_kin_consistency.do_plot)
        self._button_connect_task(self.btnMuscleLenCons,
                                  nexus_musclelen_consistency.do_plot)
        self._button_connect_task(self.btnKinAverage,
                                  nexus_kin_average.do_plot)
        self._button_connect_task(self.btnTimeDistAverage,
                                  nexus_time_distance_vars.
                                  do_session_average_plot)
        # these take a long time and do not use matplotlib, so thread them
        self._button_connect_task(self.btnAutoprocTrial,
                                  nexus_autoprocess_trial.autoproc_single,
                                  thread=True)
        self._button_connect_task(self.btnAutoprocSession,
                                  nexus_autoprocess_session.autoproc_session,
                                  thread=True)
        self._button_connect_task(self.btnAutomark,
                                  nexus_automark_trial.automark_single)

        self.btnConvertVideos.clicked.connect(self._convert_session_videos)
        self.btnCreatePDFs.clicked.connect(self._create_pdf_report)
        self.btnCreateComparison.clicked.connect(self._create_comparison)
        self.btnCreateWebReport.clicked.connect(self._create_web_report)
        self.btnOptions.clicked.connect(self._options_dialog)
        self.btnQuit.clicked.connect(self.close)
        (self.listActiveReports.itemDoubleClicked.
         connect(lambda item: _browse_localhost(item.userdata)))

        # collect operation widgets
        self.opWidgets = list()
        for widget in self.__dict__:
            if ((widget[:3] == 'btn' or widget[:4] == 'rbtn') and
               widget != 'btnQuit'):
                self.opWidgets.append(widget)


        XStream.stdout().messageWritten.connect(self._log_message)
        XStream.stderr().messageWritten.connect(self._log_message)

        self.threadpool = QThreadPool()
        logger.debug('started threadpool with max %d threads' %
                     self.threadpool.maxThreadCount())

    def _button_connect_task(self, button, fun, thread=False):
        """ Helper to connect button with task function. Use lambda to consume
        unused events argument. If thread=True, launch in a separate worker
        thread. """
        button.clicked.connect(lambda ev: self._execute(fun, thread=thread))

    def _convert_vidfiles(self, vidfiles):
        """Convert given list of video files to web format. Uses non-blocking
        Popen() calls"""
        self._disable_op_buttons()
        prog = QtWidgets.QProgressDialog()
        prog.setWindowTitle('Converting videos...')
        prog.setCancelButton(None)
        prog.setMinimum(0)
        prog.setMaximum(100)
        prog.setGeometry(500, 300, 500, 100)
        prog.show()
        QtWidgets.QApplication.processEvents()
        procs = self._execute(report.convert_videos, thread=False,
                              block_ui=False, vidfiles=vidfiles)
        completed = False
        while not completed:
            n_complete = len([p for p in procs if p.poll() is not None])
            prog.setLabelText('%d of %d files done' % (n_complete,
                                                       len(procs)))
            prog.setValue(100*n_complete/float(len(procs)))
            QtWidgets.QApplication.processEvents()
            time.sleep(.25)
            completed = n_complete == len(procs)
        prog.hide()
        self._enable_op_buttons()

    def _convert_session_videos(self):
        """Convert current Nexus session videos to web format. Converts
        representative and static trial videos"""
        try:
            session = nexus.get_sessionpath()
        except GaitDataError as e:
            qt_message_dialog(str(e))
            return
        tags = cfg.plot.eclipse_tags
        tagged = sessionutils.find_tagged(session, tags=tags)
        vidfiles = []
        for c3dfile in tagged:
            vidfiles.extend(nexus.find_trial_videos(c3dfile))
        static_c3ds = sessionutils.find_tagged(session, ['Static'], ['TYPE'])
        if static_c3ds:
            vidfiles.extend(nexus.find_trial_videos(static_c3ds[-1]))
        if not vidfiles:
            qt_message_dialog('Cannot find any video files for session %s')
            return
        if report.convert_videos(vidfiles, check_only=True):
            qt_message_dialog('It looks like the session videos have already '
                              'been converted.')
            return
        self._convert_vidfiles(vidfiles)

    def closeEvent(self, event):
        """ Confirm and close application. """
        if self.listActiveReports.count():
            reply = qt_yesno_dialog('There are active processes which '
                                    'will be terminated. Are you sure you '
                                    'want to quit?')
            if reply == QtWidgets.QMessageBox.YesRole:
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()

    def _options_dialog(self):
        """ Show the autoprocessing options dialog """
        dlg = OptionsDialog()
        dlg.exec_()

    def _create_comparison(self):
        dlg = ComparisonDialog()
        if dlg.exec_():
            self._sessions = dlg.sessions
            self._execute(nexus_make_comparison_report.do_plot,
                          sessions=dlg.sessions)

    def _create_web_report(self):
        """Collect sessions, create the dash app, start it and launch a
        web browser on localhost on the correct port"""

        dlg = WebReportSessionsDialog()
        if not dlg.exec_():
            return
        sessions = dlg.sessions

        session_infos, info = sessionutils._merge_session_info(sessions)
        if info is None:
            qt_message_dialog('Patient info does not match. Sessions may be '
                              'from different patients. Continuing without '
                              'patient info.')
            info = sessionutils.default_info()

        else:
            # get updated info from user
            dlg_info = WebReportInfoDialog(info)
            if dlg_info.exec_():
                new_info = dict(hetu=dlg_info.hetu, fullname=dlg_info.fullname,
                                notes=dlg_info.notes)
                info.update(new_info)

                # update the notes field into each session (other session data
                # should match and will not be updated)
                for session in sessions:
                    update_dict = dict(notes=dlg_info.notes,
                                       fullname=dlg_info.fullname,
                                       hetu=dlg_info.hetu)
                    session_infos[session].update(update_dict)
                    sessionutils.save_info(session, session_infos[session])
            else:
                return

        # for comparison between sessions, get representative trials only
        tags = (cfg.plot.eclipse_repr_tags if len(sessions) > 1 else
                cfg.plot.eclipse_tags)

        # collect all video files for conversion
        vidfiles = list()
        for session in sessions:
            tagged = sessionutils.find_tagged(session, tags=tags)
            for c3dfile in tagged:
                vidfiles.extend(nexus.find_trial_videos(c3dfile))
            static_c3ds = sessionutils.find_tagged(session, ['Static'],
                                                   ['TYPE'])
            if static_c3ds:
                vidfiles.extend(nexus.find_trial_videos(static_c3ds[-1]))

        if not report.convert_videos(vidfiles, check_only=True):
            self._convert_vidfiles(vidfiles)

        logger.debug('Creating web report...')
        app = self._execute(report.dash_report, info=info, sessions=sessions,
                            tags=tags)
        if app is None:
            qt_message_dialog('Could not create report, check that session is '
                              'valid')
            return

        # report ok - start server, thread and do not block ui
        port = 5000 + self.listActiveReports.count()
        self._execute(app.server.run, thread=True, block_ui=False,
                      debug=False, port=port)
        sessions_str = '/'.join([op.split(s)[-1] for s in dlg.sessions])
        report_type = ('single session' if len(dlg.sessions) == 1
                       else 'comparison')
        report_name = 'localhost:%d: %s, %s' % (port, report_type,
                                                sessions_str)
        # double clicking on the list item will browse to corresponding port
        self.listActiveReports.add_item(report_name, data=port)
        logger.debug('starting web browser')
        _browse_localhost(port)

    def _create_pdf_report(self):
        """Creates the full pdf report"""
        try:
            subj = nexus.get_subjectnames()
        except GaitDataError as e:
            qt_message_dialog(str(e))
            return

        # ask for patient info, update saved info accordingly
        session = nexus.get_sessionpath()
        info = sessionutils.load_info(session) or sessionutils.default_info()
        prompt_ = 'Please give additional subject information for %s:' % subj
        dlg = PdfReportDialog(info, prompt=prompt_)
        if dlg.exec_():
            new_info = dict(hetu=dlg.hetu, fullname=dlg.fullname,
                            session_description=dlg.session_description)
            self._execute(nexus_make_pdf_report.do_plot, thread=True,
                          fullname=dlg.fullname, hetu=dlg.hetu,
                          session_description=dlg.session_description,
                          pages=dlg.pages)
            info.update(new_info)
            sessionutils.save_info(session, info)

    def _log_message(self, msg):
        c = self.txtOutput.textCursor()
        c.movePosition(QtGui.QTextCursor.End)
        self.txtOutput.setTextCursor(c)
        self.txtOutput.insertPlainText(msg)
        self.txtOutput.ensureCursorVisible()

    def _no_custom(self):
        qt_message_dialog('No custom plot defined. Please create '
                          'nexus_scripts/nexus_customplot.py')

    def _exception(self, e):
        logger.debug('caught exception while running task')
        qt_message_dialog(str(e))

    def _disable_op_buttons(self):
        """ Disable all operation buttons """
        QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
        for widget in self.opWidgets:
            self.__dict__[widget].setEnabled(False)
        # update display immediately in case thread gets blocked
        QtWidgets.QApplication.processEvents()

    def _enable_op_buttons(self):
        """ Enable all operation buttons """
        for widget in self.opWidgets:
            self.__dict__[widget].setEnabled(True)
        QtWidgets.QApplication.restoreOverrideCursor()

    def _tardieu(self):
        win = nexus_tardieu.TardieuWindow()
        win.show()

    def _execute(self, fun, thread=False, block_ui=True, **kwargs):
        """ Run function fun. If thread==True, run it in a separate worker
        thread. If block_ui, disable the ui until worker thread is finished
        (except for messages!) Returns function return value if not threaded.
        kwargs are passed to function
        """
        fun_ = partial(fun, **kwargs)
        if block_ui:
            self._disable_op_buttons()
        if thread:
            self.runner = Runner(fun_)
            if block_ui:
                self.runner.signals.finished.connect(self._enable_op_buttons)
            self.runner.signals.error.connect(lambda e: self._exception(e))
            self.threadpool.start(self.runner)
            retval = None
        else:
            try:
                retval = fun_()
            except Exception as e:
                retval = None
                self._exception(e)
            finally:
                if block_ui:
                    self._enable_op_buttons()
        return retval


class RunnerSignals(QObject):
    """Need a separate class since QRunnable cannot emit signals"""
    finished = pyqtSignal()
    error = pyqtSignal(Exception)


class Runner(QRunnable):
    """Encapsulates threaded functions for QThreadPool"""
    def __init__(self, fun):
        super(Runner, self).__init__()
        self.fun = fun
        self.signals = RunnerSignals()

    def run(self):
        try:
            self.fun()
        except Exception as e:
            self.signals.error.emit(e)
        finally:
            self.signals.finished.emit()


def main():

    app = QtWidgets.QApplication(sys.argv)

    logger = logging.getLogger()
    handler = QtHandler()  # log to Qt logging widget
    # handler = logging.StreamHandler()   # log to sys.stdout

    handler.setFormatter(logging.
                         Formatter("%(name)s: %(levelname)s: %(message)s"))
    handler.setFormatter(logging.Formatter("%(name)s: %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)

    # uiparser logger makes too much noise
    logging.getLogger('PyQt5.uic').setLevel(logging.WARNING)

    gaitmenu = Gaitmenu()
    gaitmenu.show()

    nexus_status = 'Vicon Nexus is %srunning' % ('' if nexus.pid() else 'not ')
    logger.debug(nexus_status)
    app.exec_()


if __name__ == '__main__':
    main()
