# -*- coding: utf-8 -*-
"""
Created on Wed Feb 15 13:14:16 2017

@author: hus20664877
"""


import ConfigParser
import ast
import os.path as op
from pkg_resources import resource_filename


# default config
cfg_template = resource_filename(__name__, 'default.cfg')
# user specific config
homedir = op.expanduser('~')
cfg_user = homedir + '/.gaitutils.cfg'


class Section(object):
    """ Holds data for sections """
    pass


class ExtConfigParser(object):
    """ Extends SafeConfigParser by:
    1) providing attribute access as extconfigparser.section.item
    2) attributes (as above) are stored as Python types, with autoconversion by
    the ast module
    """

    def __init__(self, cfg_template, cfg_user):
        self._parser = ConfigParser.SafeConfigParser()
        self._read(cfg_template)
        try:
            self._read(cfg_user)
        except IOError:
            print('no config file, trying to create %s' % cfg_user)
            self._write(cfg_user)

    def _read(self, file):
        if not op.isfile(file):
            raise IOError('Config file does not exist')
        self._parser.read(file)
        for section in self._parser.sections():
            if section[0] == '_':  # don't allow underscores (protect members)
                raise ValueError('Illegal section name: %s' % section)
            if section not in self.__dict__:
                self.__dict__[section] = Section()
            cfgtxt = self._parser._sections[section]
            cfg = self._untextify(cfgtxt)
            self.__dict__[section].__dict__.update(cfg)

    def _write(self, file):
        cfg = open(file, 'wt')
        self._parser.write(cfg)
        cfg.close()

    @staticmethod
    def _untextify(di):
        """ Converts textual dict values into Python types """
        return {key: ast.literal_eval(val) for key, val in di.items()
                if key != '__name__'}

""" Provide a singleton config instance, so it doesn't have to be instantiated
separately by every caller module """
cfg = ExtConfigParser(cfg_template, cfg_user)
