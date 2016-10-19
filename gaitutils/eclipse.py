# -*- coding: utf-8 -*-
"""
Created on Fri Sep 23 10:59:28 2016

Eclipse (database) hacks.

@author: jnu@iki.fi
"""
from __future__ import print_function
import os.path


def get_eclipse_key(fname_enf, keyname):
    """ Get the Eclipse database entry 'keyname' for the specified trial. Specify
    trialname with full path. Return empty string for no key. """
    with open(fname_enf, 'r') as f:
        eclipselines = f.read().splitlines()
    for line in eclipselines:
        eqpos = line.find('=')
        if eqpos > 0:
            key = line[:eqpos]
            val = line[eqpos+1:]
            if key == keyname:
                value = val
    # assume utf-8 encoding for Windows text files, return Unicode object
    # could also use codecs.read with encoding=utf-8 (recommended way)
    return unicode(value, 'utf-8')


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
        # print('set_eclipse_key: writing %s' % fname_enf_)
        for li in linesnew:
            # print('set_eclipse_key: new line %s' % li)
            f.write(li + '\n')
