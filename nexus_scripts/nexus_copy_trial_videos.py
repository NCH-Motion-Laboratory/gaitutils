# -*- coding: utf-8 -*-
"""
Created on Thu Sep 03 14:54:34 2015

Copy trial videos to desktop under nexus_videos

@author: Jussi
"""

from gaitutils import nexus
import os
import os.path as op
import glob
import shutil
import logging
logger = logging.getLogger(__name__)


def do_copy():

    dest_dir = op.join(op.expanduser('~'), 'Desktop', 'nexus_videos')
    if not op.isdir(dest_dir):
        os.mkdir(dest_dir)

    search = ['R1', 'L1']
    eclkeys = ['DESCRIPTION', 'NOTES']
    enf_files = nexus.find_trials(eclkeys, search)

    def trial_videos(enffile):
        trialname = enffile[:enffile.find('.Trial.enf')]
        return glob.glob(trialname+'*avi')

    # concatenate video iterators for all .enf files
    vidfiles = []
    for enf in enf_files:
        vidfiles += trial_videos(enf)

    if not vidfiles:
        raise Exception('No video files found for specified trials')

    # copy each file
    for vidfile in vidfiles:
        logger.debug('%s -> %s' % (vidfile, dest_dir))
        shutil.copy2(vidfile, dest_dir)


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    if not nexus.pid():
        raise Exception('Vicon Nexus not running')
    do_copy()
