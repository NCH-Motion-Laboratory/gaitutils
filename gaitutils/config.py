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

    def __init__(self, dict):
        """ The config items are provided as key/value dict, where values
        are strings. """
        self._dict = dict

    def __getattr__(self, item):
        """ This implements attribute access. The items don't directly
        exist as instance variables, so referencing them will cause
        __getattr__ to be called. The items are automatically converted from
        strings to Python types. """
        return ast.literal_eval(self._dict[item])


class EpicParser(ConfigParser.SafeConfigParser):
    """ Extends SafeConfigParser by providing convenient attribute access
    (by parser.section.value) and autoconversion from strings to Python
    types.
    For modifying config items, it's still necessary to use the
    syntax parser[section][item] = data, where data must always be a string
    type. """

    def __getitem__(self, section):
        """ This returns the parser section dictionary. """
        return self._sections[section]

    def __getattr__(self, section):
        """ This implements attribute access. The sections don't directly
        exist as instance variables, so referencing them will cause
        __getattr__ to be called. """
        return Section(self._sections[section])


cfg = EpicParser()
cfg.read(cfg_template)
if not op.isfile(cfg_user):
    print('no config file, trying to create %s' % cfg_user)
    cfg_file = open(cfg_user, 'wt')
    cfg.write(cfg_file)
    cfg_file.close()
else:
    cfg.read(cfg_user)
