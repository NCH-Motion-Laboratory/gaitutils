# -*- coding: utf-8 -*-
"""
Created on Fri Sep 23 10:59:28 2016

Eclipse (database) hacks.

@author: jnu@iki.fi
"""
import logging
import ConfigParser


logger = logging.getLogger(__name__)


class FileStripper(object):
    """ File filter class that will skip lines listed in ignore """
    ignore = ['=\n']
    
    def __init__(self, f):
        self.fileobj = open(f)
        self.data = (x for x in self.fileobj if x not in
                     FileStripper.ignore)

    def readline(self):
        try:
            return next(self.data)
        except StopIteration:
            return ''
    
    def close(self):
        self.fileobj.close()
    

def _enf_reader(fname_enf):
    """ Return enf reader """
    cp = ConfigParser.SafeConfigParser(allow_no_value=True)
    cp.optionxform = str  # case sensitive
    fp = FileStripper(fname_enf)
    cp.readfp(fp)
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
