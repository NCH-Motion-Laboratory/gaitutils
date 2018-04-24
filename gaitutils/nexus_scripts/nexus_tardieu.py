# -*- coding: utf-8 -*-
"""
Interactive script for analysis of Tardieu trials.
matplotlib + Qt5

TODO:

    filter behaves weirdly when hp is set at 0 Hz
    filter crash when lp is set at 1000 Hz
    no narrow view

    params to config
    EMG scale box is not updated when scaling w/ toolbar tool
    add statusbar?


@author: Jussi (jnu@iki.fi)
"""

from __future__ import print_function
from collections import OrderedDict
import matplotlib
from matplotlib.figure import Figure
import matplotlib.gridspec as gridspec
import logging
import sys
import numpy as np
import copy
from pkg_resources import resource_filename
from PyQt5 import QtGui, QtWidgets, uic, QtCore
from matplotlib.backends.backend_qt5agg import (FigureCanvasQTAgg,
                                                NavigationToolbar2QT)
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
from gaitutils import (EMG, nexus, cfg, read_data, trial, eclipse, models,
                       Trial, Plotter, layouts, utils, GaitDataError,
                       register_gui_exception_handler)
from gaitutils.numutils import segment_angles, rms
from gaitutils.guiutils import qt_message_dialog, qt_yesno_dialog


matplotlib.style.use(cfg.plot.mpl_style)

logger = logging.getLogger(__name__)


def read_nexus_starting_angle():
    """Read the Nexus defined starting angle"""
    subjname = nexus.get_subjectnames()
    vicon = nexus.viconnexus()
    asp = vicon.GetSubjectParam(subjname, 'AnkleStartPos')
    return asp[0] if asp[1] else None


class LoadDialog(QtWidgets.QDialog):
    """ Dialog for loading data """

    def __init__(self):

        super(self.__class__, self).__init__()
        uifile = resource_filename(__name__, 'tardieu_load_dialog.ui')
        uic.loadUi(uifile, self)
        try:
            ang0_nexus = read_nexus_starting_angle()
        except GaitDataError:
            ang0_nexus = None
        self.spNormAngle.setValue(ang0_nexus if ang0_nexus else 90)


class EMGFilterDialog(QtWidgets.QDialog):
    """ Dialog for setting the EMG filter """

    def __init__(self, emg_passband):

        super(self.__class__, self).__init__()
        uifile = resource_filename(__name__, 'tardieu_filter_dialog.ui')
        uic.loadUi(uifile, self)
        self.spEMGLow.setValue(emg_passband[0])
        self.spEMGHigh.setValue(emg_passband[1])


class HelpDialog(QtWidgets.QDialog):
    """ Dialog for help"""

    def __init__(self):

        super(self.__class__, self).__init__()
        uifile = resource_filename(__name__, 'tardieu_help_dialog.ui')
        uic.loadUi(uifile, self)


class SimpleToolbar(NavigationToolbar2QT):
    """ Simplified mpl navigation toolbar with some items removed """

    toolitems = [t for t in NavigationToolbar2QT.toolitems if
                 t[0] in ('Pan', 'Zoom')]


