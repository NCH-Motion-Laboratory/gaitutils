# -*- coding: utf-8 -*-
"""

-1 instance per layout
-separate methods for adding normal data?
-exception handling?
-plot unnormalized data
-plot avg/stddev?


TODO:

-return also appropriate time variable from Trial class __getitem__ (to be
used for plotting)

-config class to store all parameters




@author: jnu@iki.fi
"""


import models
from trial import Trial
import matplotlib.pyplot as plt
from matplotlib import pylab
from matplotlib.backends.backend_pdf import PdfPages
import matplotlib.gridspec as gridspec
from guiutils import error_exit, messagebox
import os.path as op


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

    def plot_trial(self, cycles={'R': 1, 'L': 1}, context=None, t=None,
                   plotheightratios=None, model_tracecolor=None,
                   emg_tracecolor=None):

        """ Create plot of variables. Parameters:

        cycles  : dict of int | dict of list | 'all' | None
                Gait cycles to plot. Default is first cycle (1) for
                both sides. Multiple cycles can be given as lists.
                If None, plot unnormalized data. 'context' must be specified.
                If 'all', plot all available cycles.
                Model variable names are modified according to context, e.g.
                'HipMomentX' -> 'LHipMomentX' for a left side gait cycle.
        t       Time axis for unnormalized data. If None, plot whole time
                axis.
        """

        label_fontsize = 10  # TODO: into config
        ticks_fontsize = 10
        totalfigsize = (14, 12)
        model_tracecolors = {'R': 'lawngreen', 'L': 'red'}
        emg_tracecolor = 'black'
        emg_ylabel = 'mV'
        emg_multiplier = 1e3  # plot millivolts

        if not self.trial:
            raise ValueError('No trial to plot, call open_trial() first')
        if self.fig is None:
            superposing = False
            self.fig = plt.figure(figsize=totalfigsize)
        else:
            superposing = True
        if plotheightratios is None:
            plotheightratios = [1] * self.nrows  # set plot heights all equal
        self.gridspec = gridspec.GridSpec(self.nrows, self.ncols,
                                          height_ratios=plotheightratios)
        if cycles is None:
            cycles = [None]  # make iterable
        elif cycles == 'all':
            cycles = self.trial.cycles
        elif isinstance(cycles, dict):
            cycles.update({key: [val] for (key, val) in cycles.items()
                          if isinstance(val, int)})  # int -> list
            cycles = [self.trial.get_cycle(side, ncycle) for side in ['L', 'R']
                      for ncycle in cycles[side]]

        for i, var in enumerate(self.allvars):
            ax = plt.subplot(self.gridspec[i])
            var_type = self._var_type(var)
            if var_type is None:
                continue
            elif var_type == 'model':
                model = models.model_from_var(var)
                for cycle in cycles:
                    if cycle is not None:  # plot normalized data
                        self.trial.set_norm_cycle(cycle)
                        context = cycle.context
                        if (models.pig_lowerbody.is_kinetic_var(var) and
                           cycle not in self.trial.kinetics_cycles):
                                continue  # break if no kinetics for this cycle
                    else:
                        if context is None:
                            raise ValueError('Must specify context if plotting '
                                             'unnormalized model variables')
                    varname = context + var
                    x, data = self.trial[varname]
                    tcolor = (model_tracecolor if model_tracecolor
                              else model_tracecolors[context])
                    ax.plot(x, data, tcolor)
                    # set labels, ticks, etc. after plotting last cycle
                    if cycle == cycles[-1]:
                        ax.set(ylabel=model.ylabels[varname])  # no xlabel for now
                        ax.xaxis.label.set_fontsize(label_fontsize)
                        ax.yaxis.label.set_fontsize(label_fontsize)
                        plt.axhline(0, color='black')  # zero line
                        ax.locator_params(axis='y', nbins=6)  # less y tick marks
                        # tick font size
                        ax.tick_params(axis='both', which='major',
                                       labelsize=ticks_fontsize)
                        ylim = ax.get_ylim()
                        # model specific adjustments
                        if model == models.pig_lowerbody:
                            ylim0 = -10 if ylim[0] == 0 else ylim[0]
                            ylim1 = 10 if ylim[1] == 0 else ylim[1]
                            ax.set_ylim(ylim0, ylim1)
                        elif model == models.musclelen:
                            ax.set_ylim(ylim[0]-10, ylim[1]+10)

            elif var_type == 'emg':
                for cycle in cycles:
                    if cycle is not None:  # plot normalized data
                        self.trial.set_norm_cycle(cycle)
                    x, data = self.trial[var]
                    data *= emg_multiplier
                    ax.plot(x, data)
                    ax.set(ylabel=emg_ylabel)
                    ax.yaxis.label.set_fontsize(label_fontsize)
                    plt.title(var, fontsize=self.fsize_titles)
                    plt.locator_params(axis='y', nbins=4)
                    # tick font size
                    plt.tick_params(axis='both', which='major',
                                    labelsize=ticks_fontsize)

        self.gridspec.update(left=.08, right=.98, top=.92, bottom=.03,
                             hspace=.37, wspace=.22)

        plt.show()

    def create_pdf(self, pdf_name=None, pdf_prefix=None):
        """ Make a pdf out of the created figure into the Nexus session dir.
        If pdf_name is not specified, automatically name according to current
        trial. """
        if not self.fig:
            raise Exception('No figure to save!')
        # resize to A4
        # self.fig.set_size_inches([8.27,11.69])
        if pdf_name:
            pdf_name = self.trial.sessionpath + pdf_name
        else:
            if not pdf_prefix:
                pdf_prefix = 'Nexus_plot_'
            pdf_name = (self.trial.sessionpath + pdf_prefix +
                        self.trial.trialname + '.pdf')
        if op.isfile(pdf_name):
            pass  # can prevent overwriting here
        try:
            with PdfPages(pdf_name) as pdf:
                pdf.savefig(self.fig)
        except IOError:
            messagebox('Error writing PDF file,'
                       'check that file is not already open.')










