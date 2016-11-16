# -*- coding: utf-8 -*-
"""
Created on Wed Jun 03 15:41:41 2015

Lab -specific stuff (electrode names etc.)

@author: Jussi
"""

import os.path as op


emg_lowpass = '400'
emg_highpass = '10'


# Version should be bumped on Nexus update to get the latest API
NEXUS_VER = "2.5"
NEXUS_PATH = "C:/Program Files (x86)/Vicon/"
NEXUS_PATH += 'Nexus'
NEXUS_PATH += NEXUS_VER

# App dir contains the config file and normal data
pathprefix = op.expanduser('~')
appdir = pathprefix + '/.gaitutils'

# Plug-in Gait normal data
pig_normaldata_path = appdir + '/Data/normal.gcd'

# EMG device name
emg_devname = 'Myon'

# EMG y scale for plotting
emg_yscale = .5e-3

# default bandpass values for EMG
emg_lowpass = '400'
emg_highpass = '10'


# EMG electrode names and descriptions
emg_labels = {'RHam': 'Medial hamstrings (R)',
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
emg_normals = {'RGas': [[16, 50]],
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

# put names into a separate variable
emg_names = emg_labels.keys()
