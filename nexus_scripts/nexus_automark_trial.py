# -*- coding: utf-8 -*-
"""

Run automark for single trial.

Note: event detection is less accurate compared to running autoprocess for the
whole session, since here we cannot use statistics for velocity thresholding.

@author: Jussi
"""

from __future__ import print_function
from gaitutils import nexus, utils
from gaitutils.config import cfg
import argparse

import logging


def automark_single(plot=False):

    vicon = nexus.viconnexus()
    vicon.ClearAllEvents()

    fpe = utils.detect_forceplate_events(vicon)
    vel = utils.get_foot_velocity(vicon, fpe)

    nexus.automark_events(vicon, vel_thresholds=vel,
                          max_dist=cfg.autoproc.automark_max_dist,
                          fp_events=fpe, ctr_pos=cfg.autoproc.walkway_ctr,
                          restrict_to_roi=True, plot=plot)

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)

    parser = argparse.ArgumentParser()
    parser.add_argument('--plot', action='store_true',
                        help='plot velocity curves')
    args = parser.parse_args()
    automark_single(args.plot)
