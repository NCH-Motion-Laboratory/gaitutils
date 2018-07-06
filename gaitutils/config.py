# -*- coding: utf-8 -*-
"""
Handles gaitutils config files.

@author: Jussi (jnu@iki.fi)
"""

import ConfigParser
import ast
import os.path as op
import os
import copy
import sys
from pkg_resources import resource_filename

from . import envutils


""" Work around stdout and stderr not being available, if we are run
using pythonw.exe on Windows. Without this, exception will be raised
e.g. on any print statement. """
if (sys.platform.find('win') != -1 and sys.executable.find('pythonw') != -1 and
   not envutils.run_from_ipython()):
    blackhole = file(os.devnull, 'w')
    sys.stdout = sys.stderr = blackhole

# default config
cfg_template = resource_filename(__name__, 'default.cfg')
# user specific config
homedir = op.expanduser('~')
cfg_user = op.join(homedir, '.gaitutils.cfg')


class Section(object):
    """ A config section """

    def __init__(self, di):
        """ The config items for the section are provided as key/value dict,
        where values are strings. """
        self._dict = di

    def __getattr__(self, item):
        """ Implements attribute access, i.e. section.item. The items don't
        exist as instance variables, so referencing them will cause
        __getattr__ to be called. The items are returned from the section dict
        and automatically converted from strings to Python types. """
        try:
            return ast.literal_eval(self._dict[item])
        except ValueError:
            raise ValueError('Could not convert value %s to Python type' %
                             self._dict[item])


class EpicParser(ConfigParser.SafeConfigParser):
    """ Extends SafeConfigParser by providing convenient attribute access
    (by parser.section.item) and autoconversion from strings to Python
    types.
    For modifying config items, it's still necessary to use the
    syntax parser[section][item] = data, where data must always be a string
    type. """

    def __getitem__(self, section):
        """ Returns the parser section dictionary. """
        return self._sections[section]

    def __repr__(self):
        return '<EpicParser>'

    def __getattr__(self, section):
        """ Implements attribute access, i.e. parser.section or more commonly
        parser.section.item. A new Section instance is created from the parser
        data. """
        return Section(self._sections[section])

    def write_file(self, filename):
        """ Save config into file """
        # using the with statement would force-close the file even in case
        # of errors, which could lead to broken (e.g. empty) files
        fh = open(filename, 'wt')
        cfg.write(fh)
        fh.close()

    def load_default(self):
        """ Load default config """
        self.read(cfg_template)


# provide the global cfg instance
# read template config
cfg = EpicParser()
cfg.load_default()
cfg_tpl_di = copy.deepcopy(cfg._sections)  # save the template config

# read user config
if not op.isfile(cfg_user):
    print('no config file, trying to create %s' % cfg_user)
    cfg.write_file(cfg_user)
else:
    print('reading user config from %s' % cfg_user)
    cfg.read(cfg_user)

# check for extra entries in user config
no_check = ['layouts']
cfg_user_di = cfg._sections
for sname, section in cfg_user_di.items():
    if sname not in cfg_tpl_di:
        print('WARNING: unused (deprecated?) section %s in user config'
              % sname)
    else:
        if sname not in no_check:
            for key in section:
                if key not in cfg_tpl_di[sname]:
                    print('WARNING: unused (deprecated?) key '
                          '%s.%s in user config' % (sname, key))

# handle some deprecated/changed types for user convenience
if not isinstance(cfg.plot.emg_yscale, float):
    ysc = cfg.plot.emg_yscale[1]
    print('WARNING: emg_yscale was changed to float, using %g' % ysc)
    cfg['plot']['emg_yscale'] = str(cfg.plot.emg_yscale[1])

sys.stdout.flush()  # make sure that warnings are printed out
