# -*- coding: utf-8 -*-
"""

-1 instance per layout
-separate methods for adding normal data?
-exception handling?
-plot unnormalized data
-plot avg/stddev?


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
from config import Config


class Plotter():

    def __init__(self, plotvars, normaldata=None):
        """ Plot gait data.

        plotvars: list of lists
            Variables to be plotted. Each list is a row of variables.
        normaldata: list of lists
            Corresponding normal data files for each plot. Will override
            default normal data settings.
        """

        if (not isinstance(plotvars, list) or not
           all([isinstance(item, list)for item in plotvars])):
            raise ValueError('Plot variables must be a list of lists')
        self.nrows = len(plotvars)
        self.ncols = len(plotvars[0])
        self.plotvars = plotvars
        self.trial = None
        self.fig = None
        self.allvars = [item for row in plotvars for item in row]
        self.normaldata = normaldata
        self.cfg = Config()

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
                   emg_tracecolor=None, plot_model_normaldata=True,
                   plot_emg_normaldata=True, superpose=True,
                   maintitle=None, maintitleprefix=None):

        """ Create plot of variables. Parameters:

        cycles : dict of int | int | dict of list | 'all' | None
                Gait cycles to plot. Default is first cycle (1) for
                both sides. Multiple cycles can be given as lists.
                If None, plot unnormalized data. 'context' must be specified.
                If 'all', plot all available cycles.
                Model variable names are modified according to context, e.g.
                'HipMomentX' -> 'LHipMomentX' for a left side gait cycle.
        t       Time axis for unnormalized data. If None, plot whole time
                axis.
        plot_model_normaldata : bool
                Whether to plot normal data. Uses either default normal data
                (in site_defs) or the data given when creating the plotter
                instance.
        plot_emg_normaldata : bool
                Whether to plot normal data. Uses either default normal data
                (in site_defs) or the data given when creating the plotter
                instance.

        If a plot already exists, new data will be superposed on it.

        """

        if not self.trial:
            raise ValueError('No trial to plot, call open_trial() first')
        if not maintitle:
            maintitle = maintitleprefix + self.trial.trialname
        if self.fig is None or not superpose:
            superposing = False
            self.fig = plt.figure(figsize=self.cfg.totalfigsize)
        else:
            superposing = True
        if plotheightratios is None:
            plotheightratios = [1] * self.nrows  # set plot heights all equal
        self.gridspec = gridspec.GridSpec(self.nrows, self.ncols,
                                          height_ratios=plotheightratios)
        if cycles is None:
            cycles = [None]  # make iterable
        elif isinstance(cycles, int):
            cycles = {'L': cycles, 'R': cycles}
        elif cycles == 'all':
            cycles = self.trial.cycles
        if isinstance(cycles, dict):  # not elif due to dict conversion above
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
                            raise ValueError('Must specify context for '
                                             'plotting unnormalized variable')
                    varname = context + var
                    x, data = self.trial[varname]
                    tcolor = (model_tracecolor if model_tracecolor
                              else self.cfg.model_tracecolors[context])
                    ax.plot(x, data, tcolor)
                    # set labels, ticks, etc. after plotting last cycle
                    if cycle == cycles[-1] and not superposing:
                        ax.set(ylabel=model.ylabels[varname])  # no xlabel for now
                        ax.xaxis.label.set_fontsize(self.cfg.label_fontsize)
                        ax.yaxis.label.set_fontsize(self.cfg.label_fontsize)
                        ax.set_title(model.varlabels[varname])
                        ax.title.set_fontsize(self.cfg.title_fontsize)
                        ax.axhline(0, color='black')  # zero line
                        ax.locator_params(axis='y', nbins=6)  # less y tick marks
                        ax.tick_params(axis='both', which='major',
                                       labelsize=self.cfg.ticks_fontsize)
                        ylim = ax.get_ylim()
                        # model specific adjustments
                        if model == models.pig_lowerbody:
                            ylim0 = -10 if ylim[0] == 0 else ylim[0]
                            ylim1 = 10 if ylim[1] == 0 else ylim[1]
                            ax.set_ylim(ylim0, ylim1)
                        elif model == models.musclelen:
                            ax.set_ylim(ylim[0]-10, ylim[1]+10)
                        if plot_model_normaldata:
                            tnor, ndata = model.get_normaldata(varname)
                            if ndata is not None:
                                # assume (mean, stddev) for normal data
                                # fill region between mean-stddev, mean+stddev
                                nor = ndata[:, 0]
                                nstd = (ndata[:, 1] if ndata.shape[1] == 2
                                        else 0)
                                ax.fill_between(tnor, nor-nstd, nor+nstd,
                                                color=self.cfg.normals_color,
                                                alpha=self.cfg.normals_alpha)

            elif var_type == 'emg':
                for cycle in cycles:
                    if cycle is not None:  # plot normalized data
                        self.trial.set_norm_cycle(cycle)
                    x_, data = self.trial[var]
                    x = x_ / self.trial.analograte if cycle is None else x_
                    # TODO: annotate
                    ax.plot(x, data*self.cfg.emg_multiplier)
                    if cycle == cycles[-1] and not superposing:
                        ax.set(ylabel=self.cfg.emg_ylabel)
                        ax.yaxis.label.set_fontsize(self.cfg.label_fontsize)
                        ax.set_title(var)
                        ax.title.set_fontsize(self.cfg.title_fontsize)
                        ax.locator_params(axis='y', nbins=4)
                        # tick font size
                        ax.tick_params(axis='both', which='major',
                                       labelsize=self.cfg.ticks_fontsize)
                        ax.set_xlim(min(x), max(x))
                        ysc = self.cfg.emg_yscale
                        ax.set_ylim(ysc[0]*self.cfg.emg_multiplier,
                                    ysc[1]*self.cfg.emg_multiplier)
                        if plot_emg_normaldata and cycle is not None:
                            # plot EMG normal bars
                            emgbar_ind = self.cfg.emg_normals[var]
                            for k in range(len(emgbar_ind)):
                                inds = emgbar_ind[k]
                                plt.axvspan(inds[0], inds[1],
                                            alpha=self.cfg.emg_normals_alpha,
                                            color=self.cfg.emg_normals_color)
                        if cycle is None:
                            ax.set(xlabel='Time (s)')
                            ax.xaxis.label.set_fontsize(self.cfg.label_fontsize)

                

        plt.suptitle(maintitle, fontsize=12, fontweight="bold")
        self.gridspec.update(left=.08, right=.98, top=.92, bottom=.05,
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
            messagebox('Error writing PDF file, '
                       'check that file is not already open.')