class TardieuWindow(QtWidgets.QMainWindow):
    """ Main Qt window with controls. The mpl figure containing the actual data
    is created by a separate class and embedded into this window. """

    def __init__(self, parent=None):

        super(TardieuWindow, self).__init__(parent)

        uifile = resource_filename(__name__, 'tardieu.ui')
        uic.loadUi(uifile, self)

        self._tardieu_plot = TardieuPlot()
        # set the internal callbacks to point to our methods
        self._tardieu_plot._update_marker_status = self._update_marker_status
        self._tardieu_plot._update_status = self._update_status
        self.canvas = FigureCanvasQTAgg(self._tardieu_plot.fig)
        self.canvas.setSizePolicy(QtWidgets.QSizePolicy.Expanding,
                                  QtWidgets.QSizePolicy.Expanding)
        self.canvas.setParent(self)  # ?
        self.canvas.setFocusPolicy(QtCore.Qt.ClickFocus)
        self.canvas.show()

        self.btnClearMarkers.clicked.connect(self._clear_markers)
        self.btnSaveFig.clicked.connect(self._save_plot)
        self.btnZoomFast.clicked.connect(self._xzoom_to_fast)
        self.btnZoomReset.clicked.connect(self._xzoom_reset)

        self.spEMGYScale.valueChanged.connect(self._rescale_emg)
        self.btnSetEMGFilter.clicked.connect(self._emg_filter_dialog)

        self.emg_passband = cfg.emg.passband
        self.lblEMGPassband.setText('%.1f Hz - %.1f Hz' %
                                    (self.emg_passband[0],
                                     self.emg_passband[1]))

        # keep some controls disabled until data is loaded
        self._set_data_controls(False)
        self.btnQuit.clicked.connect(self.close)

        # no focus on buttons - need to keep focus on canvas for mpl events
        for w in self.findChildren(QtWidgets.QWidget):
            wname = unicode(w.objectName())
            if wname[:3] in ['btn']:
                w.setFocusPolicy(QtCore.Qt.NoFocus)

        self.actionQuit.triggered.connect(self.close)
        self.actionHelp.triggered.connect(self._help_dialog)
        self.actionOpen.triggered.connect(self._load_dialog_nexus)
        self.actionOpenC3D.triggered.connect(self._load_dialog_c3d)

        """
        # add the narrow view button?
        """
        self.lblStatus.setText('No data loaded')
        self.lblMarkerStatus.setText('No markers')

        # self.setStyleSheet("background-color: white;");
        # add canvas into last column, span all rows
        self.mainGridLayout.addWidget(self.canvas, 1,
                                      self.mainGridLayout.columnCount(),
                                      self.mainGridLayout.rowCount()-1, 1)

        # create toolbar and add it into last column, 1st row
        self.toolbar = SimpleToolbar(self.canvas, self)
        self._tardieu_plot._toolbar = self.toolbar
        self.mainGridLayout.addWidget(self.toolbar, 0,
                                      self.mainGridLayout.columnCount()-1,
                                      1, 1)
        self.canvas.setFocus()
        self.canvas.draw()

    def _xzoom_to_fast(self):
        self._tardieu_plot._xzoom_to_fast()
        self.canvas.draw()

    def _xzoom_reset(self):
        self._tardieu_plot._xzoom_reset()
        self.canvas.draw()

    def _reset_emg_filter(self, f1, f2):
        """Re-set the EMG filter"""
        self.emg_passband = [f1, f2]
        self.lblEMGPassband.setText('%.1f Hz - %.1f Hz' % (f1, f2))
        self._tardieu_plot._reset_emg_filter(f1, f2)
        self.canvas.draw()

    def _rescale_emg(self):
        """Callback for EMG rescaling"""
        yscale = self.spEMGYScale.value()
        self._tardieu_plot._rescale_emg(yscale)
        self.canvas.draw()
        self.canvas.setFocus()

    def _set_data_controls(self, enabled):
        """Show data related controls as (non)-responsive according to
        enabled (bool)"""
        for w in [self.btnSaveFig, self.spEMGYScale, self.btnClearMarkers,
                  self.btnSetEMGFilter, self.btnZoomFast, self.btnZoomReset]:
            w.setEnabled(enabled)

    def _nonresp(self):
        """Show whole window as non-responsive"""
        for w in self.findChildren(QtWidgets.QWidget):
            wname = unicode(w.objectName())
            if wname[:2] in ['bt', 'me', 'sp']:  # catch buttons, menus, spins
                w.setEnabled(False)
        # update display immediately in case thread gets blocked
        QtWidgets.QApplication.processEvents()
        QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)

    def _resp(self):
        """Show whole window as responsive"""
        for w in self.findChildren(QtWidgets.QWidget):
            wname = unicode(w.objectName())
            if wname[:2] in ['bt', 'me', 'sp']:
                w.setEnabled(True)
        QtWidgets.QApplication.restoreOverrideCursor()

    def _help_dialog(self):
        dlg = HelpDialog()
        dlg.exec_()

    def _load_dialog_nexus(self):
        """Dialog for loading from Nexus"""
        try:
            vicon = nexus.viconnexus()
        except GaitDataError as e:
            qt_message_dialog('Error: %s' % str(e))
            return
        self._load_dialog(vicon)

    def _load_dialog_c3d(self):
        """Dialog for loading from c3d"""
        fout = QtWidgets.QFileDialog.getOpenFileName(self, 'Open C3D file',
                                                     '',
                                                     u'C3D files (*.c3d)')[0]
        if fout:
            self._load_dialog(fout)

    def _emg_filter_dialog(self):
        dlg = EMGFilterDialog(self.emg_passband)
        if not dlg.exec_():
            return
        else:
            self._reset_emg_filter(dlg.spEMGLow.value(), dlg.spEMGHigh.value())

    def _load_dialog(self, source):
        """Dialog for loading data """
        dlg = LoadDialog()
        if not dlg.exec_():
            return
        side = 'R' if dlg.rbRight.isChecked() else 'L'
        # prepend side to configured EMG channel names
        emg_chs = [side+ch for ch in cfg.tardieu.emg_chs]
        ang0_nexus = dlg.spNormAngle.value()

        self._nonresp()
        try:
            self._tardieu_plot.load_data(source, emg_chs, self.emg_passband,
                                         ang0_nexus)
        except GaitDataError as e:
            qt_message_dialog('Error: %s' % str(e))
            self._resp()
            return

        self._tardieu_plot.plot_data()
        self.canvas.draw()
        self.canvas.setFocus()
        self._update_status()
        self._update_marker_status()
        # set data controls to match what was loaded
        self.spEMGYScale.setValue(cfg.plot.emg_yscale*1e3)  # mV
        # enable all controls
        self._resp()
        self._set_data_controls(True)

    def _save_plot(self):
        """Save a pdf report"""
        fn_pdf = self._tardieu_plot.trial.trialname + '.pdf'
        fname = QtWidgets.QFileDialog.getSaveFileName(self, 'Save plot',
                                                      fn_pdf,
                                                      u'PDF files (*pdf)')[0]
        if not fname:
            return
        try:
            with PdfPages(fname) as pdf:
                page_size = (11.69, 8.27)
                # create header page
                #timestr = time.strftime("%d.%m.%Y")
                fig_hdr = Figure()
                FigureCanvas(fig_hdr)
                ax = fig_hdr.add_subplot(111)
                ax.set_axis_off()
                txt = self._tardieu_plot.status_text
                ax.text(.5, .8, txt, ha='center', va='center', weight='bold',
                        fontsize=12)
                fig_hdr.set_size_inches(page_size[0], page_size[1])
                pdf.savefig(fig_hdr)
                figx, data_axes, legend_ax = self._tardieu_plot.plot_data(interactive=False,
                                                                          emg_yscale=self.spEMGYScale.value())
                FigureCanvas(figx)
                figx.set_size_inches(page_size[0], page_size[1])
                # full view
                self._tardieu_plot.markers.plot_on_axes(data_axes)
                self._tardieu_plot.markers.legend(legend_ax)
                pdf.savefig(figx)
                # create zoomed version
                fast_rng = self._tardieu_plot._get_fast_movement()
                for ax in data_axes:
                    ax.set_xlim(fast_rng[0], fast_rng[1])
                pdf.savefig(figx)
        except IOError:
            qt_message_dialog('Error writing %s, '
                              'check that file is not already open.' % fname)
            return

    def _update_status(self):
        """Update the status text"""
        status = self._tardieu_plot.status_text
        self.lblStatus.setText(status)

    def _update_marker_status(self):
        """Update the marker status text"""
        status = self._tardieu_plot.marker_status_text
        self.lblMarkerStatus.setText(status)

    def _clear_markers(self):
        """Clear all markers"""
        if self._tardieu_plot.markers is not None:
            self._tardieu_plot.markers.clear()
            self.canvas.draw()
            self._update_marker_status()

    def closeEvent(self, event):
        """Confirm and close application"""
        reply = qt_yesno_dialog('Are you sure?')
        if reply == QtWidgets.QMessageBox.YesRole:
            event.accept()
        else:
            event.ignore()


