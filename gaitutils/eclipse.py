# -*- coding: utf-8 -*-
"""
Created on Fri Sep 23 10:59:28 2016

Eclipse (database) hacks.

@author: Jussi (jnu@iki.fi)
"""
import logging
import io
import configobj
from configobj import ConfigObj
from collections import defaultdict, OrderedDict

from .numutils import isint
from .envutils import GaitDataError

logger = logging.getLogger(__name__)


class FileFilter(object):
    """ File-like class that will replace strings according to the replace
    dict below. This is needed for prefiltering before configobj parsing,
    since configobj will not tolerate lines with neither key nor value
    (which seem to occasionally appear in Eclipse files).
    Also deduplicates successive identical lines for same reason """

    replace = {'\n=\n': '\n'}

    def __init__(self, fname):
        # enf files are supposed to be in utf8 encoding
        self.fp = io.open(fname, encoding='utf8')

    def read(self):
        """ ConfigObj seems to use only this method """
        data = self.fp.read()
        # filter
        for val, newval in FileFilter.replace.items():
            data = data.replace(val, newval)
        # rm subsequent duplicate lines - a bit cryptic
        data = '\n'.join(list(OrderedDict.fromkeys(data.split('\n'))))
        return data

    def close(self):
        self.fp.close()


def _enf_reader(fname_enf):
    """ Return enf reader """
    fp = FileFilter(fname_enf)
    # do not listify comma-separated values
    # logger.debug('loading %s' % fname_enf)
    try:
        cp = ConfigObj(fp, encoding='utf8', list_values=False,
                       write_empty_values=True)
    except configobj.ParseError:
        raise GaitDataError('Cannot parse config file %s' % fname_enf)
    if 'TRIAL_INFO' not in cp.sections:
        raise GaitDataError('No trial info in .enf file')
    return cp


def get_eclipse_keys(fname_enf, return_empty=False):
    """ Read key/value pairs from ENF file into a dict. Only keys in the
    TRIAL_INFO section will be read. Return keys without value if
    return_empty.
    """
    di = defaultdict(lambda: u'')
    cp = _enf_reader(fname_enf)
    di.update({key: val for key, val in cp['TRIAL_INFO'].items()
               if val != '' or return_empty})
    return di


def eclipse_fp_keys(eclipse_keys):
    """ Filter that returns Eclipse forceplate keys/values as a dict """
    return {key: val for key, val in eclipse_keys.items()
            if key[:2] == 'FP' and len(key) == 3 and isint(key[2])}


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
