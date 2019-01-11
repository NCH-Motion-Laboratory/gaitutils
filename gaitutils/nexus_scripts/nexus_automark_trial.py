#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""

Run automark for single Nexus trial. Events are restricted to ROI.

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
    roi = vicon.GetTrialRegionOfInterest()
    vicon.ClearAllEvents()

    foot_markers = (cfg.autoproc.left_foot_markers +
                    cfg.autoproc.right_foot_markers)
    mkrs = foot_markers + utils._pig_pelvis_markers()
    mkrdata = read_data.get_marker_data(vicon, mkrs, ignore_missing=True)
    fpe = utils.detect_forceplate_events(vicon, mkrdata, roi=roi)
    vel = utils.get_foot_contact_velocity(mkrdata, fpe, roi=roi)
    utils.automark_events(vicon, vel_thresholds=vel, fp_events=fpe, roi=roi,
                          plot=plot)


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)

    parser = argparse.ArgumentParser()
    parser.add_argument('--plot', action='store_true',
                        help='plot velocity curves')
    args = parser.parse_args()
    automark_single(args.plot)