class Markers(object):
    """ Manage vertical marker lines at multiple axes.
    The markers are created as matplotlib axvline()s. """

    def __init__(self, marker_colors, marker_width, axes):
        """ Initialize.
        marker_colors: the colors (and max. number) of markers
        marker_width: the line width for the markers
        axes: all axes to put the markers in """
        self._markers = OrderedDict()  # markers are keyed by x coordinate
        self._axes = axes
        self.marker_colors = marker_colors
        self.marker_width = marker_width
        self.max_markers = len(self.marker_colors)

    def add_on_click(self, x):
        """Add a marker on mouse click"""
        if x not in self._markers.keys():
            if len(self._markers) == self.max_markers:
                qt_message_dialog('You can place a maximum of %d markers' %
                                  self.max_markers)
            else:
                self.add(x)

    def add(self, x, annotation=''):
        """Add a marker at point x with optional annotation"""
        if x in self._markers.keys():  # marker already exists here
            return
        else:
            cols_in_use = [m['color'] for m in self._markers.values()]
            col = list((set(self.marker_colors) - set(cols_in_use)))[0]
            self._markers[x] = dict()
            self._markers[x]['annotation'] = annotation
            self._markers[x]['color'] = col
            # each axis gets its own line artist
            for ax in self._axes:
                self._markers[x][ax] = ax.axvline(x=x, color=col,
                                                  linewidth=self.marker_width)
                # generate picker events at given tolerance
                self._markers[x][ax].set_picker(3)

    def delete(self, x):
        """Delete marker by location"""
        for ax in self._axes:
            self._markers[x][ax].remove()
        self._markers.pop(x)

    def delete_artist(self, artist, ax):
        """Delete marker by artist at axis ax"""
        # need to find the marker that has the corresponding artist
        for x, m in self._markers.items():
            if m[ax] == artist:
                self.delete(x)
                return

    def clear(self):
        """Remove all markers"""
        for marker in self._markers:
            self.delete(marker)

    def plot_on_axes(self, axes):
        """Plot all markers on given axes (iterable)"""
        for ax in axes:
            for x, m in self._markers.items():
                ax.axvline(x=x, color=m['color'], linewidth=self.marker_width)

    def legend(self, ax, ncol=2):
        """Create legend"""
        artists = list()
        legtxts = list()
        for mkr, anno, col in self.marker_info:
            artists.append(matplotlib.lines.Line2D((0, 1), (0, 0),
                                                   linewidth=self.marker_width,
                                                   color=col))
            legtxts.append(u'%.3f s: %s' % (mkr, anno))
        ax.legend(artists, legtxts, loc='upper left', ncol=ncol,
                  prop={'size': cfg.plot.label_fontsize})

    @property
    def marker_info(self):
        """Return tuple of marker, annotation, and color"""
        annotations = [m['annotation'] for m in self._markers.values()]
        cols_in_use = [m['color'] for m in self._markers.values()]
        return zip(self._markers.keys(), annotations, cols_in_use)


