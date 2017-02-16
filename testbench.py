# -*- coding: utf-8 -*-
"""
Created on Mon Oct 17 14:06:22 2016

Test new gaitutils code

@author: HUS20664877
"""

from gaitutils import EMG, nexus, config, read_data, trial, eclipse, models, Plotter, layouts, utils
import matplotlib.pyplot as plt
import sys
import logging

logging.basicConfig()

# c3dfile = u'c:\\Users\\hus20664877\\Desktop\\Vicon\\vicon_data\\test\\H0036_EV\\2015_9_21_seur_EV\\2015_9_21_seur_EV19.c3d'


c3dfile = "C:/Users/hus20664877/Desktop/NVUG2017/Example Data Workshop/Carita/Level/Dynamic 03.c3d"

vicon = nexus.viconnexus()


pl = Plotter()

pl.open_trial(c3dfile)

print pl.trial.forceplate


sys.exit()



lout = [['RGlut', 'LGlut'], ['LRec', 'RRec']]
#lout = layouts.kinetics_emg('R')

#lout = layouts.std_emg

pl = Plotter()
pl.layout = layouts.rm_dead_channels(vicon, lout)
pl.open_nexus_trial()
pl.plot_trial()






