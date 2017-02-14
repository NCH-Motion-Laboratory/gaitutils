# -*- coding: utf-8 -*-
"""

Manage config.

@author: Jussi (jnu@iki.fi)
"""

import ConfigParser
import os.path as op
import ast
import defaultconfig
import logging

logger = logging.getLogger(__name__)


class Section(object):
    """ Holds config items for a section """
    pass


class Config(object):
    """ Configuration class for gaitutils. Config values are readable as
    instance attributes or by indexing, but must be set by indexing.

    Uses configparser and auto conversion between string values and Python
    types (based on __repr__ and ast.literal_eval). Values are converted to
    text when saving to file and back to Python expressions when reading.
    Alternative might be to use configobj module.
    """

    def __init__(self, autoread=True):
        self.cfg = defaultconfig.cfg
        self.configfile = defaultconfig.cfg_file
        self.parser = ConfigParser.SafeConfigParser()
        self.parser.optionxform = str  # make it case sensitive
        for section in self.cfg:
            self.parser.add_section(section)
            self.__dict__[section] = Section()  # section  -> instance variable
            # make section vars available as instance variables
            self.__dict__[section].__dict__.update(self.cfg[section])
        if autoread:
            try:
                self.read()
            except ValueError:
                # logging handlers are not installed at this point
                print('Config: no config file, trying to create %s' %
                      self.configfile)
                self.write()

    def read(self):
        """ Read config dict from disk file. """
        if not op.isfile(self.configfile):
            raise ValueError('No config file')
        self.parser.read(self.configfile)
        inifile = open(self.configfile, 'rt')        
        inifile.close()
        for section in self.parser.sections():
            if section not in self.__dict__:
                self.__dict__[section] = Section()
            cfgtxt = self.parser._sections[section]  # dict
            cfg = self._untextify(cfgtxt)  # dict values -> Python types
            self.__dict__[section].__dict__.update(cfg)

    def write(self):
        """ Save current config dict to a disk file. """
        try:
            inifile = open(self.configfile, 'wt')
        except IOError:
            raise ValueError('Cannot open config file for writing')
        for section in self.parser.sections():
            cfgtxt = self._textify(self.__dict__[section].__dict__)
            for key in sorted(cfgtxt):  # keys into file in alphabetical order
                self.parser.set(section, key, cfgtxt[key])
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