class TardieuPlot(object):
    """ Create matplotlib graphs for Tardieu analysis """

    def __init__(self):
        """Initialize but do not plot anything yet"""
        # adjustable params
        # TODO: some could go into config
        self.marker_button = 1  # mouse button for placing markers
        self.marker_del_button = 3  # remove marker
        self.marker_key = 'shift'  # modifier key for markers
        self.markers = None
        # FIXME: check colors
        self.marker_colors = ['orange', 'green', 'red', 'brown',
                              'gray', 'purple']
        self.marker_width = 1.5
        self.width_ratio = [1, 5]
        self.text_fontsize = 9
        self.margin = .025  # margin at edge of plots
        self.margin = 0
        self.narrow = False
        self.hspace = .4
        self.wspace = .5
        self.emg_automark_chs = ['Gas', 'Sol']   # FIXME: into config?
        self.data_axes = list()  # axes that actually contain data
        self.emg_axes = list()
        # these are callbacks that should be registered by the creator
        self._update_marker_status = None
        self._update_status = None
        self.fig = Figure()

    def load_data(self, source, emg_chs, emg_passband, ang0_nexus):
        """Load the Tardieu data.
        emg_chs: list of EMG channel names to use

        Returns True on successful data load, False otherwise
        """

        self.trial = Trial(source)
        self.trial.emg.passband = emg_passband

        # the 'true' physiological starting angle (given as a param)
        self.ang0_nexus = ang0_nexus
        self.emg_chs = emg_chs
        self.time = self.trial.t / self.trial.framerate  # time axis in sec
        self.tmax = self.time[-1]
        self.nframes = len(self.time)

        # read EMG data
        self.emgdata = dict()
        self.emg_rms = dict()
        for ch in self.emg_chs:
            t_, self.emgdata[ch] = self.trial[ch]
            self.emg_rms[ch] = rms(self.emgdata[ch], cfg.emg.rms_win)

        if cfg.tardieu.acc_chs:
            accdata_ = self.trial.accelerometer_data['data']
            # compute vector sum over given accelerometer chs
            try:
                accsigs = [accdata_[ch] for ch in cfg.tardieu.acc_chs]
            except KeyError:
                raise GaitDataError('No such accelerometer channel %s' % ch)
            acctot = np.stack(accsigs)
            self.acctot = np.sqrt(np.sum(acctot**2, 0))
        else:
            self.acctot = None

        # FIXME: self.time?
        self.time_analog = t_ / self.trial.analograte

        # read marker data and compute segment angle
        mnames = cfg.tardieu.marker_names
        data = read_data.get_marker_data(source, mnames)

        P0 = data[mnames[0]+'_P']
        P1 = data[mnames[1]+'_P']
        P2 = data[mnames[2]+'_P']
        # stack so that marker changes along 2nd dim for segment_angles
        Pall = np.stack([P0, P1, P2], axis=1)
        # compute segment angles (deg)
        self.angd = segment_angles(Pall) / np.pi * 180
        # this is our calculated starting angle
        ang0_our = np.median(self.angd[~np.isnan(self.angd)][:10])
        # normalize: plantarflexion negative, our starting angle equals
        # the starting angle given in Nexus (i.e. if ang0_nexus is 95,
        # we offset the data to start at -5 deg)
        # if starting angle is not specified in Nexus, it defaults to 90 deg
        self.angd = 90 - self.ang0_nexus - self.angd + ang0_our
        return True

    def plot_data(self, interactive=True, emg_yscale=None):
        """ Plot the data. Can plot either on the main (interactive) display
        or a new mpl Figure() (which will be returned)"""

        fig = self.fig if interactive else Figure()
        fig.clear()
        data_axes = list()
        if interactive:  # save trace objects for later modification by GUI
            self.emg_traces, self.rms_traces = dict(), dict()

        nrows = len(self.emg_chs) + 3   # emgs + acc + marker data
        if self.acctot is not None:
            nrows += 1

        # add one row for legend if not in interactive mode
        if not interactive:
            hr = [1] * nrows + [.5]
            nrows += 1
            gs = gridspec.GridSpec(nrows, 1, height_ratios=hr)
            legend_ax = fig.add_subplot(gs[-1, 0])
            legend_ax.set_axis_off()
        else:
            gs = gridspec.GridSpec(nrows, 1)
            legend_ax = None

        # EMG plots
        ind = 0
        for ch in self.emg_chs:
            sharex = None if ind == 0 or not interactive else data_axes[0]
            ax = fig.add_subplot(gs[ind, 0], sharex=sharex)
            emgtr_, = ax.plot(self.time_analog, self.emgdata[ch]*1e3,
                              linewidth=cfg.plot.emg_linewidth)
            rmstr_, = ax.plot(self.time_analog, self.emg_rms[ch]*1e3,
                              linewidth=cfg.plot.emg_rms_linewidth,
                              color='black')
            data_axes.append(ax)
            if interactive:
                self.emg_traces[ind] = emgtr_
                self.rms_traces[ind] = rmstr_
                self.emg_axes.append(ax)

            ysc = (cfg.plot.emg_yscale if emg_yscale is None
                   else emg_yscale/1.e3)
            ax.set_ylim([-ysc*1e3, ysc*1e3])
            ax.set(ylabel='mV')
            ax.set_title(ch)
            ind += 1

        # total acceleration
        if self.acctot is not None:
            sharex = None if ind == 0 or not interactive else data_axes[0]
            ax = fig.add_subplot(gs[ind, 0], sharex=sharex)
            ax.plot(self.time_analog, self.acctot,
                    linewidth=cfg.plot.emg_linewidth)
            # FIXME: no calibration yet so data is assumed to be in mV
            # ax.set(ylabel=u'm/s²')
            ax.set(ylabel=u'mV')
            ax.set_title('Accelerometer vector sum')
            data_axes.append(ax)
            ind += 1

        # angle plot
        sharex = None if ind == 0 or not interactive else data_axes[0]
        ax = fig.add_subplot(gs[ind, 0], sharex=sharex)
        ax.plot(self.time, self.angd, linewidth=cfg.plot.model_linewidth)
        ax.set(ylabel='deg')
        ax.set_title('Angle')
        data_axes.append(ax)
        ind += 1

        # angular velocity plot
        sharex = None if ind == 0 or not interactive else data_axes[0]
        ax = fig.add_subplot(gs[ind, 0], sharex=sharex)
        self.angveld = self.trial.framerate * np.diff(self.angd, axis=0)
        ax.plot(self.time[:-1], self.angveld,
                linewidth=cfg.plot.model_linewidth)
        ax.set(ylabel='deg/s')
        ax.set_title('Angular velocity')
        data_axes.append(ax)
        ind += 1

        # angular acceleration plot
        sharex = None if ind == 0 or not interactive else data_axes[0]
        ax = fig.add_subplot(gs[ind, 0], sharex=sharex)
        self.angaccd = np.diff(self.angveld, axis=0)
        ax.plot(self.time[:-2], self.angaccd,
                linewidth=cfg.plot.model_linewidth)
        ax.set(xlabel='Time (s)', ylabel=u'deg/s²')
        ax.set_title('Angular acceleration')
        data_axes.append(ax)

        for ax in data_axes:
            self._adj_fonts(ax)

        if interactive:
            self.data_axes = data_axes
            self.tmin, self.tmax = self.data_axes[0].get_xlim()
            # create markers
            markers = Markers(self.marker_colors, self.marker_width,
                              self.data_axes)

            # place the auto markers
            tmin_ = max(self.time[0], self.tmin)
            tmax_ = min(self.time[-1], self.tmax)
            fmin, fmax = self._time_to_frame([tmin_, tmax_],
                                             self.trial.framerate)
            smin, smax = self._time_to_frame([tmin_, tmax_],
                                             self.trial.analograte)
            # max. velocity
            velr = self.angveld[fmin:fmax]
            velmaxind = np.nanargmax(velr)/self.trial.framerate + tmin_
            markers.add(velmaxind, annotation='Max. velocity')
            # min. acceleration
            accr = self.angaccd[fmin:fmax]
            accmaxind = np.nanargmin(accr)/self.trial.framerate + tmin_
            markers.add(accmaxind, annotation='Min. acceleration')

            for ch in self.emg_chs:
                # check if channel is tagged for automark
                if any([s in ch for s in self.emg_automark_chs]):
                    rmsdata = self.emg_rms[ch][smin:smax]
                    rmsmaxind = np.argmax(rmsdata)/self.trial.analograte + tmin_
                    markers.add(rmsmaxind, annotation='%s max. RMS' % ch)

            # connect callbacks
            for ax in self.data_axes:
                ax.callbacks.connect('xlim_changed', self._xlim_changed)
            fig.canvas.mpl_connect('button_press_event', self._onclick)
            # catch key press
            # fig.canvas.mpl_connect('key_press_event', self._onpress)
            # pick handler
            fig.canvas.mpl_connect('pick_event', self._onpick)
            #
            self._last_click_event = None
            self.markers = markers

        fig.set_tight_layout(True)
        return fig, data_axes, legend_ax

    def _rescale_emg(self, yscale):
        """Takes new EMG yscale in mV"""
        for ax in self.emg_axes:
            ax.set_ylim(-yscale, yscale)

    def _get_fast_movement(self):
        """Get x range around fast movement"""
        velmaxt = self.time[np.nanargmax(self.angveld)]
        return velmaxt-.5, velmaxt+1.5

    def _xzoom(self, x1, x2):
        for ax in self.data_axes:
            ax.set_xlim(x1, x2)

    def _xzoom_to_fast(self):
        """Zoom x to fast movement"""
        rng = self._get_fast_movement()
        self._xzoom(rng[0], rng[1])

    def _xzoom_reset(self):
        self._xzoom(self.time[0], self.time[-1])

    def _reset_emg_filter(self, f1, f2):
        """Takes new EMG lowpass and highpass values"""
        logger.debug('reset EMG filter to %.2f-%.2f' % (f1, f2))
        self.trial.emg.passband = [f1, f2]
        for ind, ch in enumerate(self.emg_chs):
            t_, self.emgdata[ch] = self.trial[ch]
            self.emg_rms[ch] = rms(self.emgdata[ch], cfg.emg.rms_win)
            self.emg_traces[ind].set_ydata(self.emgdata[ch]*1e3)
            self.rms_traces[ind].set_ydata(self.emg_rms[ch]*1e3)

    @staticmethod
    def _adj_fonts(ax):
        """Adjust font sizes on an axis"""
        ax.xaxis.label.set_fontsize(cfg.plot.label_fontsize)
        ax.yaxis.label.set_fontsize(cfg.plot.label_fontsize)
        ax.title.set_fontsize(cfg.plot.title_fontsize)
        ax.tick_params(axis='both', which='major',
                       labelsize=cfg.plot.ticks_fontsize)

    @staticmethod
    def _time_to_frame(times, rate):
        """Convert time to samples (according to rate)"""
        return np.round(rate * np.array(times)).astype(int)

    def tight_layout(self):
        """ Auto set spacing between/around axes """
        self.fig.set_tight_layout(True)
        # not sure if works/needed
        # self.gs.update(hspace=self.hspace, wspace=self.wspace,
        #               left=self.margin, right=1-self.margin)
        # probably needed
        # self.fig.canvas.draw()

    def _xlim_changed(self, ax):
        """Callback for x limits change, e.g. on zoom"""
        # we need to get the limits from the axis that was zoomed
        # (the limits are not instantly propagated by sharex)
        self.tmin, self.tmax = ax.get_xlim()
        self.fig.canvas.draw()
        self._update_status()

    def _toggle_narrow_callback(self, event):
        """Toggle narrow/wide display"""
        self.narrow = not self.narrow
        wratios = [1, 1] if self.narrow else self.width_ratio
        btext = 'Wide view' if self.narrow else 'Narrow view'
        self.gs.set_width_ratios(wratios)
        self._narrowbutton.label.set_text(btext)
        self.gs.update()
        # FIXME: canvas ref
        self.fig.canvas.draw()

    def _onpick(self, event):
        """Gets triggered on pick event, i.e. selection of existing marker"""
        if self._toolbar.mode:  # do not respond if toolbar buttons enabled
            return
        mevent = event.mouseevent
        # prevent handling the same onpick event multiple times (e.g.
        # if multiple markers get picked on a single click)
        if self._last_click_event == mevent:
            return
        if (mevent.button != self.marker_del_button or
           mevent.key != self.marker_key):
            return
        self.markers.delete_artist(event.artist, mevent.inaxes)
        self._last_click_event = mevent
        self.fig.canvas.draw()
        self._update_marker_status()

    def _onpress(self, event):
        """Keyboard event handler"""
        if event.key == 'tab':
            self._toggle_narrow_callback(event)

    def _onclick(self, event):
        """Gets triggered by a mouse click on canvas"""
        if self._toolbar.mode:  # do not respond if toolbar buttons are enabled
            return
        if event.inaxes not in self.data_axes:
            return
        # prevent handling the same click event multiple times
        # onpick and onclick may get triggered simultaneously
        if event == self._last_click_event:
            return
        if event.button != self.marker_button or event.key != self.marker_key:
            return
        x = event.xdata
        self.markers.add_on_click(x)
        self._last_click_event = event
        self.fig.canvas.draw()
        self._update_marker_status()

    @property
    def marker_status_text(self):
        """Return marker status text in HTML"""
        s = u''
        # each marker gets text of its own color
        for marker, anno, col in self.markers.marker_info:
            frame = self._time_to_frame(marker, self.trial.framerate)
            s += u"<font color='%s'>" % col
            # len of acc signal is nframes - 2
            if frame < 0 or frame >= self.nframes - 2:
                s += u'Marker outside data range'
            else:
                s += u'Marker @%.3f s' % marker
                s += (' (%s):<br>') % anno if anno else ':<br>'
                s += u'dflex: %.2f° vel: %.2f°/s' % (self.angd[frame],
                                                       self.angveld[frame])
                s += u' acc: %.2f°/s²<br><br>' % self.angaccd[frame]
            s += u'</font>'
        return s

    @property
    def status_text(self):
        """Create the status text"""

        # find the limits of the data that is shown
        tmin_ = max(self.time[0], self.tmin)
        tmax_ = min(self.time[-1], self.tmax)
        s = u'Trial name: %s\n' % self.trial.trialname
        s += u'Description: %s\n' % (self.trial.eclipse_data['DESCRIPTION'])
        s += u'Notes: %s\n' % (self.trial.eclipse_data['NOTES'])
        s += u'Angle offset: '
        s += (u' %.1f°\n' % self.ang0_nexus) if self.ang0_nexus else u'none\n'
        s += u'Data range shown: %.2f - %.2f s\n' % (tmin_, tmax_)
        # frame indices corresponding to time limits
        fmin, fmax = self._time_to_frame([tmin_, tmax_], self.trial.framerate)
        if fmin == fmax:
            s += 'Zoomed in to a single frame\nPlease zoom out for info'
            return s
        else:
            smin, smax = self._time_to_frame([tmin_, tmax_],
                                             self.trial.analograte)
            s += u'In frames: %d - %d\n\n' % (fmin, fmax)
            # foot angle in chosen range and the maximum
            angr = self.angd[fmin:fmax]
            # check if we zoomed to all-nan region of angle data
            if np.all(np.isnan(angr)):
                s += 'No valid data in region'
                return s
            angmax = np.nanmax(angr)
            angmaxind = np.nanargmax(angr)/self.trial.framerate + tmin_
            angmin = np.nanmin(angr)
            angminind = np.nanargmin(angr)/self.trial.framerate + tmin_
            # same for velocity
            velr = self.angveld[fmin:fmax]
            velmax = np.nanmax(velr)
            velmaxind = np.nanargmax(velr)/self.trial.framerate + tmin_
            s += u'Values for range shown:\n'
            s += u'Max. dorsiflexion: %.2f° @ %.2f s\n' % (angmax, angmaxind)
            s += u'Max. plantarflexion: %.2f° @ %.2f s\n' % (angmin, angminind)
            s += u'Max velocity: %.2f°/s @ %.2f s\n' % (velmax, velmaxind)
            for ch in self.emg_chs:
                rmsdata = self.emg_rms[ch][smin:smax]
                rmsmax = rmsdata.max()
                rmsmaxind = np.argmax(rmsdata)/self.trial.analograte + tmin_
                s += u'%s max RMS: %.2f mV @ %.2f s\n' % (ch, rmsmax*1e3,
                                                          rmsmaxind)
            return s


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)

    # uiparser logger makes too much noise
    logging.getLogger('PyQt5.uic').setLevel(logging.WARNING)

    app = QtWidgets.QApplication(sys.argv)
    win = TardieuWindow()
    win.show()
    sys.exit(app.exec_())
