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

# EMG channels of interest
emg_chs = ['L_Gastr', 'L_Sol', 'L_TibAnt']



def _adj_fonts(ax):
    ax.xaxis.label.set_fontsize(cfg.plot.label_fontsize)
    ax.yaxis.label.set_fontsize(cfg.plot.label_fontsize)
    ax.title.set_fontsize(cfg.plot.title_fontsize)
    ax.tick_params(axis='both', which='major',
                   labelsize=cfg.plot.ticks_fontsize)

vicon = nexus.viconnexus()

# plot EMG vs. frames
# x axis will be same as Nexus (here data is plotted starting at frame 0)
pl = Plotter()
pl.layout = [[ch] for ch in emg_chs] + [[None], [None], [None]]
pl.open_nexus_trial()
fs = pl.trial.framerate
pl.plot_trial(model_cycles=None, emg_cycles=None, x_axis_is_time=True,
              plot_emg_rms=True, emg_tracecolor='b', sharex=True, show=False)

# get marker data
data = read_data.get_marker_data(vicon, ['Toe', 'Ankle', 'Knee'])
Ptoe = data['Toe_P']
Pank = data['Ankle_P']
Pknee = data['Knee_P']
# stack so that marker changes along 2nd dim, as req'd by segment_angles
Pall = np.stack([Ptoe, Pank, Pknee], axis=1)
# compute segment angles (deg)
angd = segment_angles(Pall) / np.pi * 180

# normalize according to initial pos
# ang -= ang[~np.isnan(ang)][0]
# plot angular velocity -> deg/s


# plot angle
pos = len(emg_chs)
ax = plt.subplot(pl.gridspec[pos], sharex=pl.axes[0])
ax.plot(pl.trial.t / fs, angd)
ax.set(ylabel='Angle (deg)')
ax.set_title('Angle')
_adj_fonts(ax)

# plot angular velocity
ax = plt.subplot(pl.gridspec[pos+1], sharex=pl.axes[0])
angveld = fs * np.diff(angd, axis=0)
ax.plot(pl.trial.t[:-1] / fs, angveld)
ax.set(ylabel='Velocity (deg/s)')
ax.set_title('Angular velocity')
_adj_fonts(ax)

# plot angular acceleration
ax = plt.subplot(pl.gridspec[pos+2], sharex=pl.axes[0])
angaccd = np.diff(angveld, axis=0)
ax.plot(pl.trial.t[:-2] / fs, angaccd)
ax.set(xlabel='Time (s)', ylabel='Acceleration (deg/s^2)')
ax.set_title('Angular acceleration')
_adj_fonts(ax)


# read events
evs = vicon.GetEvents('4-511', 'General', 'MuscleOn')[0]

#  for ax in pl.fig.get_axes()[:2]:
#    for ev in evs:
#        ax.plot(ev, 0, 'k^')

# compute RMS
emg_rms = dict()
for ch in emg_chs:
    x, data = pl.trial[ch]
    emg_rms[ch] = rms(data, cfg.emg.rms_win)


def _onselect(xmin_, xmax_):
    """ Callback: analyze given range """
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
    velmaxang = angd[velmaxind]
    maxmang = angd.max()
    rmsmaxind = np.argmax(rms)
    # TODO: find events in this range, raport corresponding angles
    """

allaxes = pl.fig.get_axes()

# add span selector to all axes
spans = []
for ax in allaxes:
    span = SpanSelector(ax, _onselect, 'horizontal', useblit=True, button=1,
                        rectprops=dict(alpha=0.5, facecolor='red'))
    spans.append(span)  # keep reference


# line markers 
markers = dict()


def bclick(event):
    for m in markers:
        for ax in allaxes:
            markers[m][ax].remove()
    markers.clear()
    pl.fig.canvas.draw()


def onclick(event):
    if event.button != 3:
        return
    x = int(np.round(event.xdata))
    if x not in markers:
        markers[x] = dict()
        for ax in allaxes:
            li = ax.axvline(x=event.xdata, linewidth=1, color='k')
            markers[x][ax] = li
    pl.fig.canvas.draw()

cid = pl.fig.canvas.mpl_connect('button_press_event', onclick)

pl.tight_layout()

ax = plt.axes([0.7, 0.9, 0.25, 0.05])
bkoe = Button(ax, 'Clear markers')
bkoe.on_clicked(bclick)

plt.show()