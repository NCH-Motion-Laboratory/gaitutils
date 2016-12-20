# -*- coding: utf-8 -*-
"""
Default config for gaitutils. Will be overwritten by updates - do not edit.
Edit the user specific config file instead (location given by cfg_file below)


@author: Jussi (jnu@iki.fi)
"""

import os.path as op

cfg = dict()

# location of user specific config file
pathprefix = op.expanduser('~')
appdir = pathprefix + '/.gaitutils'
cfg_file = appdir + '/gaitutils.cfg'


""" These variables will be written out into config file. """

""" Nexus installation """
cfg['nexus_ver'] = "2.5"
cfg['vicon_path'] = "C:/Program Files (x86)/Vicon"
cfg['nexus_path'] = cfg['vicon_path'] + '/Nexus' + cfg['nexus_ver']

""" Plug-in Gait normal data """
cfg['pig_normaldata_path'] = appdir + '/Data/normal.gcd'

""" EMG settings """
cfg['emg_lowpass'] = 400
cfg['emg_highpass'] = 10
cfg['emg_devname'] = 'Myon'
cfg['emg_yscale'] = (-.5e-3, .5e-3)
cfg['emg_labels'] = {'RHam': 'Medial hamstrings (R)',
                     'RRec': 'Rectus femoris (R)',
                     'RGas': 'Gastrognemius (R)',
                     'RGlut': 'Gluteus (R)',
                     'RVas': 'Vastus (R)',
                     'RSol': 'Soleus (R)',
                     'RTibA': 'Tibialis anterior (R)',
                     'RPer': 'Peroneus (R)',
                     'LHam': 'Medial hamstrings (L)',
                     'LRec': 'Rectus femoris (L)',
                     'LGas': 'Gastrognemius (L)',
                     'LGlut': 'Gluteus (L)',
                     'LVas': 'Vastus (L)',
                     'LSol': 'Soleus (L)',
                     'LTibA': 'Tibialis anterior (L)',
                     'LPer': 'Peroneus (L)'}

cfg['emg_names'] = cfg['emg_labels'].keys()

# EMG normal bars (the expected range of activation during gait cycle),
# axis is 0..100%
cfg['emg_normals'] = {'RGas': [[16, 50]],
                      'RGlut': [[0, 42], [96, 100]],
                      'RHam': [[0, 2], [92, 100]],
                      'RPer': [[4, 54]],
                      'RRec': [[0, 14], [56, 100]],
                      'RSol': [[10, 54]],
                      'RTibA': [[0, 12], [56, 100]],
                      'RVas': [[0, 24], [96, 100]],
                      'LGas': [[16, 50]],
                      'LGlut': [[0, 42], [96, 100]],
                      'LHam': [[0, 2], [92, 100]],
                      'LPer': [[4, 54]],
                      'LRec': [[0, 14], [56, 100]],
                      'LSol': [[10, 54]],
                      'LTibA': [[0, 12], [56, 100]],
                      'LVas': [[0, 24], [96, 100]]}


""" Plotting related settings """
cfg['plot_label_fontsize'] = 10
cfg['plot_title_fontsize'] = 12
cfg['plot_ticks_fontsize'] = 10
cfg['plot_totalfigsize'] = (14, 12)
cfg['model_tracecolors'] = {'R': 'lawngreen', 'L': 'red'}
cfg['model_linewidth'] = 1
cfg['model_normals_alpha'] = .3
cfg['model_normals_color'] = 'gray'
cfg['emg_tracecolor'] = 'black'
cfg['emg_linewidth'] = .5
cfg['emg_ylabel'] = 'mV'
cfg['emg_multiplier'] = 1e3
cfg['emg_normals_alpha'] = .8
cfg['emg_alpha'] = .6
cfg['emg_normals_color'] = 'pink'
cfg['emg_ylabel'] = 'mV'
