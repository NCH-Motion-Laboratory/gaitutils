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

import logging
logging.basicConfig(level=logging.DEBUG)


def automark_single():

    if not nexus.pid():
        raise Exception('Vicon Nexus not running')

    vicon = nexus.viconnexus()
    vicon.ClearAllEvents()

    fpe = utils.detect_forceplate_events(vicon)
    vel = utils.get_foot_velocity(vicon, fpe)

    nexus.automark_events(vicon, vel_thresholds=vel,
                          max_dist=cfg.autoproc.automark_max_dist,
                          fp_events=fpe, ctr_pos=cfg.autoproc.walkway_ctr,
                          plot=False)

if __name__ == '__main__':
    automark_single()
