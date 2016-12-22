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
import nexus
from trial import Trial
import matplotlib.pyplot as plt
from matplotlib import pylab
from matplotlib.backends.backend_pdf import PdfPages
import matplotlib.gridspec as gridspec
from guiutils import error_exit, messagebox
import os.path as op
import os
import subprocess
from config import Config


class Plotter(object):

    def __init__(self, layout=None, normaldata=None):
        """ Plot gait data.

        layout: list of lists
            Variables to be plotted. Each list is a row of variables.
            If none, must be set before plotting (plotter.layout = layout)
        normaldata: list of lists
            Corresponding normal data files for each plot. Will override
            default normal data settings.
        """
        if layout:
            self.layout = layout
        else:
            self._layout = None
        self.trial = None
        self.fig = None
        self.normaldata = normaldata
        self.legendnames = []
        self.modelartists = []
        self.emgartists = []
        self.cfg = Config()

    @property
    def layout(self):
        return self._layout

    @layout.setter
    def layout(self, layout):
        if (not isinstance(layout, list) or not
           all([isinstance(item, list) for item in layout])):
            raise ValueError('Plot variables must be a list of lists')
        self._layout = layout
        self.allvars = [item for row in layout for item in row]
        self.nrows = len(layout)
        self.ncols = len(layout[0])

    def open_nexus_trial(self):
        source = nexus.viconnexus()
        self.open_trial(source)

    def open_trial(self, source):
        self.trial = Trial(source)

    def external_play_video(self, vidfile):
        """ Launch video player (defined in config) to play vidfile. """
        PLAYER_CMD = self.cfg.videoplayer_path
        if not (op.isfile(PLAYER_CMD) and os.access(PLAYER_CMD, os.X_OK)):
            error_exit('Invalid video player executable: %S' % PLAYER_CMD)
        PLAYER_OPTS = self.cfg.videoplayer_opts
        # command needs to be constructed in a very particular way
        # see subprocess.list2cmdline
        subprocess.Popen([PLAYER_CMD]+PLAYER_OPTS.split()+[vidfile])

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
        elif var in ('model_legend', 'emg_legend'):
            return var
        else:
            raise ValueError('Unknown variable')

    def _plot_height_ratios(self):
        plotheightratios = []
        for row in self._layout:
            if all([self._var_type(var) == 'model' for var in row]):
                plotheightratios.append(1)
            else:
                plotheightratios.append(self.cfg.plot_analog_plotheight)
        return plotheightratios

    def plot_trial(self, model_cycles={'R': 1, 'L': 1},
                   emg_cycles={'R': 1, 'L': 1},
                   context=None, t=None, plotheightratios=None,
                   model_tracecolor=None, model_linestyle='-',
                   linestyles_context=False,
                   emg_tracecolor=None, plot_model_normaldata=True,
                   plot_emg_normaldata=True, superpose=True, show=True,
                   maintitle=None, maintitleprefix=None):

        """ Create plot of variables. Parameters:

        model_cycles : dict of int | int | dict of list | 'all' | None
                Gait cycles to plot. Default is first cycle (1) for
                both contexts. Multiple cycles can be given as lists.
                If None, plot unnormalized data. 'context' must then be
                specified.
                If 'all', plot all available cycles.
                Model variable names are modified according to context, e.g.
                'HipMomentX' -> 'LHipMomentX' for a left side gait cycle.
        emg_cycles : dict of int | int | dict of list | 'all' | None
                Same as above, applied to EMG variables.
        t : array-like
                Time axis for unnormalized data. If None, plot whole time
                axis.
        plot_model_normaldata : bool
                Whether to plot normal data. Uses either default normal data
                (in site_defs) or the data given when creating the plotter
                instance.
        plot_emg_normaldata : bool
                Whether to plot normal data. Uses either default normal data
                (in site_defs) or the data given when creating the plotter
                instance.
        maintitle : str
                Plot title.
        maintitleprefix : str
                If maintitle is not set, title will be set to
                maintitleprefix + trial name.

        If a plot already exists, new data will be superposed on it.

        """

        if not self.trial:
            raise ValueError('No trial to plot, call open_trial() first')
        if self._layout is None:
            raise ValueError('No layout set')
        if not maintitle:
            if maintitleprefix is None:
                maintitleprefix = ''
            maintitle = maintitleprefix + self.trial.trialname
        if self.fig is None or not superpose:
            superposing = False
            self.fig = plt.figure(figsize=self.cfg.plot_totalfigsize)
            self.gridspec = gridspec.GridSpec(self.nrows, self.ncols,
                                              height_ratios=plotheightratios)
        else:
            superposing = True
        if plotheightratios is None:
            plotheightratios = self._plot_height_ratios()

        def _get_cycles(cycles):
            """ Get specified cycles from the gait trial """
            if cycles is None:
                cycles = [None]  # make iterable
            elif isinstance(cycles, int):
                cycles = {'L': cycles, 'R': cycles}
            elif cycles == 'all':
                cycles = self.trial.cycles
            if isinstance(cycles, dict):  # not elif due to conversion above
                for side in ['L', 'R']:  # add L/R if needed
                    if side not in cycles:
                        cycles[side] = [None]
                # convert ints to lists
                cycles.update({key: [val] for (key, val) in cycles.items()
                              if isinstance(val, int)})
                # get the specified cycles
                cycles = [self.trial.get_cycle(side, ncycle) for side in ['L', 'R']
                          for ncycle in cycles[side] if ncycle]
            return cycles

        model_cycles = _get_cycles(model_cycles)
        emg_cycles = _get_cycles(emg_cycles)

        for i, var in enumerate(self.allvars):
            var_type = self._var_type(var)
            if var_type is None:
                continue
            ax = plt.subplot(self.gridspec[i])
            if var_type == 'model':
                model = models.model_from_var(var)
                for cycle in model_cycles:
                    if cycle is not None:  # plot normalized data
                        self.trial.set_norm_cycle(cycle)
                        context = cycle.context
                    elif context is None:
                        raise ValueError('Must specify context for '
                                         'plotting unnormalized variable')
                    # plot, unless kinetic var and kinetics not available
                    if not (models.pig_lowerbody.is_kinetic_var(var) and
                       cycle not in self.trial.kinetics_cycles):
                        varname = context + var
                        x_, data = self.trial[varname]
                        x = x_ / self.trial.framerate if cycle is None else x_
                        tcolor = (model_tracecolor if model_tracecolor
                                  else self.cfg.model_tracecolors[context])
                        lstyle = (self.cfg.model_linestyles[context] if
                                  linestyles_context else model_linestyle)
                        ax.plot(x, data, tcolor, linestyle=lstyle,
                                linewidth=self.cfg.model_linewidth)
                    # set labels, ticks, etc. after plotting last cycle
                    if cycle == model_cycles[-1] and not superposing:
                        ax.set(ylabel=model.ylabels[varname])  # no xlabel now
                        ax.xaxis.label.set_fontsize(self.cfg.
                                                    plot_label_fontsize)
                        ax.yaxis.label.set_fontsize(self.cfg.
                                                    plot_label_fontsize)
                        ax.set_title(model.varlabels[varname])
                        ax.title.set_fontsize(self.cfg.plot_title_fontsize)
                        ax.axhline(0, color='black')  # zero line
                        ax.locator_params(axis='y', nbins=6)  # less tick marks
                        ax.tick_params(axis='both', which='major',
                                       labelsize=self.cfg.plot_ticks_fontsize)
                        ylim = ax.get_ylim()
                        # model specific adjustments
                        if model == models.pig_lowerbody:
                            ylim0 = -10 if ylim[0] == 0 else ylim[0]
                            ylim1 = 10 if ylim[1] == 0 else ylim[1]
                            ax.set_ylim(ylim0, ylim1)
                        elif model == models.musclelen:
                            ax.set_ylim(ylim[0]-10, ylim[1]+10)
                        if cycle is None:
                            ax.set(xlabel='Time (s)')
                            ax.xaxis.label.set_fontsize(self.cfg.
                                                        plot_label_fontsize)
                        if plot_model_normaldata and cycle is not None:
                            tnor, ndata = model.get_normaldata(varname)
                            if ndata is not None:
                                # assume (mean, stddev) for normal data
                                # fill region between mean-stddev, mean+stddev
                                nor = ndata[:, 0]
                                nstd = (ndata[:, 1] if ndata.shape[1] == 2
                                        else 0)
                                ax.fill_between(tnor, nor-nstd, nor+nstd,
                                                color=self.cfg.
                                                model_normals_color,
                                                alpha=self.cfg.
                                                model_normals_alpha)

            elif var_type == 'emg':
                for cycle in emg_cycles:
                    if cycle is not None:  # plot normalized data
                        self.trial.set_norm_cycle(cycle)
                    x_, data = self.trial[var]
                    x = x_ / self.trial.analograte if cycle is None else x_
                    # TODO: annotate
                    tcolor = (emg_tracecolor if emg_tracecolor else
                              self.cfg.emg_tracecolor)
                    ax.plot(x, data*self.cfg.emg_multiplier, tcolor,
                            linewidth=self.cfg.emg_linewidth)
                    if cycle == emg_cycles[-1] and not superposing:
                        ax.set(ylabel=self.cfg.emg_ylabel)
                        ax.yaxis.label.set_fontsize(self.cfg.
                                                    plot_label_fontsize)
                        ax.set_title(var)
                        ax.title.set_fontsize(self.cfg.plot_title_fontsize)
                        ax.locator_params(axis='y', nbins=4)
                        # tick font size
                        ax.tick_params(axis='both', which='major',
                                       labelsize=self.cfg.plot_ticks_fontsize)
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
                            ax.xaxis.label.set_fontsize(self.cfg.
                                                        plot_label_fontsize)

            elif var_type in ('model_legend', 'emg_legend'):
                self.legendnames.append('%s   %s   %s' % (
                                        self.trial.trialname,
                                        self.trial.eclipse_data['DESCRIPTION'],
                                        self.trial.eclipse_data['NOTES']))
                if var_type == 'model_legend':
                    legtitle = ['Model traces:']
                    artists = self.modelartists
                    artists.append(plt.Line2D((0, 1), (0, 0),
                                   color=model_tracecolor,
                                   linewidth=2,
                                   linestyle=lstyle))
                else:
                    legtitle = ['EMG traces:']
                    artists = self.emgartists
                    artists.append(plt.Line2D((0, 1), (0, 0),
                                              linewidth=2,
                                              color=emg_tracecolor))
                plt.axis('off')
                nothing = [plt.Rectangle((0, 0), 1, 1, fc="w", fill=False,
                                         edgecolor='none', linewidth=0)]
                ax.legend(nothing+artists,
                          legtitle+self.legendnames,
                          prop={'size': self.cfg.plot_label_fontsize},
                          loc='upper center')

        plt.suptitle(maintitle, fontsize=12, fontweight="bold")
        # magic adjustments to fig geometry
        self.gridspec.update(left=.08, right=.98, top=.92, bottom=.05,
                             hspace=.37, wspace=.22)
        if show:
            plt.show()

    def show(self):
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

