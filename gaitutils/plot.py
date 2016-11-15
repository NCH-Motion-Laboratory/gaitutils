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

import models
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
        self.nrows = len(plotvars)
        self.ncols = len(plotvars[0])
        self.plotvars = plotvars
        self.trial = None
        self.fig = None
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
        """ Helper to return variable type """
        if var is None:
            return None
        elif models.model_from_var(var):
            return 'model'
        elif var in self.trial.emg.ch_names:
            return 'emg'
        else:
            raise ValueError('Unknown variable')

    def plot_trial(self, cycles={'R': [1], 'L': [1]}, t=None,
                   plotheightratios=None):

        """ Create plot of variables. Parameters:

        cycles  Lists of gait cycles to plot. Default is first cycle (1) for
                both sides. Multiple cycles will be overlaid. If None, plot
                unnormalized data. If 'all', plot all available cycles.
                Model variable names are determined according to cycle, e.g.
                'HipMomentX' will be 'LHipMomentX' for a left gait cycle.
        t       Time axis for unnormalized data. If None, plot whole time
                axis.
        """

        if not self.trial:
            raise ValueError('No trial to plot, call open_trial() first')
        if self.fig is None:
            self.fig = plt.figure()
        if plotheightratios is None:
            plotheightratios = [1] * self.nrows  # set plot heights all equal
        self.gridspec = gridspec.GridSpec(self.nrows, self.ncols,
                                          height_ratios=plotheightratios)
        if cycles is None:
            pass  # TODO: plot unnormalized
        elif cycles is 'all':
            cycles = self.trial.cycles
        else:  # pick cycles specified by argument
            cycles = [self.trial.get_cycle(side, ncycle) for side in ['L', 'R']
                      for ncycle in cycles[side]]
        for i, var in enumerate(self.allvars):
            ax = plt.subplot(self.gridspec[i])
            var_type = self._var_type(var)
            if var_type is None:
                continue
            elif var_type == 'model':
                for cycle in cycles:
                    self.trial.set_norm_cycle(cycle)
                    if (models.pig_lowerbody.is_kinetic_var(var) and
                       cycle not in self.trial.kinetics_cycles):
                            continue  # break if no kinetics for this cycle
                    self.trial.set_norm_cycle(cycle)
                    varname = cycle.context + var
                    data = self.trial[varname]
                    ax.plot(data)
            elif var_type == 'emg':
                for cycle in cycles:
                    self.trial.set_norm_cycle(cycle)
                    data = self.trial[var]
                    ax.plot(data)
        plt.show()









