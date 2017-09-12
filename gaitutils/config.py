# -*- coding: utf-8 -*-
"""
Handles gaitutils config files.

@author: jnu@iki.fi
"""

import ConfigParser
import ast
import os.path as op
from pkg_resources import resource_filename

# default config
cfg_template = resource_filename(__name__, 'default.cfg')
# user specific config
homedir = op.expanduser('~')
cfg_user = homedir + '/.gaitutils_cp_projekti.cfg'


class Section(object):
    """ A config section """

    def __init__(self, dict):
        """ The config items for the section are provided as key/value dict,
        where values are strings. """
        self._dict = dict

    def __getattr__(self, item):
        """ Implements attribute access, i.e. section.item. The items don't
        exist as instance variables, so referencing them will cause
        __getattr__ to be called. The items are returned from the section dict
        and automatically converted from strings to Python types. """
        return ast.literal_eval(self._dict[item])


class EpicParser(ConfigParser.SafeConfigParser):
    """ Extends SafeConfigParser by providing convenient attribute access
    (by parser.section.item) and autoconversion from strings to Python
    types.
    For modifying config items, it's still necessary to use the
    syntax parser[section][item] = data, where data must always be a string
    type. """

    def __getitem__(self, section):
        """ Returns the parser section dictionary. Not implemented by
        SafeConfigParser """
        return self._sections[section]
    
    def __repr__(self):
        """ For completeness; not implemented by SafeConfigParser """
        return '<%s.%s at %s>' % (self.__class__.__module__,
                                  self.__class__.__name__,
                                  str(hex(id(self))))

    def __getattr__(self, section):
        """ Implements attribute access, i.e. parser.section or more commonly
        parser.section.item. A new Section instance is created from the parser
        data. """
        return Section(self._sections[section])

# provide the global cfg instance
cfg = EpicParser()
cfg.read(cfg_template)
if not op.isfile(cfg_user):
    print('no config file, trying to create %s' % cfg_user)
    cfg_file = open(cfg_user, 'wt')
    cfg.write(cfg_file)
    cfg_file.close()
else:
    cfg.read(cfg_user)
