# -*- coding: utf-8 -*-
"""
Created on Fri Nov 11 11:44:00 2016

@author: hus20664877
"""

import read_data
from trial import Trial
import matplotlib.pyplot as plt


class Plotter():

    def __init__(self, vars):
        self.vars = vars
        pass
        
    def open_trial(self, source):
        self.trial = Trial(source)
                
    def plot(self):
        self.gridspec = gridspec.GridSpec(self.gridv, self.gridh,
                                          height_ratios=plotheightratios)
        ax = plt.subplot(self.gs[self.model_plot_pos[k]])        
        
        
