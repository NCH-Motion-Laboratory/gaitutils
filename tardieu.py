# -*- coding: utf-8 -*-
"""

Test Tardieu analysis

@author: HUS20664877
"""

from gaitutils import (EMG, nexus, cfg, read_data, trial, eclipse, models,
                       Plotter, layouts, utils)
from gaitutils.numutils import segment_angles, rms
import matplotlib.pyplot as plt
import sys
import logging
import scipy.linalg
import numpy as np
import btk


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
pl.layout = [['L_Gastr'], ['L_TibAnt'], [None], [None]]
pl.open_nexus_trial()
pl.plot_trial(model_cycles=None, emg_cycles=None, x_axis_is_time=False,
              plot_emg_rms=True, emg_tracecolor='b', sharex=True)


sys.exit()


# get marker data
data = read_data.get_marker_data(vicon, ['Toe', 'Ankle', 'Knee'])
Ptoe = data['Toe_P']
Pank = data['Ankle_P']
Pknee = data['Knee_P']
# stack so that marker changes along 2nd dim, as req'd by segment_angles
Pall = np.stack([Ptoe, Pank, Pknee], axis=1)
# compute segment angles (deg)
ang = segment_angles(Pall)
# normalize according to initial pos
# ang -= ang[~np.isnan(ang)][0]
ang = -ang
# plot angular velocity -> deg/s
angd = pl.trial.framerate * np.diff(ang, axis=0)

# plot angle
ax = plt.subplot(pl.gridspec[2], sharex=pl.axes[0])
ax.plot(pl.trial.t, ang / np.pi * 180)
ax.set(ylabel='deg')
ax.set_title('Angle')
_adj_fonts(ax)

# plot angular velocity
ax = plt.subplot(pl.gridspec[3], sharex=pl.axes[0])
ax.plot(pl.trial.t[:-1], angd / np.pi * 180)
ax.set(xlabel='Frame', ylabel='deg/s')
ax.set_title('Angular velocity')
_adj_fonts(ax)

# read events
evs = vicon.GetEvents('4-511', 'General', 'MuscleOn')[0]
for ax in pl.fig.get_axes():
    for ev in evs:
        ax.plot(ev, 0, 'k^')

# find peak RMS
x, data = pl.trial['L_TibAnt']
emg_rms = rms(data, cfg.emg.rms_win)
max_fr_ = np.round(np.argmax(emg_rms) / pl.trial.samplesperframe)



