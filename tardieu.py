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


vicon = nexus.viconnexus()

# plot EMG vs. frames
pl = Plotter()
pl.layout = [['L_TibAnt'], [None], [None]]
pl.open_nexus_trial()
pl.plot_trial(model_cycles=None, emg_cycles=None, x_axis_is_time=False,
              plot_emg_rms=True)

# get marker data
fs = pl.trial.framerate
data = read_data.get_marker_data(vicon, ['Toe', 'Ankle', 'Knee'])
Ptoe = data['Toe_P']
Pank = data['Ankle_P']
Pknee = data['Knee_P']
# stack so that marker changes along 2nd dim, as req'd by segment_angles
Pall = np.stack([Ptoe, Pank, Pknee], axis=1)
# compute segment angles (deg)
ang = segment_angles(Pall)

# angle
ax = plt.subplot(pl.gridspec[1], sharex=pl.axes[0])
ax.plot(pl.trial.t+pl.trial.offset, ang / np.pi * 180)
ax.set(ylabel='Angle (deg)')
ax.xaxis.label.set_fontsize(cfg.plot.label_fontsize)
ax.yaxis.label.set_fontsize(cfg.plot.label_fontsize)
ax.tick_params(axis='both', which='major', labelsize=cfg.plot.ticks_fontsize)

# angular velocity -> deg/s
angd = fs * np.diff(ang, axis=0)
ax = plt.subplot(pl.gridspec[2], sharex=pl.axes[0])
ax.plot(pl.trial.t[:-1]+pl.trial.offset, angd / np.pi * 180)
ax.set(xlabel='Frame', ylabel='Angular velocity (deg/s)')
ax.xaxis.label.set_fontsize(cfg.plot.label_fontsize)
ax.yaxis.label.set_fontsize(cfg.plot.label_fontsize)
ax.tick_params(axis='both', which='major', labelsize=cfg.plot.ticks_fontsize)

# read events
evs = vicon.GetEvents('4-511', 'General', 'MuscleOn')[0]
for ax in pl.fig.get_axes():
    for ev in evs:
        ax.plot(ev, 0, 'k^')

# find peak RMS
x, data = pl.trial['L_TibAnt']
emg_rms = rms(data, cfg.emg.rms_win)
max_fr_ = np.round(np.argmax(emg_rms) / pl.trial.samplesperframe)










