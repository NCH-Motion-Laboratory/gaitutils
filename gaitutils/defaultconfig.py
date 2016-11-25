# -*- coding: utf-8 -*-
"""
Default config for gaitutils. Will be overwritten by updates - do not edit.

@author: Jussi (jnu@iki.fi)
"""

cfg = dict()
cfg['emg_lowpass'] = 400
cfg['emg_highpass'] = 10
cfg['emg_devname'] = 'Myon'
cfg['nexus_ver'] = "2.5"
cfg['nexus_path'] = "C:/Program Files (x86)/Vicon/"
cfg['emg_yscale'] = "(-.5e-3, .5e-3)"

# EMG electrode names and descriptions
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

cfg['label_fontsize'] = 10
cfg['title_fontsize'] = 12
cfg['ticks_fontsize'] = 10
cfg['totalfigsize'] = "(14, 12)"
cfg['model_tracecolors'] = {'R': 'lawngreen', 'L': 'red'}
cfg['normals_alpha'] = .3
cfg['normals_color'] = 'gray'
cfg['emg_tracecolor'] = 'black'
cfg['emg_ylabel'] = 'mV'
cfg['emg_multiplier'] = 1e3
cfg['emg_normals_alpha'] = .8
cfg['emg_alpha'] = .6
cfg['emg_normals_color'] = 'pink'
cfg['emg_ylabel'] = 'mV'
