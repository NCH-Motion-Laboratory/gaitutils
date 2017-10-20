# -*- coding: utf-8 -*-
"""
Interactive script for analysis of Tardieu trials.


@author: Jussi (jnu@iki.fi)
"""

from __future__ import print_function
from collections import OrderedDict
import matplotlib
import matplotlib.pyplot as plt
from matplotlib.widgets import Button
import matplotlib.gridspec as gridspec
import logging
import sys
import numpy as np

from gaitutils import (EMG, nexus, cfg, read_data, trial, eclipse, models,
                       Trial, Plotter, layouts, utils, GaitDataError,
                       register_gui_exception_handler)
from gaitutils.numutils import segment_angles, rms
from gaitutils.guiutils import messagebox

# increase default DPI for figure saving
plt.rcParams['savefig.dpi'] = 200
# style
matplotlib.style.use(cfg.plot.mpl_style)


logger = logging.getLogger(__name__)


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

    def clicked(self, x):
        if x not in self._markers.keys():
            if len(self._markers) == self.max_markers:
                messagebox('You can place a maximum of %d markers' %
                           self.max_markers)
            else:
                self.add(x)
        else:
            self.delete(x)  # secret delete-on-click feature

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


class Tardieu_window(object):
    """ Open a matplotlib window for Tardieu analysis """

    def __init__(self, emg_chs=None):

        # adjustable params
        # TODO: some could go into config
        self.marker_button = 1  # mouse button for placing markers
        self.marker_del_button = 3  # remove marker
        self.marker_key = 'shift'  # modifier key for markers
        # take marker colors from mpl default cycle, but skip the first color
        # (which is used for angle plots). n of colors determined max n of
        # markers.
        marker_colors = [u'#55A868', u'#C44E52', u'#8172B2', u'#CCB974',
                         u'#64B5CD']
        marker_width = 1.5
        self.emg_yrange = [-.5e-3, .5e-3]
        self.width_ratio = [1, 5]
        self.text_fontsize = 9
        self.margin = .025  # margin at edge of plots
        self.narrow = False
        self.hspace = .4
        self.wspace = .4
        markers_text_start = .5  # relative to the text axis
        markers_text_spacing = .05
        buttonwidth = .125
        buttonheight = .04
        buttongap = .025
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
        ang0_nexus = self.read_starting_angle(vicon)
        # if it cannot be read, assume 90 deg
        ang0_nexus = 90 if ang0_nexus is None else ang0_nexus
        # normalize: plantarflexion negative, our starting angle equals
        # the starting angle given in Nexus (i.e. if ang0_nexus is 95,
        # we normalize the data to start at -5 deg)
        self.angd = 90 - ang0_nexus - self.angd + ang0_our

        self.fig = plt.figure(figsize=(16, 10))
        self.gs = gridspec.GridSpec(len(self.emg_chs) + 3, 2,
                                    width_ratios=self.width_ratio)

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
            ax = plt.subplot(self.gs[ind, 1:], sharex=sharex)
            ax.plot(t, emgdata*1e3, linewidth=cfg.plot.emg_linewidth)
            ax.plot(t, self.emg_rms[ch]*1e3,
                    linewidth=cfg.plot.emg_rms_linewidth, color='black')
            ax.set_ylim(self.emg_yrange[0]*1e3, self.emg_yrange[1]*1e3)
            ax.set(ylabel='mV')
            ax.set_title(ch)
            self._adj_fonts(ax)
            self.data_axes.append(ax)

        pos = len(emg_chs)
        # add angle plot
        ax = plt.subplot(self.gs[pos, 1:], sharex=self.data_axes[0])
        ax.plot(self.time, self.angd, linewidth=cfg.plot.model_linewidth)
        ax.set(ylabel='deg')
        ax.set_title('Angle')
        self._adj_fonts(ax)
        self.data_axes.append(ax)

        # add angular velocity plot
        ax = plt.subplot(self.gs[pos+1, 1:], sharex=self.data_axes[0])
        self.angveld = self.trial.framerate * np.diff(self.angd, axis=0)
        ax.plot(self.time[:-1], self.angveld,
                linewidth=cfg.plot.model_linewidth)
        ax.set(ylabel='deg/s')
        ax.set_title('Angular velocity')
        self._adj_fonts(ax)
        self.data_axes.append(ax)

        # add angular acceleration plot
        ax = plt.subplot(self.gs[pos+2, 1:], sharex=self.data_axes[0])
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
        self.textax = plt.subplot(self.gs[2:, 0])
        self.textax.set_axis_off()

        # refresh text field on zoom
        for ax in self.data_axes:
            ax.callbacks.connect('xlim_changed', self._redraw)

        # catch mouse click to add events
        self.fig.canvas.mpl_connect('button_press_event', self._onclick)
        # catch key press
        self.fig.canvas.mpl_connect('key_press_event', self._onpress)
        # pick handler
        self.fig.canvas.mpl_connect('pick_event', self._onpick)

        # adjust plot layout
        self.gs.tight_layout(self.fig)
        self.gs.update(hspace=self.hspace, wspace=self.wspace,
                       left=self.margin, right=1-self.margin)

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

        self.tmin, self.tmax = self.data_axes[0].get_xlim()

        # automatically place markers
        tmin_ = max(self.time[0], self.tmin)
        tmax_ = min(self.time[-1], self.tmax)
        fmin, fmax = self._time_to_frame([tmin_, tmax_], self.trial.framerate)
        smin, smax = self._time_to_frame([tmin_, tmax_], self.trial.analograte)
        angr = self.angd[fmin:fmax]
        angminind = np.nanargmin(angr)/self.trial.framerate + tmin_
        self.markers.add(angminind, annotation='Min. dorsiflex')
        velr = self.angveld[fmin:fmax]
        velmaxind = np.nanargmax(velr)/self.trial.framerate + tmin_
        self.markers.add(velmaxind, annotation='Max. velocity')
        for ch in self.emg_chs:
            # check if ch is tagged for automark
            if any([s in ch for s in self.emg_automark_chs]):
                rmsdata = self.emg_rms[ch][smin:smax]
                rmsmaxind = np.argmax(rmsdata)/self.trial.analograte + tmin_
                self.markers.add(rmsmaxind, annotation='Max. RMS %s' % ch)

        # init status text
        self._update_status_text()

        plt.show()

    @staticmethod
    def read_starting_angle(vicon):
        subjname = nexus.getsubjectnames()[0]
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
        plt.close(self.fig)

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
        self.fig.canvas.draw()

    def _onpick(self, event):
        mevent = event.mouseevent
        if mevent.button != self.marker_del_button or mevent.key != 'shift':
            return
        self.markers.delete_artist(event.artist, mevent.inaxes)
        self._redraw(mevent.inaxes)  # marker status needs to be updated

    def _onpress(self, event):
        """Keyboard event handler"""
        if event.key == 'tab':
            self._toggle_narrow_callback(event)

    def _onclick(self, event):
        """Mouse click handler"""
        if event.inaxes not in self.data_axes:
            return
        if event.button != self.marker_button or event.key != 'shift':
            return
        x = event.xdata
        self.markers.clicked(x)
        self._redraw(event.inaxes)  # marker status needs to be updated

    def _plot_text(self, s, ypos, color):
        """Plot string s at y position ypos (relative to text frame)"""
        self.texts.append(self.textax.text(0, ypos, s, ha='left', va='top',
                                           transform=self.textax.transAxes,
                                           fontsize=self.text_fontsize,
                                           color=color, wrap=True))

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
        s += u'Note: EMG not delay corrected!\n\n'
        s += u'Trial name: %s\n' % self.trial.trialname
        s += u'EMG passband: %.1f Hz - %.1f Hz\n' % (self.trial.emg.passband)
        s += u'Data range shown: %.2f - %.2f s\n' % (tmin_, tmax_)
        # frame indices corresponding to time limits
        fmin, fmax = self._time_to_frame([tmin_, tmax_], self.trial.framerate)
        if fmin == fmax:
            s += 'Zoomed in to a single frame\nPlease zoom out for info'
            self._plot_text(s, 1, 'k')
            return
        else:
            # analog sample indices ...
            smin, smax = self._time_to_frame([tmin_, tmax_],
                                             self.trial.analograte)
            s += u'In frames: %d - %d\n\n' % (fmin, fmax)
            # foot angle in chosen range and the maximum
            angr = self.angd[fmin:fmax]
            angmax = np.nanmax(angr)
            angmaxind = np.nanargmax(angr)/self.trial.framerate + tmin_
            # same for velocity
            velr = self.angveld[fmin:fmax]
            velmax = np.nanmax(velr)
            velmaxind = np.nanargmax(velr)/self.trial.framerate + tmin_
            s += u'Max. dorsiflexion: %.2f° @ %.2f s\n' % (angmax, angmaxind)
            s += u'Max velocity: %.2f°/s @ %.2f s\n' % (velmax, velmaxind)
            s += u'\nEMG RMS peaks:\n'
            for ch in self.emg_chs:
                rmsdata = self.emg_rms[ch][smin:smax]
                rmsmax = rmsdata.max()
                rmsmaxind = np.argmax(rmsdata)/self.trial.analograte + tmin_
                s += u'%s: %.2f mV @ %.2f s\n' % (ch, rmsmax*1e3, rmsmaxind)
            self._plot_text(s, 1, 'k')
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
                self._plot_text(ms, pos, col)
        self.fig.canvas.draw()


def do_plot(side):
    emg_chs = [side+ch for ch in cfg.tardieu.emg_chs]
    Tardieu_window(emg_chs=emg_chs)


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    register_gui_exception_handler(full_traceback=True)
    do_plot('L')
