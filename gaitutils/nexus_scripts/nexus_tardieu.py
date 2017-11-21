# -*- coding: utf-8 -*-
"""
Interactive script for analysis of Tardieu trials.

TODO:
    create mainwindow w/ controls class
    do not import pyplot
    rm mpl widgets
   


@author: Jussi (jnu@iki.fi)
"""

from __future__ import print_function
from collections import OrderedDict
import matplotlib
from matplotlib.figure import Figure
from matplotlib.widgets import Button
import matplotlib.gridspec as gridspec
import logging
import sys
import numpy as np
from pkg_resources import resource_filename
from PyQt5 import QtGui, QtWidgets, uic, QtCore
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from matplotlib.backends.backend_qt5agg import (NavigationToolbar2QT as
                                                NavigationToolbar)

from gaitutils import (EMG, nexus, cfg, read_data, trial, eclipse, models,
                       Trial, Plotter, layouts, utils, GaitDataError,
                       register_gui_exception_handler)
from gaitutils.numutils import segment_angles, rms
from gaitutils.guiutils import messagebox

# increase default DPI for figure saving
# TODO: into config?
#plt.rcParams['savefig.dpi'] = 200

matplotlib.style.use(cfg.plot.mpl_style)

logger = logging.getLogger(__name__)


class TardieuWindow(QtWidgets.QMainWindow):

    def __init__(self, parent=None):
        super(TardieuWindow, self).__init__(parent)

        uifile = resource_filename(__name__, 'tardieu.ui')
        uic.loadUi(uifile, self)

        # FIXME: right channel
        emg_chs = ['R'+ch for ch in cfg.tardieu.emg_chs]

        self._tardieu_plot = TardieuPlot(emg_chs=emg_chs)
        self.canvas = FigureCanvasQTAgg(self._tardieu_plot.fig)
        self.canvas.setSizePolicy(QtWidgets.QSizePolicy.Expanding,
                                  QtWidgets.QSizePolicy.Expanding)

        # FIXME: canvas callbacks need to be set here, or alternatively
        # canvas ref could live in the plot class

        # these are needed for mpl callbacks to work (?)
        self.canvas.setFocusPolicy(QtCore.Qt.ClickFocus)
        self.canvas.setFocus()

        # self.setStyleSheet("background-color: white;");
        # add canvas into last column, span all rows
        self.mainGridLayout.addWidget(self.canvas, 0,
                                      self.mainGridLayout.columnCount(),
                                      self.mainGridLayout.rowCount(), 1)


class Markers(object):
    """ Manage the marker lines at given axes """

    def __init__(self, marker_colors, marker_width, markers_text_start,
                 markers_text_spacing, axes):
        self._markers = OrderedDict()  # keyed by time coordinate
        self._axes = axes
        self.marker_colors = marker_colors
        self.marker_width = marker_width
        self.max_markers = len(self.marker_colors)
        # calculate text positions for markers
        markers_text_end = (markers_text_start -
                            (markers_text_spacing * self.max_markers))
        self.markers_text_pos = np.linspace(markers_text_start,
                                            markers_text_end,
                                            self.max_markers)

    def add_on_click(self, x):
        if x not in self._markers.keys():
            if len(self._markers) == self.max_markers:
                messagebox('You can place a maximum of %d markers' %
                           self.max_markers)
            else:
                self.add(x)

    def add(self, x, annotation=''):
        """ Add marker at x at given axes """
        if x in self._markers.keys():
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
        """ Delete by location """
        for ax in self._axes:
            self._markers[x][ax].remove()
        self._markers.pop(x)

    def delete_artist(self, artist, ax):
        """ Delete by artist at axis ax """
        # need to find the marker that has the corresponding artist
        for x, m in self._markers.items():
            if m[ax] == artist:
                self.delete(x)
                return

    def clear(self):
        for marker in self._markers:
            self.delete(marker)

    def marker_pos_col(self):
        """ Return tuple of marker, annotation, position and color """
        annotations = [m['annotation'] for m in self._markers.values()]
        cols_in_use = [m['color'] for m in self._markers.values()]
        return zip(self._markers.keys(), annotations, self.markers_text_pos,
                   cols_in_use)


