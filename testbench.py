# -*- coding: utf-8 -*-
"""
Created on Mon Oct 17 14:06:22 2016

Test new gaitutils code

@author: HUS20664877
"""

from gaitutils import EMG, nexus, config, read_data, trial, eclipse, models, Plotter, layouts, utils
import matplotlib.pyplot as plt


# c3dfile = u'c:\\Users\\hus20664877\\Desktop\\Vicon\\vicon_data\\test\\H0036_EV\\2015_9_21_seur_EV\\2015_9_21_seur_EV19.c3d'
vicon = nexus.viconnexus()


lout = [['LVas', 'RVas'], ['LRec', 'RRec'], ['LHam', 'RHam']]
lout = layouts.kinetics_emg('R')

lout = layouts.std_kinetics

pl = Plotter()

pl.layout = lout

pl.open_nexus_trial()

pl.plot_trial(model_cycles=None, context='L')






