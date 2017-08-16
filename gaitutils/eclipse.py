# -*- coding: utf-8 -*-
"""
Created on Fri Sep 23 10:59:28 2016

Eclipse (database) hacks.

@author: jnu@iki.fi
"""
import logging
import io
from configobj import ConfigObj


logger = logging.getLogger(__name__)


class FileFilter(object):
    """ File-like class that will replace strings according to the replace
    dict below. This is needed for prefiltering before configobj parsing,
    since configobj will not tolerate lines with neither key nor value
    (which seem to occasionally appear in Eclipse files) """

    replace = {'\n=\n': '\n'}

    def __init__(self, fname):
        # enf files are supposed to be in utf8 encoding
        self.fp = io.open(fname, encoding='utf8')

    def read(self):
        data = self.fp.read()
        for val, newval in FileFilter.replace.items():
            data = data.replace(val, newval)
        return data

    def readline(self):
        line = self.fp.readline()
        for val, newval in FileFilter.replace.items():
            line = line.replace(val, newval)
        return line

    def readlines(self):
        lines = list()
        while True:
            line = self.readline()
            if not line:
                break
            else:
                lines.append(line)
        return lines

    def close(self):
        self.fp.close()


def _enf_reader(fname_enf):
    """ Return enf reader """
    fp = FileFilter(fname_enf)
    # do not listify comma-separated values
    cp = ConfigObj(fp, encoding='utf8', list_values=False)
    if 'TRIAL_INFO' not in cp.sections:
        raise ValueError('No trial info in .enf file')
    return cp


def get_eclipse_keys(fname_enf, return_empty=False):
    """ Read key/value pairs from ENF file into a dict. Only keys in the
    TRIAL_INFO section will be read. Return keys without value if
    return_empty.
    """
    cp = _enf_reader(fname_enf)
    return {key: val for key, val in cp['TRIAL_INFO'].items()
            if val != '' or return_empty}


def set_eclipse_keys(fname_enf, eclipse_dict, update_existing=False):
    """ Set key/value pairs in an ENF file. If update_existing is True,
    overwrite existing keys. Keys will be written into the TRIAL_INFO section.
    """
    cp = _enf_reader(fname_enf)
    did_set = False
    for key, val in eclipse_dict.items():
        if key not in cp['TRIAL_INFO'].keys() or update_existing:
            cp['TRIAL_INFO'][key] = val
            did_set = True
    if did_set:
        logger.debug('writing %s' % fname_enf)
        out = cp.write()  # output the config lines
        # result is utf8, but needs to be converted to unicode type for write
        outu = [unicode(line+'\n', encoding='utf8') for line in out]
        with io.open(fname_enf, 'w', encoding='utf8') as fp:
            fp.writelines(outu)
    else:
        logger.warning('Did not set any keys')
