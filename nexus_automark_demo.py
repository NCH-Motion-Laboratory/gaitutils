# -*- coding: utf-8 -*-
"""

Run automark for single trial

@author: Jussi
"""

from __future__ import print_function
from gaitutils import nexus, eclipse
import glob
import os
import numpy as np
import time

AUTOMARK_HW = 100

if not nexus.pid():
    raise Exception('Vicon Nexus not running')

vicon = nexus.viconnexus()
# get kinetics info
fpdata = nexus.kinetics_available(vicon)
context = fpdata['context']
vel_th = dict()

for side in ['R', 'L']:
    vel_th[side+'_strike'] = None
    vel_th[side+'_toeoff'] = None

if context:
    vel_th[context+'_strike'] = fpdata['strike_v']
    vel_th[context+'_toeoff'] = fpdata['toeoff_v']

vicon.ClearAllEvents()

strike_frame = fpdata['strike'] if fpdata else None
nexus.automark_events(vicon, strike_frame=strike_frame, plot=True,
                      context=context,
                      vel_thresholds=vel_th,
                      mark_window_hw=AUTOMARK_HW)

