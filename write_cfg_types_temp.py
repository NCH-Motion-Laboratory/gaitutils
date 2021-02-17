# %% init


"""
NOTE:
-plotting from Noraxon may fail due to low amplitudes (autobad)
-should really annotate bad EMG


"""


import gaitutils
from gaitutils import nexus, emg, cfg, numutils, trial
from gaitutils.viz import plots, plot_misc
import matplotlib.pyplot as plt
import logging


logging.basicConfig(level=logging.DEBUG)

vicon = nexus.viconnexus()


cfg.emg.devname = 'Noraxon Ultium'
cfg.emg.autodetect_bads = False


for k in range(16):
    cfg.emg.channel_labels['EMG%d' % k] = 'EMG%d' % k

cfg.emg.passband = [200, 400]


emg = emg.EMG(vicon)

tr = trial.Trial(vicon)

fig = plots.plot_trials(tr, layout_name='noraxon', cycles='unnormalized')

plot_misc.show_fig(fig)

# plots.plot_trials(tr, layout_name='noraxon', cycles='unnormalized', backend='matplotlib')


# %% foo

emgdata = emg.data['v'][:1000]


emgdata_filt = numutils._filtfilt(emgdata, [100, 400], 2000)


plt.plot(emgdata)
