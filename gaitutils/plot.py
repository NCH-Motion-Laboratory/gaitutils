# -*- coding: utf-8 -*-
"""

-1 instance per layout
-separate methods for adding normal data?
-exception handling?
-plot unnormalized data
-overlay multiple cycles from same trial
-plot avg/stddev?


@author: hus20664877
"""

import read_data
from trial import Trial
import matplotlib.pyplot as plt
from matplotlib import pylab
import matplotlib.gridspec as gridspec
from guiutils import error_exit, messagebox


class Plotter():

    def __init__(self, plotvars):
        if (not isinstance(plotvars, list) or not
           all([isinstance(item, list)for item in plotvars])):
            raise ValueError('Plot variables must be a list of lists')
        self.nrows = len(vars)
        self.ncols = len(vars[0])
        self.plotvars = plotvars
        self.trial = None
        self.allvars = [item for row in plotvars for item in row]

    def open_trial(self, source):
        self.trial = Trial(source)

    def _move_plot_window(self, x, y):
        """ Move figure upper left corner to x,y. Only works with
        Qt backend. """
        if 'Qt4' in pylab.get_backend():
            cman = pylab.get_current_fig_manager()
            _, _, dx, dy = cman.window.geometry().getRect()
            cman.window.setGeometry(x, y, dx, dy)

    def _var_type(self, var):
        """ Helper function to return variable type """
        try:
            Trial._get_modelvar(var)
            return 'model'
        except ValueError:
            try:
                Trial.emg[var]
                return 'emg'
            except KeyError:
                raise ValueError('Unknown variable')

    def plot_trial(self, cycles=[1], t=None):

        """ Create plot of variables. Parameters:
       
        cycles  List of cycles to plot. Default is first cycle (1). Multiple
                cycles will be overlaid. If None, plot unnormalized data.
        t       Time axis for unnormalized data.
        """        
        
        if not self.trial:
            raise ValueError('No trial to plot')
        if plotheightratios is None:
            plotheightratios = [1] * self.nrows  # set plot heights all equal
        self.gridspec = gridspec.GridSpec(self.gridw, self.gridh,
                                          height_ratios=plotheightratios)
        # loop through variables and plot
        if cycles is None:
            cycles = [None]                                          
        for i, var in enumerate(self.allvars):
            for cyclen in cycles:
                if cyclen:
                    rcycle = self.trial.get_cycle('R', cyclen)
                    lcycle = self.trial.get_cycle('L', cyclen)
                if _var_type == 'model':
                    ax = plt.subplot(self.gridspec[i])
                    data = self.trial[var]
                
                
            
            
            
                                



