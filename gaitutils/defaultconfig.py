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

""" Video player """
cfg['videoplayer_path'] = 'C:/Program Files (x86)/VideoLAN/VLC/vlc.exe'
cfg['videoplayer_opts'] = '--input-repeat=-1 --rate=.2'

""" EMG settings """
cfg['emg_passband'] = (10, 400)
cfg['linefreq'] = 50
cfg['emg_devname'] = 'Myon'
cfg['emg_yscale'] = (-.5e-3, .5e-3)
cfg['emg_labels'] = {'RHam': 'Medial hamstrings (R)',
                     'RRec': 'Rectus femoris (R)',
                     'RGas': 'Gastrognemius (R)',
                     'RLat_gast': 'Lateral gastrocnemius (R)',
                     'RGlut': 'Gluteus (R)',
                     'RVas': 'Vastus (R)',
                     'RSol': 'Soleus (R)',
                     'RTibA': 'Tibialis anterior (R)',
                     'RPer': 'Peroneus (R)',
                     'LHam': 'Medial hamstrings (L)',
                     'LRec': 'Rectus femoris (L)',
                     'LGas': 'Gastrocnemius (L)',
                     'LLat_gast': 'Lateral gastrocnemius (L)',
                     'LGlut': 'Gluteus (L)',
                     'LVas': 'Vastus (L)',
                     'LSol': 'Soleus (L)',
                     'LTibA': 'Tibialis anterior (L)',
                     'LPer': 'Peroneus (L)'}

cfg['emg_names'] = cfg['emg_labels'].keys()

# EMG "normal bars" (the expected range of activation during gait cycle),
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
cfg['plot_label_fontsize'] = 9
cfg['plot_title_fontsize'] = 12
cfg['plot_ticks_fontsize'] = 10
cfg['plot_inch_per_row'] = 1.5
cfg['plot_inch_per_col'] = 4.5
cfg['plot_titlespace'] = .75
cfg['plot_maxw'] = 20.
cfg['plot_maxh'] = 12.
cfg['plot_analog_plotheight'] = .667
cfg['model_tracecolors'] = {'R': 'lawngreen', 'L': 'red'}
cfg['model_linestyles'] = {'R': '-', 'L': '--'}
cfg['model_linewidth'] = 1.5
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


""" Autoprocessing settings """

cfg['pre_pipelines'] = ['Reconstruct and label (legacy)',
                        'AutoGapFill_mod', 'filter']
cfg['model_pipeline'] = 'Dynamic model + save (LEGACY)'
cfg['trial_open_timeout'] = 45
cfg['pipeline_timeout'] = 45
cfg['save_timeout'] = 100
cfg['type_skip'] = 'Static'
cfg['desc_skip'] = ['Unipedal right', 'Unipedal left', 'Toe standing']
cfg['min_trial_duration'] = 100
cfg['crop_margin'] = 10
cfg['track_markers'] = ['RASI', 'LASI']
cfg['y_midpoint'] = 0
cfg['enf_descriptions'] = {'short': 'short trial', 'context_right': 'o',
                           'context_left': 'v', 'no_context': 'ei kontaktia',
                           'dir_front': 'e', 'dir_back': 't', 'ok': 'ok',
                           'automark_failure': 'not automarked',
                           'gaps': 'gaps',
                           'gaps_or_short': 'gaps or short trial',
                           'label_failure': 'labelling failed'}
cfg['gaps_min_dist'] = 70
cfg['gaps_max'] = 10
cfg['write_eclipse_desc'] = True
cfg['reset_roi'] = True
cfg['check_weight'] = True
cfg['automark_max_dist'] = 2000
cfg['walkway_mid'] = [0, 300, 0]













