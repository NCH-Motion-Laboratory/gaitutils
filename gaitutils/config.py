# -*- coding: utf-8 -*-
"""
Created on Wed Feb 15 13:14:16 2017

@author: hus20664877
"""


import ConfigParser
import ast
import os.path as op

# default config
cfg_template = 'C:/Users/hus20664877/gaitutils/gaitutils/default.cfg'
# user specific config
cfg_user = 'C:/Users/hus20664877/.gaitutils.cfg'


class Section(object):
    """ Holds data for sections """
    pass


class ExtConfigParser(object):
    """ Extends SafeConfigParser by:
    1) providing attribute access as extconfigparser.data.section.item
    2) attributes (as above) are stored as Python types, with autoconversion by
    the ast module (this is not implemented when accessing via ConfigParser
    default interface)
    """

    def __init__(self, cfg_template, cfg_user):
        self._parser = ConfigParser.SafeConfigParser.__init__(self)
        self.data = Section()
        self.read(cfg_template)
        try:
            self.read(cfg_user)
        except IOError:
            print('no config file, trying to create %s' % cfg_user)
            self.write(cfg_user)

    def read(self, file):
        if not op.isfile(file):
            raise IOError('config file does not exist')
        ConfigParser.SafeConfigParser.read(self, file)
        for section in self.sections():
            if section not in self.data.__dict__:
                self.data.__dict__[section] = Section()
            cfgtxt = self._sections[section]
            cfg = self._untextify(cfgtxt)
            self.data.__dict__[section].__dict__.update(cfg)

    def write(self, file):
        cfg = open(file, 'wt')
        ConfigParser.SafeConfigParser.write(self, cfg)
        cfg.close()

    @staticmethod
    def _untextify(di):
        """ Converts textual dict values into Python types """
        return {key: ast.literal_eval(val) for key, val in di.items()
                if key != '__name__'}

""" Provide a singleton config instance, so it doesn't have to be instantiated
separately by every caller module """
cfg = ExtConfigParser(cfg_template, cfg_user)
