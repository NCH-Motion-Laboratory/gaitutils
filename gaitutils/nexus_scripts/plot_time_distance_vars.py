# -*- coding: utf-8 -*-
"""
Created on Tue Nov 14 16:45:32 2017

@author: hus20664877
"""

import gaitutils

fn = 'Z:\\Userdata_Vicon_Server\\CP-projekti\\TD26\\20160824\\TD26_N1_05.c3d'


"""
pl = gaitutils.Plotter()

pl.open_trial(fn)

pl.layout = gaitutils.cfg.layouts.lb_kin

pl.plot_trial()
"""


an = gaitutils.c3d.get_c3d_analysis(fn)


vars = ['Cadence', 'Walking Speed', 'Stride Time', 'Stride Length',
        'Single Support', 'Step Length']


