# -*- coding: utf-8 -*-
"""
Default config for gaitutils. Will be overwritten by updates - do not edit.
Edit the user specific config file instead (location given by cfg_file below)


@author: Jussi (jnu@iki.fi)
"""

import os.path as op

cfg = dict()

# location of user specific config file
homedir = op.expanduser('~')
cfg_file = homedir + '/.gaitutils.cfg'


""" These variables will be written out into config file. """

cfg['general'] = dict()
""" Nexus installation """
cfg['general']['nexus_ver'] = "2.5"
cfg['general']['vicon_path'] = "C:/Program Files (x86)/Vicon"
cfg['general']['nexus_path'] = cfg['general']['vicon_path'] + '/Nexus' + cfg['general']['nexus_ver']
""" Plug-in Gait normal data """
cfg['general']['pig_normaldata_path'] = homedir + '/Data/normal.gcd'
""" Video player """
cfg['general']['videoplayer_path'] = 'C:/Program Files (x86)/VideoLAN/VLC/vlc.exe'
cfg['general']['videoplayer_opts'] = '--input-repeat=-1 --rate=.2'



""" EMG settings """
cfg['emg'] = dict()
cfg['emg']['emg_passband'] = (10, 400)
cfg['emg']['linefreq'] = 50
cfg['emg']['emg_devname'] = 'Myon'
cfg['emg']['emg_yscale'] = (-.5e-3, .5e-3)
cfg['emg']['emg_labels'] = {'RHam': 'Medial hamstrings (R)',
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

cfg['emg']['emg_names'] = cfg['emg']['emg_labels'].keys()

# EMG "normal bars" (the expected range of activation during gait cycle),
# axis is 0..100%
cfg['emg']['emg_normals'] = {'RGas': [[16, 50]],
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
cfg['plotting'] = dict()
cfg['plotting']['plot_label_fontsize'] = 9
cfg['plotting']['plot_title_fontsize'] = 12
cfg['plotting']['plot_ticks_fontsize'] = 10
cfg['plotting']['plot_inch_per_row'] = 1.5
cfg['plotting']['plot_inch_per_col'] = 4.5
cfg['plotting']['plot_titlespace'] = .75
cfg['plotting']['plot_maxw'] = 20.
cfg['plotting']['plot_maxh'] = 12.
cfg['plotting']['plot_analog_plotheight'] = .667
cfg['plotting']['model_tracecolors'] = {'R': 'lawngreen', 'L': 'red'}
cfg['plotting']['model_linestyles'] = {'R': '-', 'L': '--'}
cfg['plotting']['model_linewidth'] = 1.5
cfg['plotting']['model_normals_alpha'] = .3
cfg['plotting']['model_normals_color'] = 'gray'
cfg['plotting']['emg_tracecolor'] = 'black'
cfg['plotting']['emg_linewidth'] = .5
cfg['plotting']['emg_ylabel'] = 'mV'
cfg['plotting']['emg_multiplier'] = 1e3
cfg['plotting']['emg_normals_alpha'] = .8
cfg['plotting']['emg_alpha'] = .6
cfg['plotting']['emg_normals_color'] = 'pink'
cfg['plotting']['emg_ylabel'] = 'mV'


""" Autoprocessing settings """

cfg['autoproc'] = dict()
cfg['autoproc']['pre_pipelines'] = ['Reconstruct and label (legacy)',
                        'AutoGapFill_mod', 'filter']
cfg['autoproc']['model_pipeline'] = 'Dynamic model + save (LEGACY)'
cfg['autoproc']['trial_open_timeout'] = 45
cfg['autoproc']['pipeline_timeout'] = 45
cfg['autoproc']['save_timeout'] = 100
cfg['autoproc']['type_skip'] = 'Static'
cfg['autoproc']['desc_skip'] = ['Unipedal right', 'Unipedal left', 'Toe standing']
cfg['autoproc']['min_trial_duration'] = 100
cfg['autoproc']['crop_margin'] = 10
cfg['autoproc']['track_markers'] = ['RASI', 'LASI']
cfg['autoproc']['y_midpoint'] = 0
cfg['autoproc']['enf_descriptions'] = {'short': 'short trial', 'context_right': 'o',
                           'context_left': 'v', 'no_context': 'ei kontaktia',
                           'dir_front': 'e', 'dir_back': 't', 'ok': 'ok',
                           'automark_failure': 'not automarked',
                           'gaps': 'gaps',
                           'gaps_or_short': 'gaps or short trial',
                           'label_failure': 'labelling failed'}
cfg['autoproc']['gaps_min_dist'] = 70
cfg['autoproc']['gaps_max'] = 10
cfg['autoproc']['write_eclipse_desc'] = True
cfg['autoproc']['reset_roi'] = True
cfg['autoproc']['check_weight'] = True
cfg['autoproc']['automark_max_dist'] = 2000
cfg['autoproc']['walkway_mid'] = [0, 300, 0]





