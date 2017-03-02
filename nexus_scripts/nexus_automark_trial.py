# -*- coding: utf-8 -*-
"""

Run automark for single trial.

Note: event detection is less accurate compared to running autoprocess for the
whole session, since here we cannot use statistics for velocity thresholding.

@author: Jussi
"""

from __future__ import print_function
from gaitutils import nexus, utils

import logging
logging.basicConfig(level=logging.DEBUG)


def automark_single():

    if not nexus.pid():
        raise Exception('Vicon Nexus not running')

    vicon = nexus.viconnexus()
    fpdata = utils.check_forceplate_contact(vicon)

    vel_th = {'R_strike': None, 'R_toeoff': None,
              'L_strike': None, 'L_toeoff': None}

    first_strike = dict()
    for context in ['R', 'L']:
        if context in fpdata['strikes']:
            vel_th[context+'_strike'] = fpdata['strike_v']
            vel_th[context+'_toeoff'] = fpdata['toeoff_v']
            first_strike[context] = fpdata['strike']

    vicon.ClearAllEvents()
    nexus.automark_events(vicon,
                          vel_thresholds=vel_th, max_dist=2000,
                          ctr_pos=[0, 300, 0],
                          first_strike=first_strike, plot=False)

if __name__ == '__main__':
    automark_single()