class TardieuPlot(object):
    """ matplotlib graphs for Tardieu analysis """

    def __init__(self, emg_chs=None):

        # adjustable params
        # TODO: some could go into config
        self.marker_button = 1  # mouse button for placing markers
        self.marker_del_button = 3  # remove marker
        self.marker_key = 'shift'  # modifier key for markers
        # take marker colors from mpl default cycle, but skip the first color
        # (which is used for angle plots). n of colors determines max n of
        # markers.
        marker_colors = ['tab:orange', 'tab:green', 'tab:red', 'tab:brown',
                         'tab:pink', 'tab:gray', 'tab:olive'][:6]
        marker_width = 1.5
        self.emg_yrange = [-.5e-3, .5e-3]
        self.width_ratio = [1, 5]
        self.text_fontsize = 9
        self.margin = .025  # margin at edge of plots
        self.narrow = False
        self.hspace = .4
        self.wspace = .5
        markers_text_start = .95  # relative to the text axis
        markers_text_spacing = .15
        self.emg_chs = emg_chs
        self.emg_automark_chs = ['Gas', 'Sol']
        self.texts = []
        self.data_axes = list()  # axes that actually contain data

        # read data from Nexus and initialize plot
        try:
            vicon = nexus.viconnexus()
            self.trial = Trial(vicon)
        except GaitDataError as e:
            messagebox(e.message)
            return
        self.time = self.trial.t / self.trial.framerate  # time axis in sec
        self.tmax = self.time[-1]
        self.nframes = len(self.time)

        # read marker data from Nexus
        try:
            data = read_data.get_marker_data(vicon, ['Toe', 'Ankle', 'Knee'])
        except GaitDataError as e:
            messagebox(e.message)
            return
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

        self.fig = Figure(figsize=(16, 10))
        self.gs = gridspec.GridSpec(len(self.emg_chs) + 3, 1)
        
        # plot EMG signals
        self.emg_rms = dict()
        for ind, ch in enumerate(emg_chs):
            try:
                t_, emgdata = self.trial[ch]
            except KeyError:
                messagebox('EMG channel not found: %s' % ch)
                sys.exit()
            t = t_ / self.trial.analograte

            self.emg_rms[ch] = rms(emgdata, cfg.emg.rms_win)
            sharex = None if ind == 0 else self.data_axes[0]
            ax = self.fig.add_subplot(self.gs[ind, 0],
                                      sharex=sharex)
            ax.plot(t, emgdata*1e3, linewidth=cfg.plot.emg_linewidth)
            ax.plot(t, self.emg_rms[ch]*1e3,
                    linewidth=cfg.plot.emg_rms_linewidth, color='black')
            ax.set_ylim(self.emg_yrange[0]*1e3, self.emg_yrange[1]*1e3)
            ax.set(ylabel='mV')
            ax.set_title(ch)
            self._adj_fonts(ax)
            self.data_axes.append(ax)

        ind += 1

        # add angle plot
        ax = self.fig.add_subplot(self.gs[ind, 0],
                                  sharex=self.data_axes[0])
        ax.plot(self.time, self.angd, linewidth=cfg.plot.model_linewidth)
        ax.set(ylabel='deg')
        ax.set_title('Angle')
        self._adj_fonts(ax)
        self.data_axes.append(ax)
        ind += 1

        # add angular velocity plot
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

        # add angular acceleration plot
        ax = self.fig.add_subplot(self.gs[ind, 0],
                                  sharex=self.data_axes[0])
        self.angaccd = np.diff(self.angveld, axis=0)
        ax.plot(self.time[:-2], self.angaccd,
                linewidth=cfg.plot.model_linewidth)
        ax.set(xlabel='Time (s)', ylabel=u'deg/s²')
        ax.set_title('Angular acceleration')
        self._adj_fonts(ax)
        self.data_axes.append(ax)

        # create markers
        self.markers = Markers(marker_colors, marker_width, markers_text_start,
                               markers_text_spacing, self.data_axes)

        # add text axis spanning the left column (leave top rows for buttons)
        """
        self.textax = self.fig.add_subplot(self.gs[3:8, 0])
        self.textax.set_axis_off()
        self.marker_textax = self.fig.add_subplot(self.gs[8:, 0])
        self.marker_textax.set_axis_off()
        """

        # refresh text field on zoom
        for ax in self.data_axes:
            ax.callbacks.connect('xlim_changed', self._redraw)

        # FIXME: canvas does not exist here
        """
        # catch mouse click to add events
        self.fig.canvas.mpl_connect('button_press_event', self._onclick)
        # catch key press
        self.fig.canvas.mpl_connect('key_press_event', self._onpress)
        # pick handler
        self.fig.canvas.mpl_connect('pick_event', self._onpick)

        # adjust plot layout
        self.gs.tight_layout(self.fig)
        # self.gs.update(hspace=self.hspace, wspace=self.wspace,
        #               left=self.margin, right=1-self.margin)
        """

        # FIXME: move buttons to Qt interface
        """
        # add buttons
        # add the clear button
        ax = plt.axes([self.margin, 1-self.margin-buttonheight,
                       buttonwidth, buttonheight])
        self._clearbutton = Button(ax, 'Clear markers')
        self._clearbutton.label.set_fontsize(self.text_fontsize)
        self._clearbutton.on_clicked(self._clear_callback)
        # add the narrow view button
        ax = plt.axes([self.margin, 1-self.margin-2*buttonheight-buttongap,
                       buttonwidth, buttonheight])
        self._narrowbutton = Button(ax, 'Narrow view')
        self._narrowbutton.label.set_fontsize(self.text_fontsize)
        self._narrowbutton.on_clicked(self._toggle_narrow_callback)
        # add quit button
        ax = plt.axes([self.margin, 1-self.margin-3*buttonheight-2*buttongap,
                       buttonwidth, buttonheight])
        self._quitbutton = Button(ax, 'Quit')
        self._quitbutton.label.set_fontsize(self.text_fontsize)
        self._quitbutton.on_clicked(self.close)
        """

        self.tmin, self.tmax = self.data_axes[0].get_xlim()

        # automatically place markers
        tmin_ = max(self.time[0], self.tmin)
        tmax_ = min(self.time[-1], self.tmax)
        fmin, fmax = self._time_to_frame([tmin_, tmax_], self.trial.framerate)
        smin, smax = self._time_to_frame([tmin_, tmax_], self.trial.analograte)
        # max. velocity
        velr = self.angveld[fmin:fmax]
        velmaxind = np.nanargmax(velr)/self.trial.framerate + tmin_
        self.markers.add(velmaxind, annotation='Max. velocity')
        for ch in self.emg_chs:
            # check if ch is tagged for automark
            if any([s in ch for s in self.emg_automark_chs]):
                rmsdata = self.emg_rms[ch][smin:smax]
                rmsmaxind = np.argmax(rmsdata)/self.trial.analograte + tmin_
                self.markers.add(rmsmaxind, annotation='%s max. RMS' % ch)

        # init status text
        self._update_status_text()
        self._last_click_event = None

        # self._toolbar = plt.get_current_fig_manager().toolbar

    @staticmethod
    def read_starting_angle(vicon):
        subjname = nexus.get_subjectnames()
        asp = vicon.GetSubjectParam(subjname, 'AnkleStartPos')
        return asp[0] if asp[1] else None

    @staticmethod
    def _adj_fonts(ax):
        ax.xaxis.label.set_fontsize(cfg.plot.label_fontsize)
        ax.yaxis.label.set_fontsize(cfg.plot.label_fontsize)
        ax.title.set_fontsize(cfg.plot.title_fontsize)
        ax.tick_params(axis='both', which='major',
                       labelsize=cfg.plot.ticks_fontsize)

    @staticmethod
    def _time_to_frame(times, rate):
        """Convert time to samples (according to rate)"""
        return np.round(rate * np.array(times)).astype(int)


    def close(self, event):
        """Close window"""
        #plt.close(self.fig)
    

    def _redraw(self, ax):
        """Update display on e.g. zoom"""
        # we need to get the limits from the axis that was zoomed
        # (the limits are not instantly updated by sharex)
        self.tmin, self.tmax = ax.get_xlim()
        self._update_status_text()

    def _clear_callback(self, event):
        """Clear all line markers"""
        self.markers.clear()
        self._update_status_text()

    def _toggle_narrow_callback(self, event):
        """Toggle narrow/wide display"""
        self.narrow = not self.narrow
        wratios = [1, 1] if self.narrow else self.width_ratio
        btext = 'Wide view' if self.narrow else 'Narrow view'
        self.gs.set_width_ratios(wratios)
        self._narrowbutton.label.set_text(btext)
        self.gs.update()
        # FIXME: canvas ref
        #self.fig.canvas.draw()

    def _onpick(self, event):
        if self._toolbar.mode:
            return
        mevent = event.mouseevent
        # prevent handling an onpick event multiple times (e.g. if multiple
        # markers get picked)
        if self._last_click_event == mevent:
            return
        if (mevent.button != self.marker_del_button or
           mevent.key != self.marker_key):
            return
        self.markers.delete_artist(event.artist, mevent.inaxes)
        self._last_click_event = mevent
        self._redraw(mevent.inaxes)  # marker status needs to be updated

    def _onpress(self, event):
        """Keyboard event handler"""
        if event.key == 'tab':
            self._toggle_narrow_callback(event)

    def _onclick(self, event):
        """Mouse click handler"""
        if self._toolbar.mode:
            return
        if event.inaxes not in self.data_axes:
            return
        # prevent handling a click event multiple times
        # check is also needed here since onpick and onclick may get triggered
        # simultaneously
        if event == self._last_click_event:
            return
        if event.button != self.marker_button or event.key != self.marker_key:
            return
        x = event.xdata
        self.markers.add_on_click(x)
        self._last_click_event = event
        self._redraw(event.inaxes)  # marker status needs to be updated

    def _plot_text(self, ax, s, ypos, color):
        """Plot string s at y position ypos (relative to text frame)"""
        self.texts.append(ax.text(0, ypos, s, ha='left', va='top',
                                  transform=ax.transAxes,
                                  fontsize=self.text_fontsize,
                                  color=color, wrap=True))

    def _markers_info(self):
        # annotate markers
        for marker, anno, pos, col in self.markers.marker_pos_col():
            frame = self._time_to_frame(marker, self.trial.framerate)
            if frame < 0 or frame >= self.nframes:
                ms = u'Marker outside data range'
            else:
                ms = u'Marker @%.3f s' % marker
                ms += (' (%s):\n') % anno if anno else ':\n'
                ms += u'dflex: %.2f° vel: %.2f°/s' % (self.angd[frame],
                                                        self.angveld[frame])
                ms += u' acc: %.2f°/s²\n\n' % self.angaccd[frame]
            yield ms
            # self._plot_text(self.marker_textax, ms, pos, col)

    def _update_status_text(self):
        """Create status text & update display"""

        if self.texts:
            [txt.remove() for txt in self.texts]
            self.texts = []
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
        s += u'EMG passband: %.1f Hz - %.1f Hz\n' % (self.trial.emg.passband)
        s += u'Data range shown: %.2f - %.2f s\n' % (tmin_, tmax_)
        # frame indices corresponding to time limits
        fmin, fmax = self._time_to_frame([tmin_, tmax_], self.trial.framerate)
        if fmin == fmax:
            s += 'Zoomed in to a single frame\nPlease zoom out for info'
            self._plot_text(self.textax, s, 1, 'k')
            self._show_markers_info()
            return
        else:
            # analog sample indices ...
            smin, smax = self._time_to_frame([tmin_, tmax_],
                                             self.trial.analograte)
            s += u'In frames: %d - %d\n\n' % (fmin, fmax)
            # foot angle in chosen range and the maximum
            angr = self.angd[fmin:fmax]
            # check if we zoomed to all-nan region of angle data
            if np.all(np.isnan(angr)):
                s += 'No valid data in region'
                self._plot_text(self.textax, s, 1, 'k')
                self._show_markers_info()
                return
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
            #self._plot_text(self.textax, s, 1, 'k')
            #self._show_markers_info()
        # FIXME: canvas ref
        #self.fig.canvas.draw()


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)

    # uiparser logger makes too much noise
    logging.getLogger('PyQt5.uic').setLevel(logging.WARNING)

    app = QtWidgets.QApplication(sys.argv)
    win = TardieuWindow()

    win.show()
    sys.exit(app.exec_())
