# -*- coding: utf-8 -*-
"""
Created on Fri Sep 23 10:59:28 2016

Eclipse (database) hacks.

@author: jnu@iki.fi
"""
import logging
import ConfigParser


logger = logging.getLogger(__name__)


def get_eclipse_keys(fname_enf, return_empty=False):
    cp = ConfigParser.SafeConfigParser()
    cp.optionxform = str  # case sensitive
    cp.read(fname_enf)
    return {key: unicode(val) for key, val in cp.items('TRIAL_INFO')
            if val != '' or return_empty}


def set_eclipse_key(fname_enf, keyname, newval, update_existing=False):
    """ Update specified Eclipse file, changing 'keyname' to 'value'.
    If update_existing=True, update also keys that already have a value. """
    with open(fname_enf, 'r') as f:
        eclipselines = f.read().splitlines()
    linesnew = []
    for line in eclipselines:
        eqpos = line.find('=')
        if eqpos > 0:
            key = line[:eqpos]
            val = line[eqpos+1:]
            if key == keyname and (not val or update_existing):
                newline = key + '=' + newval
            else:  # key mismatch - copy line as is
                newline = line
        else:  # comment or section header - copy as is
            newline = line
        linesnew.append(newline)
    with open(fname_enf, 'w') as f:
        logger.debug('writing %s' % fname_enf)
        for li in linesnew:
            f.write(li + '\n')
