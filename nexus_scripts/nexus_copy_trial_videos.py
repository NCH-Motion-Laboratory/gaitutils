# -*- coding: utf-8 -*-
"""
Created on Thu Sep 03 14:54:34 2015

Copy trial videos to desktop under nexus_videos

@author: Jussi
"""

import os
import os.path as op
import glob
import shutil
import logging

from gaitutils import nexus
from gaitutils.guiutils import messagebox


logger = logging.getLogger(__name__)


def trial_videos(enffile):
    trialname = enffile[:enffile.find('.Trial.enf')]
    return glob.glob(trialname+'*avi')


def do_copy():

    nexus.check_nexus()

    dest_dir = op.join(op.expanduser('~'), 'Desktop', 'nexus_videos')
    if not op.isdir(dest_dir):
        os.mkdir(dest_dir)

    search = ['R1', 'L1']
    eclkeys = ['DESCRIPTION', 'NOTES']
    enf_files = nexus.find_trials(eclkeys, search)

    # concatenate video iterators for all .enf files
    vidfiles = []
    for enf in enf_files:
        vidfiles += trial_videos(enf)

    if not vidfiles:
        raise Exception('No video files found for R1/L1 trials')

    # copy each file
    for j, vidfile in enumerate(vidfiles):
        logger.debug('%s -> %s' % (vidfile, dest_dir))
        shutil.copy2(vidfile, dest_dir)

    messagebox('Copied %d video file%s into %s' % ((j+1), 's' if j > 1 else '',
                                                   dest_dir))

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    do_copy()
