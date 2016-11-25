# -*- coding: utf-8 -*-
"""

Manage config for hpimon.

@author: Jussi (jnu@iki.fi)
"""

from __future__ import print_function
import ConfigParser
import os.path as op
import ast


class Config:
    """ Configuration class for gaitutils. Config values are readable as
    instance attributes or by indexing, but must be set by indexing.
    """

    """ Default config """
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

    def __init__(self, autoread=True):
        self.cfg = Config.cfg.copy()
        self.section = 'gaitutils'  # global section identifier
        self.configfile = op.expanduser('~') + '/gaitutils.cfg'
        self.parser = ConfigParser.SafeConfigParser()
        self.parser.optionxform = str  # make it case sensitive
        self.parser.add_section(self.section)
        self.__dict__.update(self.cfg)  # default vals -> attributes
        if autoread:
            try:
                self.read()
            except ValueError:
                print('Config: no config file, creating a default one')
                self.write()

    def read(self):
        """ Read config dict from disk file. """
        if not op.isfile(self.configfile):
            raise ValueError('No config file')
        print('Config: reading from %s' % self.configfile)
        self.parser.read(self.configfile)
        cfgtxt = self.parser._sections[self.section]  # dict
        self.cfg = self._untextify(cfgtxt)
        self.__dict__.update(self.cfg)

    def write(self):
        """ Save current config dict to a disk file. """
        try:
            inifile = open(self.configfile, 'wt')
        except IOError:
            raise ValueError('Cannot open config file for writing')
        cfgtxt = self._textify(self.cfg)
        for key in sorted(cfgtxt):  # put keys into file in alphabetical order
            self.parser.set(self.section, key, cfgtxt[key])
        self.parser.write(inifile)
        inifile.close()

    def __getitem__(self, key):
        return self.cfg[key]

    def __setitem__(self, key, val):
        self.cfg[key] = val
        self.__dict__.update(self.cfg)

    @staticmethod
    def _textify(di):
        """ Converts dict values into textual representations """
        return {key: val.__repr__() for key, val in di.items()}

    @staticmethod
    def _untextify(di):
        """ Converts textual dict values into Python types """
        return {key: ast.literal_eval(val) for key, val in di.items()}
