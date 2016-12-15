# -*- coding: utf-8 -*-
"""

Manage config.

@author: Jussi (jnu@iki.fi)
"""

from __future__ import print_function
import ConfigParser
import os.path as op
import ast
import defaultconfig


class Config:
    """ Configuration class for gaitutils. Config values are readable as
    instance attributes or by indexing, but must be set by indexing.

    Uses configparser and auto conversion between string values and Python
    types (based on __repr__ and ast.literal_eval). Values are converted to
    text when saving to file and back to Python expressions when reading.
    Alternative might be to use configobj module.
    """

    def __init__(self, autoread=True):
        self.cfg = defaultconfig.cfg
        self.section = 'gaitutils'  # global section identifier
        self.configfile = defaultconfig.cfg_file
        self.parser = ConfigParser.SafeConfigParser()
        self.parser.optionxform = str  # make it case sensitive
        self.parser.add_section(self.section)
        self.__dict__.update(self.cfg)  # default vals -> attributes
        if autoread:
            try:
                self.read()
            except ValueError:
                print('Config: no config file, trying to create %s' %
                      self.configfile)
                self.write()

    def read(self):
        """ Read config dict from disk file. """
        if not op.isfile(self.configfile):
            raise ValueError('No config file')
        self.parser.read(self.configfile)
        cfgtxt = self.parser._sections[self.section]  # dict
        self.cfg = self._untextify(cfgtxt)  # dict values -> Python types
        self.__dict__.update(self.cfg)

    def write(self):
        """ Save current config dict to a disk file. """
        try:
            inifile = open(self.configfile, 'wt')
        except IOError:
            raise ValueError('Cannot open config file for writing')
        cfgtxt = self._textify(self.cfg)  # dict values -> strings
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
