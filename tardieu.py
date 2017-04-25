# -*- coding: utf-8 -*-
"""

Test Tardieu analysis

@author: HUS20664877
"""

from gaitutils import (EMG, nexus, cfg, read_data, trial, eclipse, models,
                       Plotter, layouts, utils)
from gaitutils.numutils import segment_angles
import matplotlib.pyplot as plt
import sys
import logging
import scipy.linalg
import numpy as np
import btk


pl = Plotter()
pl.layout = [['L_TibAnt']]
pl.open_nexus_trial()
pl.plot_trial(model_cycles=None, emg_cycles=None)

sys.exit()



# time varying segment angle
vicon = nexus.viconnexus()
data = read_data.get_marker_data(vicon, ['Toe', 'Ankle', 'Knee'])
Ptoe = data['Toe_P']
Pank = data['Ankle_P']
Pknee = data['Knee_P']
# stack so that marker changes along 2nd dim, as req'd by segment_angles
Pall = np.stack([Ptoe, Pank, Pknee], axis=1)

# segment angles (deg)
ang = segment_angles(Pall)
plt.plot(ang / np.pi * 180)

# compute angular velocity -> deg/s
frate = read_data.get_metadata(vicon)['framerate']
angd = frate * np.diff(ang, axis=0)
#plt.plot(angd / np.pi * 180)

# read events
evs = vicon.GetEvents('4-511', 'General', 'MuscleOn')[0]

tr = trial.Trial(vicon)




