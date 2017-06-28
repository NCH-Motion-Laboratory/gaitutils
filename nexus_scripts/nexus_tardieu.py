# -*- coding: utf-8 -*-
"""

Interactive script for analysis of Tardieu trials.
Work in progress

@author: Jussi (jnu@iki.fi)
"""

from __future__ import print_function
from gaitutils import (EMG, nexus, cfg, read_data, trial, eclipse, models,
                       Trial, Plotter, layouts, utils)
from gaitutils.numutils import segment_angles, rms
from gaitutils.guiutils import messagebox
from collections import OrderedDict
import matplotlib.pyplot as plt
from matplotlib.widgets import Button
import matplotlib.gridspec as gridspec
import sys
import logging
import scipy.linalg
import numpy as np


class Tardieu_window(object):
    """ Open a matplotlib window for Tardieu analysis """

    def __init__(self, emg_chs=None):
        # line markers

        self.marker_button = 1  # mouse button for placing markers
        self.marker_key = 'shift'  # modifier key for markers
        self.m_colors = ['r', 'g', 'b']  # colors for markers
        self.marker_width = 1.5
        self.emg_yrange = [-.5e-3, .5e-3]
        self.width_ratio = [1, 4]
        self.text_fontsize = 9
        self.margin = .025  # margin at edge of plots
        self.narrow = False
        self.hspace = .4
        self.wspace = .4

        # use OrderedDict to remember the order in which the markers were added
        self.markers = OrderedDict()
        self.max_markers = len(self.m_colors)
        self.markers_pos = np.linspace(.75, .6, self.max_markers)
        self.emg_chs = emg_chs
        self.texts = []
        self.data_axes = list()  # axes that actually contain data
        # read data from Nexus and initialize plot
        vicon = nexus.viconnexus()
        # x axis will be same as Nexus (here data is shown starting at frame 0)
        self.trial = Trial(vicon)
        self.time = self.trial.t / self.trial.framerate  # time axis in sec
        self.tmax = self.time[-1]
        self.nframes = len(self.time)
        # read marker data from Nexus
        data = read_data.get_marker_data(vicon, ['Toe', 'Ankle', 'Knee'])
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
            t_, emgdata = self.trial[ch]
            t = t_ / self.trial.analograte
            self.emg_rms[ch] = rms(emgdata, cfg.emg.rms_win)
            sharex = None if ind == 0 else self.data_axes[0]
            ax = plt.subplot(self.gs[ind, 1:], sharex=sharex)
            ax.plot(t, emgdata*1e3)
            ax.plot(t, self.emg_rms[ch]*1e3)
            ax.set_ylim(self.emg_yrange[0]*1e3, self.emg_yrange[1]*1e3)
            ax.set(ylabel='mV')
            ax.set_title(ch)
            self._adj_fonts(ax)
            self.data_axes.append(ax)

        pos = len(emg_chs)
        # add angle plot
        ax = plt.subplot(self.gs[pos, 1:], sharex=self.data_axes[0])
        ax.plot(self.time, self.angd)
        ax.set(ylabel='deg')
        ax.set_title('Angle')
        self._adj_fonts(ax)
        self.data_axes.append(ax)

        # add angular velocity plot
        ax = plt.subplot(self.gs[pos+1, 1:], sharex=self.data_axes[0])
        self.angveld = self.trial.framerate * np.diff(self.angd, axis=0)
        ax.plot(self.time[:-1], self.angveld)
        ax.set(ylabel='deg/s')
        ax.set_title('Angular velocity')
        self._adj_fonts(ax)
        self.data_axes.append(ax)

        # add angular acceleration plot
        ax = plt.subplot(self.gs[pos+2, 1:], sharex=self.data_axes[0])
        self.angaccd = np.diff(self.angveld, axis=0)
        ax.plot(self.time[:-2], self.angaccd)
        ax.set(xlabel='Time (s)', ylabel=u'deg/s²')
        ax.set_title('Angular acceleration')
        self._adj_fonts(ax)
        self.data_axes.append(ax)

        # add text axis spanning the left column
        self.textax = plt.subplot(self.gs[1:, 0])
        self.textax.set_axis_off()

        # refresh text field on zoom
        for ax in self.data_axes:
            ax.callbacks.connect('xlim_changed', self._redraw)
            
        # catch mouse click to add events
        self.fig.canvas.mpl_connect('button_press_event', self._onclick)
        # catch key press
        self.fig.canvas.mpl_connect('key_press_event', self._onpress)

        # adjust plot layout
        self.gs.tight_layout(self.fig)
        self.gs.update(hspace=self.hspace, wspace=self.wspace,
                       left=self.margin, right=1-self.margin)

        # add the 'Clear markers' button
        # axes = left, bottom, width, height
        buttonwidth = .125
        buttonheight = .05
        ax = plt.axes([self.margin, 1-self.margin-buttonheight,
                       buttonwidth, buttonheight])
        self._clearbutton = Button(ax, 'Clear markers')
        self._clearbutton.label.set_fontsize(self.text_fontsize)
        self._clearbutton.on_clicked(self._clear_callback)
        # add the narrow view button
        ax = plt.axes([self.margin, 1-self.margin-2*buttonheight-.025,
                       buttonwidth, buttonheight])
        self._narrowbutton = Button(ax, 'Narrow view')
        self._narrowbutton.label.set_fontsize(self.text_fontsize)
        self._narrowbutton.on_clicked(self._toggle_narrow_callback)

        self.tmin, self.tmax = self.data_axes[0].get_xlim()
        self._update_status_text()
        
        plt.show()
        
        
    @staticmethod
    def read_starting_angle(vicon):
        subjname = vicon.GetSubjectNames()[0]
        asp = vicon.GetSubjectParam(subjname, 'AnkleStartPos')
        return asp[0] if asp[1] else None
        
    @staticmethod
    def _adj_fonts(ax):
        ax.xaxis.label.set_fontsize(cfg.plot.label_fontsize)
        ax.yaxis.label.set_fontsize(cfg.plot.label_fontsize)
        ax.title.set_fontsize(cfg.plot.title_fontsize)
        ax.tick_params(axis='both', which='major',
                       labelsize=cfg.plot.ticks_fontsize)

    def _redraw(self, ax):
        # we need to get the limits from the axis that was zoomed
        # (the limits are not instantly updated by sharex)
        self.tmin, self.tmax = ax.get_xlim()
        self._update_status_text()

    def _clear_callback(self, event):
        for m in self.markers:
            for ax in self.data_axes:
                self.markers[m][ax].remove()
        self.markers.clear()
        self._update_status_text()

    def _toggle_narrow_callback(self, event):
        self.narrow = not self.narrow
        wratios = [1, 1] if self.narrow else self.width_ratio
        btext = 'Wide view' if self.narrow else 'Narrow view'
        self.gs.set_width_ratios(wratios)
        self._narrowbutton.label.set_text(btext)
        self.gs.update()
        self.fig.canvas.draw()

    def _onpress(self, event):
        # keyboard handler
        if event.key == 'tab':
            self._toggle_narrow_callback(event)

    def _onclick(self, event):
        if event.inaxes not in self.data_axes:
            return
        if event.button != self.marker_button or event.key != 'shift':
            return
        if len(self.markers) == self.max_markers:
            messagebox('You can place a maximum of %d markers' %
                       self.max_markers)
            return
        x = event.xdata
        if x not in self.markers:
            col = self.m_colors[len(self.markers)]  # pick next available color
            self.markers[x] = dict()
            for ax in self.data_axes:
                self.markers[x][ax] = ax.axvline(x=x, color=col,
                                                 linewidth=self.marker_width)
            self._redraw(event.inaxes)

    def _time_to_frame(self, times, rate):
        # convert time to frames or analog frames (according to rate)
        return np.round(rate * np.array(times)).astype(int)

    def _plot_text(self, s, ypos, color):
        self.texts.append(self.textax.text(0, ypos, s, ha='left', va='top',
                                           transform=self.textax.transAxes,
                                           fontsize=self.text_fontsize,
                                           color=color, wrap=True))

    def _update_status_text(self):
        if self.texts:
            [txt.remove() for txt in self.texts]
            self.texts = []
        # find the limits of the data that is shown
        tmin_ = max(self.time[0], self.tmin)
        tmax_ = min(self.time[-1], self.tmax)
        s = u'Note: EMG not delay corrected!\n\n'
        s += u'Data range shown: %.2f - %.2f s\n' % (tmin_, tmax_)
        # frame indices corresponding to time limits
        fmin, fmax = self._time_to_frame([tmin_, tmax_], self.trial.framerate)
        if fmin == fmax:
            s += 'Zoomed in to a single frame\nPlease zoom out for info'
            self._plot_text(s, 1, 'k')
            return
        else:
            # analog sample indices ...
            smin, smax = self._time_to_frame([tmin_, tmax_], self.trial.analograte)
            s += u'In frames: %d - %d\n' % (fmin, fmax)
            # foot angle in chosen range and the maximum
            angr = self.angd[fmin:fmax]
            angmax, angmaxind = np.nanmax(angr), np.nanargmax(angr)/self.trial.framerate + tmin_
            # same for velocity
            velr = self.angveld[fmin:fmax]
            velmax, velmaxind = np.nanmax(velr), np.nanargmax(velr)/self.trial.framerate + tmin_
            s += u'Max angle: %.2f °/s @ %.2f s\n' % (angmax, angmaxind)
            s += u'Max velocity: %.2f °/s @ %.2f s\n' % (velmax, velmaxind)
    
            s += u'\nEMG RMS peaks:\n'
            for ch in self.emg_chs:
                rms = self.emg_rms[ch][smin:smax]
                rmsmax, rmsmaxind = rms.max(), np.argmax(rms)/self.trial.analograte + tmin_
                s += u'%s: %.2f mV @ %.2f s\n' % (ch, rmsmax*1e3, rmsmaxind)
            self._plot_text(s, 1, 'k')
            # annotate markers
            for marker, pos, col in zip(self.markers, self.markers_pos,
                                        self.m_colors):
                frame = self._time_to_frame(marker, self.trial.framerate)
                if frame < 0 or frame >= self.nframes:
                    ms = u'Marker outside data range'
                else:
                    ms = u'marker @%.2f s:\npos %.2f° vel %.2f°/s acc %.2f°/s²\n\n' % (marker, self.angd[frame], self.angveld[frame], self.angaccd[frame])
                self._plot_text(ms, pos, col)

        self.fig.canvas.draw()


def do_plot(side):
    emg_chs = [side+ch for ch in cfg.tardieu.emg_chs]
    Tardieu_window(emg_chs=emg_chs)

if __name__ == '__main__':
    do_plot('L')
