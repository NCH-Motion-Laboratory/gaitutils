# -*- coding: utf-8 -*-
"""
Created on Fri Sep 23 10:59:28 2016

Eclipse (database) hacks.

@author: Jussi (jnu@iki.fi)
"""
from builtins import str
from builtins import object
import logging
import io
import configobj
from configobj import ConfigObj
from collections import defaultdict, OrderedDict

from .numutils import _isint
from .envutils import GaitDataError

logger = logging.getLogger(__name__)


class FileFilter(object):
    """Filter class for configobj.

    File-like class that will replace strings according to the replace
    dict below. This is needed for prefiltering before configobj parsing,
    since configobj will not tolerate lines with neither key nor value
    (which seem to occasionally appear in Eclipse files).
    Also deduplicates successive identical lines for same reason.
    """

    replace = {'\n=\n': '\n'}

    def __init__(self, fname):
        self.fname = fname

    def read(self):
        """Read data.

        ConfigObj seems to use only this method.
        """
        # Eclipse switched from latin-1 to utf-8 at some point...
        try:
            self.fp = io.open(self.fname, encoding='utf8')
            data = self.fp.read()
        except UnicodeDecodeError:
            logger.warning('Cannot interpret %s as utf-8, trying latin-1' % self.fname)
            self.fp = io.open(self.fname, encoding='latin-1')
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
    """Return enf reader (ConfigObj instance)."""
    fp = FileFilter(fname_enf)
    # do not listify comma-separated values
    # logger.debug('loading %s' % fname_enf)
    try:
        cp = ConfigObj(fp, encoding='utf8', list_values=False, write_empty_values=True)
    except configobj.ParseError:
        raise GaitDataError('Cannot parse config file %s' % fname_enf)
    if 'TRIAL_INFO' not in cp.sections:
        raise GaitDataError('No trial info in .enf file')
    return cp


def get_eclipse_keys(fname_enf, return_empty=False):
    """Read key/value pairs from enf file.

    Currently, only keys in the TRIAL_INFO section will be read.

    Parameters
    ----------
    fname_enf : str
        The filename.
    return_empty : bool, optional
        If True, return also keys without value

    Returns
    -------
    dict
        Dict of the eclipse keys and values.
    """
    di = defaultdict(lambda: u'')
    cp = _enf_reader(fname_enf)
    di.update(
        {key: val for key, val in cp['TRIAL_INFO'].items() if val != '' or return_empty}
    )
    return di


def _eclipse_forceplate_keys(eclipse_keys):
    """Filter that returns Eclipse forceplate keys/values as a dict."""
    return {
        key: val
        for key, val in eclipse_keys.items()
        if key[:2] == 'FP' and len(key) == 3 and _isint(key[2])
    }


def set_eclipse_keys(fname_enf, eclipse_dict, update_existing=False):
    """Set key/value pairs in enf file.

    Keys will be written into the TRIAL_INFO section.

    Parameters
    ----------
    fname_enf : str
        The filename.
    eclipse_dict : dict
        A dict containing the new key/value pairs.
    update_existing : bool, optional
        If True, overwrite existing keys.
    """
    cp = _enf_reader(fname_enf)
    did_set = False
    for key, val in eclipse_dict.items():
        if key not in cp['TRIAL_INFO'].keys() or update_existing:
            cp['TRIAL_INFO'][key] = val
            did_set = True
    if did_set:
        logger.debug('writing %s' % fname_enf)
        # output the config lines; this writes utf8-encoded bytes
        out = cp.write()
        # they must be converted to str for writing
        outu = [str(line, encoding='utf8') + '\n' for line in out]
        with io.open(fname_enf, 'w', encoding='utf8') as fp:
            fp.writelines(outu)
    else:
        logger.debug('did not set any keys')
