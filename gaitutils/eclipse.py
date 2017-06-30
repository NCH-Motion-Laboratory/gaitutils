# -*- coding: utf-8 -*-
"""
Created on Fri Sep 23 10:59:28 2016

Eclipse (database) hacks.

@author: jnu@iki.fi
"""
import logging
import ConfigParser


logger = logging.getLogger(__name__)


def _enf_reader(fname_enf):
    """ Return enf reader """
    cp = ConfigParser.SafeConfigParser()
    cp.optionxform = str  # case sensitive
    if not cp.read(fname_enf):
        raise IOError('No such .enf file')
    if 'TRIAL_INFO' not in cp.sections():
        raise ValueError('This does not look like an Eclipse .enf file')
    return cp


def get_eclipse_keys(fname_enf, return_empty=False):
    """ Read key/value pairs from ENF file into a dict. Only keys in the
    TRIAL_INFO section will be read.
    """
    cp = _enf_reader(fname_enf)
    return {key: unicode(val) for key, val in cp.items('TRIAL_INFO')
            if val != '' or return_empty}


def set_eclipse_keys(fname_enf, eclipse_dict, update_existing=False):
    """ Set key/value pairs in an ENF file. If update_existing is True,
    overwrite existing keys. Keys will be written into the TRIAL_INFO section.
    """
    cp = _enf_reader(fname_enf)
    did_set = False
    for key, val in eclipse_dict.items():
        if key not in zip(*cp.items('TRIAL_INFO'))[0] or update_existing:
            cp.set('TRIAL_INFO', key, val)
            did_set = True
    if did_set:
        with open(fname_enf, 'w') as fp:
            logger.debug('writing %s' % fname_enf)
            cp.write(fp)
    else:
        logger.warning('Did not set any keys')
