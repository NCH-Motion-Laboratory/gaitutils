# -*- coding: utf-8 -*-
"""

Run automark for single trial.

Note: event detection is less accurate compared to running autoprocess for the
whole session, since here we cannot use statistics for velocity thresholding.

@author: Jussi
"""

from __future__ import print_function
from gaitutils import nexus, utils


if not nexus.pid():
    raise Exception('Vicon Nexus not running')

vicon = nexus.viconnexus()
fpdata = utils.kinetics_available(vicon)
context = fpdata['context']
vel_th = {'R_strike': None, 'R_toeoff': None,
          'L_strike': None, 'L_toeoff': None}

if context:
    vel_th[context+'_strike'] = fpdata['strike_v']
    vel_th[context+'_toeoff'] = fpdata['toeoff_v']
    # mark around forceplate contact
    ctr_frame = fpdata['strike']
else:
    # no valid forceplate contact - mark around trial center
    ctr_frame = utils.get_crossing_frame(vicon, 'LASI')

vicon.ClearAllEvents()
nexus.automark_events(vicon, context=context,
                      events_context=(-1, 0, 1),
                      events_nocontext=(-1, 0, 1),
                      ctr_frame=ctr_frame,
                      vel_thresholds=vel_th,
                      plot=True)
