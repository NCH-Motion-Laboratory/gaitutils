# -*- coding: utf-8 -*-
"""

Run automark for single trial.

Note: event detection is less accurate compared to running autoprocess for the
whole session, since here we cannot use statistics for velocity thresholding.

@author: Jussi (jnu@iki.fi)
"""

from __future__ import print_function
import argparse
import logging

from gaitutils import nexus, utils, read_data, cfg


def automark_single(plot=False):

    vicon = nexus.viconnexus()
    vicon.ClearAllEvents()

    # TODO: might want to use Eclipse forceplate info also here
    foot_markers = (cfg.autoproc.left_foot_markers +
                    cfg.autoproc.right_foot_markers)
    mkrdata = read_data.get_marker_data(vicon, foot_markers)
    fpe = utils.detect_forceplate_events(vicon, mkrdata)
    vel = utils.get_foot_velocity(mkrdata, fpe)

    nexus.automark_events(vicon, vel_thresholds=vel,
                          events_range=cfg.autoproc.events_range,
                          fp_events=fpe, restrict_to_roi=True, plot=plot)


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)

    parser = argparse.ArgumentParser()
    parser.add_argument('--plot', action='store_true',
                        help='plot velocity curves')
    args = parser.parse_args()
    automark_single(args.plot)
