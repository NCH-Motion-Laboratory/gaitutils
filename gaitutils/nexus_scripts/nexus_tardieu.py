# -*- coding: utf-8 -*-
"""
Interactive script for analysis of Tardieu trials.
matplotlib + Qt5

TODO:

    focus issues?
    reloading data causes confusion / crash
    fix marker colors
    direct c3d load?
    figure saving on button
        -may need to create a 'report' since text needs to be saved also
        -maybe ask Tobi
    layout spacing ok?
    real time changes to norm. angle and emg passband?
    fix left panel width? may change according to text
    add config options?
    add statusbar?

    testing

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
from pkg_resources import resource_filename
from PyQt5 import QtGui, QtWidgets, uic, QtCore
from matplotlib.backends.backend_qt5agg import (FigureCanvasQTAgg,
                                                NavigationToolbar2QT)

from gaitutils import (EMG, nexus, cfg, read_data, trial, eclipse, models,
                       Trial, Plotter, layouts, utils, GaitDataError,
                       register_gui_exception_handler)
from gaitutils.numutils import segment_angles, rms

# increase default DPI for figure saving
# FIXME: config?
# FIXME: plt not imported
#plt.rcParams['savefig.dpi'] = 200

matplotlib.style.use(cfg.plot.mpl_style)

logger = logging.getLogger(__name__)


# FIXME: this should go into common GUI module
def message_dialog(msg):
    """ Show message with an 'OK' button. """
    dlg = QtWidgets.QMessageBox()
    dlg.setWindowTitle('Message')
    dlg.setText(msg)
    dlg.addButton(QtWidgets.QPushButton('Ok'),
                  QtWidgets.QMessageBox.YesRole)
    dlg.exec_()


def yesno_dialog(msg):
    """ Show message with 'Yes' and 'No buttons, return role accordingly """
    dlg = QtWidgets.QMessageBox()
    dlg.setWindowTitle('Message')
    dlg.setText(msg)
    dlg.addButton(QtWidgets.QPushButton('Yes'),
                  QtWidgets.QMessageBox.YesRole)
    dlg.addButton(QtWidgets.QPushButton('No'),
                  QtWidgets.QMessageBox.NoRole)
    dlg.exec_()
    return dlg.buttonRole(dlg.clickedButton())


