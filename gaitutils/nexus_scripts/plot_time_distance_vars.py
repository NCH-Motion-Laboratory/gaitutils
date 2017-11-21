# -*- coding: utf-8 -*-
"""
Created on Tue Nov 14 16:45:32 2017


@author: Jussi (jnu@iki.fi)
"""


from gaitutils.plot import time_dist_barchart
import gaitutils

fn = 'Z:\\Userdata_Vicon_Server\\CP-projekti\\TD26\\20160824\\TD26_N1_05.c3d'
an = gaitutils.c3d.get_analysis(fn, 'Normal')
fn = 'Z:\\Userdata_Vicon_Server\\CP-projekti\\TD26\\20160824\\TD26_N1_06.c3d'
an2 = gaitutils.c3d.get_analysis(fn, 'Not normal')
an.update(an2)


fig = time_dist_barchart(an, interactive=True)

#canvas = FigureCanvas(fig)
#canvas.print_figure('test')


