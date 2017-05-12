# -*- coding: utf-8 -*-
"""

Interactive script for analysis of Tardieu trials.
Work in progress

@author: HUS20664877
"""

from __future__ import print_function
from gaitutils import (EMG, nexus, cfg, read_data, trial, eclipse, models,
                       Plotter, layouts, utils)
from gaitutils.numutils import segment_angles, rms
from gaitutils.guiutils import messagebox
import matplotlib.pyplot as plt
from matplotlib.widgets import SpanSelector, Button
import sys
import logging
import scipy.linalg
import numpy as np
import btk




class Tardieu_window(object):
    """ Open a matplotlib window for Tardieu analysis """

    def __init__(self, emg_chs=None):
        # line markers
        self.markers = dict()
        self.marker_button = 3  # mouse button for markers
        self.m_colors = ['r', 'g', 'b']  # colors for markers
        self.max_markers = len(self.m_colors)
        self.emg_chs = emg_chs
        self.clear_button_ax = [.8, .95, .15, .05]
        self.width_ratio = [1, 3]
        self.text = ''

    def show(self):
        vicon = nexus.viconnexus()
        # plot EMG vs. frames
        # x axis will be same as Nexus (here data is shown starting at frame 0)
        pl = Plotter()
        pl.layout = [[None, ch] for ch in self.emg_chs] + [[None, None], [None, None], [None, None]]
        pl.open_nexus_trial()
        fs = pl.trial.framerate
        pl.plot_trial(model_cycles=None, emg_cycles=None, x_axis_is_time=True,
                      plot_emg_rms=True, emg_tracecolor='b', sharex=True,
                      plotwidthratios=self.width_ratio, show=False)
        self.pl = pl
        # read marker data from Nexus
        data = read_data.get_marker_data(vicon, ['Toe', 'Ankle', 'Knee'])
        Ptoe = data['Toe_P']
        Pank = data['Ankle_P']
        Pknee = data['Knee_P']
        # stack so that marker changes along 2nd dim for segment_angles
        Pall = np.stack([Ptoe, Pank, Pknee], axis=1)
        # compute segment angles (deg)
        angd = segment_angles(Pall) / np.pi * 180

        # read events
        # evs = vicon.GetEvents('4-511', 'General', 'MuscleOn')[0]

        # compute EMG RMS
        emg_rms = dict()
        for ch in emg_chs:
            x, data = pl.trial[ch]
            emg_rms[ch] = rms(data, cfg.emg.rms_win)

        # add angle plot
        pos = len(emg_chs)
        ax = plt.subplot(pl.gridspec[pos, 1], sharex=pl.axes[0])
        ax.plot(pl.trial.t / fs, angd)
        ax.set(ylabel='Angle (deg)')
        ax.set_title('Angle')
        self._adj_fonts(ax)

        # add angular velocity plot
        ax = plt.subplot(pl.gridspec[pos+1, 1], sharex=pl.axes[0])
        angveld = fs * np.diff(angd, axis=0)
        ax.plot(pl.trial.t[:-1] / fs, angveld)
        ax.set(ylabel='Velocity (deg/s)')
        ax.set_title('Angular velocity')
        self._adj_fonts(ax)

        # add angular acceleration plot
        ax = plt.subplot(pl.gridspec[pos+2, 1], sharex=pl.axes[0])
        angaccd = np.diff(angveld, axis=0)
        ax.plot(pl.trial.t[:-2] / fs, angaccd)
        ax.set(xlabel='Time (s)', ylabel='Acceleration (deg/s^2)')
        ax.set_title('Angular acceleration')
        self._adj_fonts(ax)

        # save axes at this point
        self.allaxes = pl.fig.get_axes()

        self.textax = plt.subplot(pl.gridspec[:, 0])
        self.textax.set_axis_off()


        # add the span selector to all axes
        """
        spans = []
        for ax in self.allaxes:
            span = SpanSelector(ax, self._onselect, 'horizontal', useblit=True,
                                button=1,
                                rectprops=dict(alpha=0.5, facecolor='red'))
            spans.append(span)  # keep reference
        """

        pl.fig.canvas.mpl_connect('button_press_event',
                                  lambda ev: self._onclick(ev))
        pl.tight_layout()

        # add the 'Clear markers' button
        ax = plt.axes(self.clear_button_ax)
        self._clearbutton = Button(ax, 'Clear markers')
        self._clearbutton.on_clicked(lambda ev: self._bclick(ev))

        self.set_text('Moikka\nKaikenlaista')

        plt.show()

    def set_text(self, text):
        self.text = self.textax.text(0, 1, text,
                                     transform=self.textax.transAxes)

    def rm_text(self):
        self.text.remove()

    @staticmethod
    def _adj_fonts(ax):
        ax.xaxis.label.set_fontsize(cfg.plot.label_fontsize)
        ax.yaxis.label.set_fontsize(cfg.plot.label_fontsize)
        ax.title.set_fontsize(cfg.plot.title_fontsize)
        ax.tick_params(axis='both', which='major',
                       labelsize=cfg.plot.ticks_fontsize)

    def _bclick(self, event):
        for m in self.markers:
            for ax in self.allaxes:
                self.markers[m][ax].remove()
        self.markers.clear()
        self.pl.fig.canvas.draw()

    def _onclick(self, event):
        if event.inaxes not in self.allaxes:
            return
        if event.button != self.marker_button:
            return
        if len(self.markers) == self.max_markers:
            messagebox('You can place a maximum of %d markers' %
                       self.max_markers)
            return
        x = event.xdata
        if x not in self.markers:
            col = self.m_colors[len(self.markers)]
            self.markers[x] = dict()
            for ax in self.allaxes:
                self.markers[x][ax] = ax.axvline(x=x, linewidth=1, color=col)
            self.pl.fig.canvas.draw()



"""
    @staticmethod
    def _onselect(xmin_, xmax_):
        xmin, xmax = np.round([xmin_, xmax_]).astype(int)
        # velocity
        velr = abs(angveld[xmin:xmax])
        velmax, velmaxind = velr.max(), np.argmax(velr) + xmin
        # foot angle
        angr = angd[xmin:xmax]
        angmax, angmaxind = angr.max(), np.argmax(angr) + xmin
        s = ''
        s += 'Selected range\t\t%d-%d\n' % (xmin, xmax)
        s += 'Max velocity\t\t%.2f deg/s @ frame %d\n' % (velmax, velmaxind)
        s += 'Max angle\t\t\t%.2f deg @ frame %d\n' % (angmax, angmaxind)
        s += '\nMax RMS in given range:\n'
        for ch in emg_chs:
            smin, smax = (pl.trial.samplesperframe*np.round([xmin_, xmax_])).astype(int)
            rms = emg_rms[ch][smin:smax]
            rmsmax, rmsmaxind = rms.max(), int(np.round((np.argmax(rms) + smin)/pl.trial.samplesperframe))
            s += '%s\t\t\t%g mV @ frame %d\n' % (ch, rmsmax*1e3, rmsmaxind)
        s += '\nMarkers:\n' if events else ''
        for event in events:
            if xmin_ < event < xmax_:
                s += 'Ankle angle at marker %d: %.2f deg\n' % (event, angd[event])
        messagebox(s, title='Info')
"""


# EMG channels of interest
emg_chs = ['L_Gastr', 'L_Sol', 'L_TibAnt']

if __name__ == '__main__':
    t = Tardieu_window(emg_chs=emg_chs)
    t.show()
    