class SimpleToolbar(NavigationToolbar2QT):
    """ Simplified mpl navigation toolbar with some items removed """

    toolitems = [t for t in NavigationToolbar2QT.toolitems if
                 t[0] in ('Home', 'Pan', 'Zoom')]


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
        self.canvas.setParent(self)
        self.canvas.show()
        self._tardieu_plot.fig.canvas = self.canvas

        self.btnClearMarkers.clicked.connect(self._clear_markers)
        self.btnQuit.clicked.connect(self.close)
        self.btnLoadData.clicked.connect(self._create_plot)
        self.spEMGLow.setValue(cfg.emg.passband[0])
        self.spEMGHigh.setValue(cfg.emg.passband[1])

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

        # these are needed for mpl callbacks to work (?)
        self.canvas.setFocusPolicy(QtCore.Qt.ClickFocus)
        self.canvas.setFocus()
        self.canvas.draw()

    def _create_plot(self):
        """Load data and create the mpl plot"""
        # FIXME: need to clear previous plot / reset some vars?
        side = 'R' if self.rbRight.isChecked() else 'L'
        # prepend side to configured EMG channel names
        emg_chs = [side+ch for ch in cfg.tardieu.emg_chs]
        emg_passband = [self.spEMGLow.value(), self.spEMGHigh.value()]
        if emg_passband[0] >= emg_passband[1]:
            message_dialog('Invalid EMG passband')
            return
        if not self._tardieu_plot.load_data(emg_chs, emg_passband):
            return
        # load successful
        self._tardieu_plot.plot_data()
        self.canvas.draw()
        self.canvas.setFocus()
        self._update_status()
        self._update_marker_status()

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
        reply = yesno_dialog('Are you sure?')
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
                message_dialog('You can place a maximum of %d markers' %
                               self.max_markers)
            else:
                self.add(x)

    def add(self, x, annotation=''):
        """Add a marker at point x with optional annotation"""
        if x in self._markers.keys():  # marker already at this point
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
                              'pink', 'gray']
        self.marker_width = 1.5
        self.emg_yrange = [-.5e-3, .5e-3]
        self.width_ratio = [1, 5]
        self.text_fontsize = 9
        self.margin = .025  # margin at edge of plots
        self.margin = 0
        self.narrow = False
        self.hspace = .4
        self.wspace = .5
        self.emg_automark_chs = ['Gas', 'Sol']
        self.data_axes = list()  # axes that actually contain data
        # these are callbacks that should be registered by the creator
        self._update_marker_status = None
        self._update_status = None
        self.fig = Figure()

    def load_data(self, emg_chs, emg_passband):
        """Load the Tardieu data.
        emg_chs: list of EMG channel names to use

        Returns True on successful data load, False otherwise
        """

        logger.debug('Load data, EMG passband %s' % emg_passband)

        try:
            vicon = nexus.viconnexus()
            self.trial = Trial(vicon)
            self.trial.emg.passband = emg_passband
        except GaitDataError as e:
            message_dialog(e.message)
            return False

        self.emg_chs = emg_chs
        self.time = self.trial.t / self.trial.framerate  # time axis in sec
        self.tmax = self.time[-1]
        self.nframes = len(self.time)

        # read EMG data
        self.emgdata = dict()
        self.emg_rms = dict()
        for ch in self.emg_chs:
            try:
                t_, self.emgdata[ch] = self.trial[ch]
                self.emg_rms[ch] = rms(self.emgdata[ch], cfg.emg.rms_win)
            except KeyError:
                message_dialog('EMG channel not found: %s' % ch)
                return False

        # FIXME: self.time?
        self.t = t_ / self.trial.analograte

        # read marker data and compute segment angle
        # FIXME: hardcoded marker names?
        try:
            data = read_data.get_marker_data(vicon, ['Toe', 'Ankle', 'Knee'])
        except GaitDataError as e:
            message_dialog(e.message)
            return False
        Ptoe = data['Toe_P']
        Pank = data['Ankle_P']
        Pknee = data['Knee_P']
        # stack so that marker changes along 2nd dim for segment_angles
        Pall = np.stack([Ptoe, Pank, Pknee], axis=1)
        # compute segment angles (deg)
        self.angd = segment_angles(Pall) / np.pi * 180
        # this is our calculated starting angle
        ang0_our = np.median(self.angd[~np.isnan(self.angd)][:10])
        # the 'true' starting angle (in Nexus as subject param)
        self.ang0_nexus = self.read_starting_angle(vicon)
        # normalize: plantarflexion negative, our starting angle equals
        # the starting angle given in Nexus (i.e. if ang0_nexus is 95,
        # we normalize the data to start at -5 deg)
        # if starting angle is not specified in Nexus, assume 90 deg
        if self.ang0_nexus:
            self.angd = 90 - self.ang0_nexus - self.angd + ang0_our
        else:
            self.angd = -self.angd + ang0_our
        return True

    def plot_data(self):
        """Plot the data."""
        self.gs = gridspec.GridSpec(len(self.emg_chs) + 3, 1)

        # EMG plots
        for ind, ch in enumerate(self.emg_chs):
            sharex = None if ind == 0 else self.data_axes[0]
            ax = self.fig.add_subplot(self.gs[ind, 0],
                                      sharex=sharex)
            ax.plot(self.t, self.emgdata[ch]*1e3,
                    linewidth=cfg.plot.emg_linewidth)
            ax.plot(self.t, self.emg_rms[ch]*1e3,
                    linewidth=cfg.plot.emg_rms_linewidth, color='black')
            ax.set_ylim(self.emg_yrange[0]*1e3, self.emg_yrange[1]*1e3)
            ax.set(ylabel='mV')
            ax.set_title(ch)
            self._adj_fonts(ax)
            self.data_axes.append(ax)
        ind += 1

        # angle plot
        ax = self.fig.add_subplot(self.gs[ind, 0],
                                  sharex=self.data_axes[0])
        ax.plot(self.time, self.angd, linewidth=cfg.plot.model_linewidth)
        ax.set(ylabel='deg')
        ax.set_title('Angle')
        # FIXME: loop adj_fonts on data_axes
        self._adj_fonts(ax)
        self.data_axes.append(ax)
        ind += 1

        # angular velocity plot
        ax = self.fig.add_subplot(self.gs[ind, 0],
                                  sharex=self.data_axes[0])
        self.angveld = self.trial.framerate * np.diff(self.angd, axis=0)
        ax.plot(self.time[:-1], self.angveld,
                linewidth=cfg.plot.model_linewidth)
        ax.set(ylabel='deg/s')
        ax.set_title('Angular velocity')
        self._adj_fonts(ax)
        self.data_axes.append(ax)
        ind += 1

        # angular acceleration plot
        ax = self.fig.add_subplot(self.gs[ind, 0],
                                  sharex=self.data_axes[0])
        self.angaccd = np.diff(self.angveld, axis=0)
        ax.plot(self.time[:-2], self.angaccd,
                linewidth=cfg.plot.model_linewidth)
        ax.set(xlabel='Time (s)', ylabel=u'deg/s²')
        ax.set_title('Angular acceleration')
        self._adj_fonts(ax)
        self.data_axes.append(ax)

        self.tmin, self.tmax = self.data_axes[0].get_xlim()

        # create markers
        self.markers = Markers(self.marker_colors, self.marker_width,
                               self.data_axes)

        # place the auto markers
        tmin_ = max(self.time[0], self.tmin)
        tmax_ = min(self.time[-1], self.tmax)
        fmin, fmax = self._time_to_frame([tmin_, tmax_], self.trial.framerate)
        smin, smax = self._time_to_frame([tmin_, tmax_], self.trial.analograte)
        # max. velocity
        velr = self.angveld[fmin:fmax]
        velmaxind = np.nanargmax(velr)/self.trial.framerate + tmin_
        self.markers.add(velmaxind, annotation='Max. velocity')
        for ch in self.emg_chs:
            # check if channel is tagged for automark
            if any([s in ch for s in self.emg_automark_chs]):
                rmsdata = self.emg_rms[ch][smin:smax]
                rmsmaxind = np.argmax(rmsdata)/self.trial.analograte + tmin_
                self.markers.add(rmsmaxind, annotation='%s max. RMS' % ch)

        self._last_click_event = None

        # connect callbacks
        for ax in self.data_axes:
            ax.callbacks.connect('xlim_changed', self._xlim_changed)

        self.fig.canvas.mpl_connect('button_press_event', self._onclick)
        # catch key press
        self.fig.canvas.mpl_connect('key_press_event', self._onpress)
        # pick handler
        self.fig.canvas.mpl_connect('pick_event', self._onpick)

        self.tight_layout()

    @staticmethod
    def read_starting_angle(vicon):
        """Read the Nexus defined starting angle"""
        subjname = nexus.get_subjectnames()
        asp = vicon.GetSubjectParam(subjname, 'AnkleStartPos')
        return asp[0] if asp[1] else None

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
        if self._toolbar.mode:  # do not respond if toolbar buttons enabled
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
            if frame < 0 or frame >= self.nframes:
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
        s = u'Shift+left click to add a new marker\n'
        s += u'Shift+right click to remove a marker\n'
        s += u'Tab to toggle wide/narrow display\n\n'
        s += u'Trial name: %s\n' % self.trial.trialname
        s += u'Description: %s\n' % (self.trial.eclipse_data['DESCRIPTION'])
        s += u'Notes: %s\n' % (self.trial.eclipse_data['NOTES'])
        s += u'Nexus angle offset: '
        s += (u' %.2f\n' % self.ang0_nexus) if self.ang0_nexus else u'none\n'
        s += u'EMG passband: %.1f Hz - %.1f Hz\n' % (self.trial.emg.passband[0], self.trial.emg.passband[1])
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
            s += u'Values for shown range:\n'
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
