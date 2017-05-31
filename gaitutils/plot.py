# -*- coding: utf-8 -*-
"""

Plot gait data

@author: jnu@iki.fi
"""

import models
import nexus
import numutils
from trial import Trial
import matplotlib.pyplot as plt
from matplotlib import pylab
from matplotlib.backends.backend_pdf import PdfPages
import matplotlib.gridspec as gridspec
import os.path as op
import os
import subprocess
from config import cfg
import logging

logger = logging.getLogger(__name__)


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
        self.cfg = cfg

    @property
    def layout(self):
        return self._layout

    @layout.setter
    def layout(self, layout):
        if (not isinstance(layout, list) or not
           all([isinstance(item, list) for item in layout])):
            raise ValueError('Layout must be a list of lists')
        self._layout = layout
        self.allvars = [item for row in layout for item in row]
        self.nrows = len(layout)
        if self.nrows == 0:
            raise ValueError('No data to plot')
        self.ncols = len(layout[0])

    def open_nexus_trial(self):
        source = nexus.viconnexus()
        self.open_trial(source)

    def open_trial(self, source):
        self.trial = Trial(source)

    def external_play_video(self, vidfile):
        """ Launch video player (defined in config) to play vidfile. """
        PLAYER_CMD = self.cfg.general.videoplayer_path
        if not (op.isfile(PLAYER_CMD) and os.access(PLAYER_CMD, os.X_OK)):
            raise ValueError('Invalid video player executable: %s'
                             % PLAYER_CMD)
        PLAYER_OPTS = self.cfg.general.videoplayer_opts
        # command needs to be constructed in a very particular way
        # see subprocess.list2cmdline
        subprocess.Popen([PLAYER_CMD]+PLAYER_OPTS.split()+[vidfile])

    def move_plot_window(self, x, y):
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
        # check whether it's a configured EMG channel or exists in the data
        # source (both are ok)
        elif (self.trial.emg.is_channel(var) or
              var in self.cfg.emg.channel_labels):
            return 'emg'
        elif var in ('model_legend', 'emg_legend'):
            return var
        else:
            raise ValueError('Unknown variable %s' % var)

    def _plot_height_ratios(self):
        """ Automatically adjust height ratios, if they are not specified """
        plotheightratios = []
        for row in self._layout:
            if all([self._var_type(var) == 'model' for var in row]):
                plotheightratios.append(1)
            else:
                plotheightratios.append(self.cfg.plot.analog_plotheight)
        return plotheightratios

    def tight_layout(self):
        """ Customized tight layout """
        self.gridspec.tight_layout(self.fig)
        # space for main title
        top = (self.figh - self.cfg.plot.titlespace) / self.figh
        # decrease vertical spacing
        hspace = .6
        # self.gridspec.update(hspace=hspace)
        # self.gridspec.update(top=top)
        self.gridspec.update(top=top, hspace=hspace)

    def plot_trial(self,
                   model_cycles=cfg.plot.default_model_cycles,
                   emg_cycles=cfg.plot.default_emg_cycles,
                   plotheightratios=None,
                   plotwidthratios=None,
                   model_tracecolor=None,
                   model_linestyle='-',
                   model_alpha=1.0,
                   split_model_vars=True,
                   auto_match_model_cycle=True,
                   x_axis_is_time=True,
                   match_pig_kinetics=True,
                   auto_match_emg_cycle=True,
                   linestyles_context=False,
                   annotate_emg=True,
                   emg_tracecolor=cfg.plot.emg_tracecolor,
                   emg_alpha=cfg.plot.emg_alpha,
                   plot_model_normaldata=True,
                   plot_emg_normaldata=True,
                   plot_emg_rms=False,
                   sharex=True,
                   superpose=False,
                   show=True,
                   maintitle=None,
                   maintitleprefix=None):

        """ Create plot of variables. Parameters:

        model_cycles : dict of int |  dict of list | 'all' | None
                Gait cycles to plot. Defaults to first cycle (1) for
                both contexts. Multiple cycles can be given as lists.
                If None, plot unnormalized data. If 'all', plot all cycles.
                If 'forceplate', plot cycles that start on valid forceplate
                contact.
        emg_cycles : dict of int | int | dict of list | 'all' | None
                Same as above, applied to EMG variables.
        t : array-like
                Time axis for unnormalized data. If None, plot complete time
                axis.
        plotheightratios : list
                Force height ratios of subplot rows, e.g. [1 2 2 2] would
                make first row half the height of others.
        model_tracecolor : Matplotlib colorspec
                Select line color for model variables. If None, will be
                automatically selected
        model_alpha : float
                Alpha value for model variable traces (0.0 - 1.0)
        split_model_vars: bool
                If model var does not have a leading context 'L' or 'R', a side
                will be prepended according to the gait cycle context.
                E.g. 'HipMoment' -> 'LHipMoment'.
                This allows convenient L/R overlay of e.g. kinematics variables
                by specifying the variable without context (and plotting cycles
                with both contexts)
        auto_match_model_cycle: bool
                If True, the model variable will be plotted only for cycles
                whose context matches the context of the variable. E.g.
                'LHipMomentX' will be plotted only for left side cycles.
                If False, the variable will be plotted for all cycles.
        x_axis_is_time: bool
                For unnormalized variables, whether x axis is in seconds
                (default) or in frames.
        match_pig_kinetics: bool
                If True, Plug-in Gait kinetics variables will be plotted only
                for cycles that begin with forceplate strike.
        auto_match_emg_cycle: bool
                If True, the EMG channel will be plotted only for cycles
                whose context matches the context of the channel name. E.g.
                'LRec' will be plotted only for left side cycles.
                If False, the channel will be plotted for all cycles.
        model_linestyle : Matplotlib linestyle
                Select line style for model variables.
        linestyles_context:
                Automatically select line style for model variables according
                to context (defined in config)
        emg_tracecolor : Matplotlib color
                Select line color for EMG variables. If None, will be
                automatically selected (defined in config)
        emg_alpha : float
                Alpha value for EMG traces (0.0 - 1.0)
        plot_model_normaldata : bool
                Whether to plot normal data. Uses either default normal data
                (in site_defs) or the data given when creating the plotter
                instance.
        plot_emg_normaldata : bool
                Whether to plot normal data. Uses either default normal data
                (in site_defs) or the data given when creating the plotter
                instance.
        plot_emg_rms : bool | string
                Whether to plot EMG RMS superposed on the EMG signal.
                If 'rms_only', plot only RMS.
        sharex : bool
                Link the x axes together (will affect zooming)
        superpose : bool
                If superpose=False, create new figure. Otherwise superpose
                on existing figure.
        show : bool
                Whether to show the plot after plotting is finished. Can also
                set show=False and call plotter.show() explicitly.
        maintitle : str
                Main title for the plot.
        maintitleprefix : str
                If maintitle is not set, title will be set to
                maintitleprefix + trial name.
        """

        if not self.trial:
            raise ValueError('No trial to plot, call open_trial() first')

        if self._layout is None:
            raise ValueError('No layout set')

        if maintitle is None:
            if maintitleprefix is None:
                maintitleprefix = ''
            maintitle = maintitleprefix + self.trial.trialname

        # auto adjust plot heights
        if plotheightratios is None:
            plotheightratios = self._plot_height_ratios()
        elif len(plotheightratios) != len(self.nrows):
            raise ValueError('n of height ratios must match n of rows')
        plotaxes = []

        if self.fig is None or not superpose:
            # auto size fig according to n of subplots w, limit size
            self.figh = min(self.nrows*self.cfg.plot.inch_per_row + 1,
                            self.cfg.plot.maxh)
            self.figw = min(self.ncols*self.cfg.plot.inch_per_col,
                            self.cfg.plot.maxw)
            logger.debug('new figure: width %.2f, height %.2f'
                         % (self.figw, self.figh))
            self.fig = plt.figure(figsize=(self.figw, self.figh))
            self.gridspec = gridspec.GridSpec(self.nrows, self.ncols,
                                              height_ratios=plotheightratios,
                                              width_ratios=plotwidthratios)



        def _axis_annotate(ax, text):
            """ Annotate at center of axis """
            ctr = sum(ax.get_xlim())/2, sum(ax.get_ylim())/2.
            ax.annotate(text, xy=ctr, ha="center", va="center")

        def _no_ticks_or_labels(ax):
            ax.tick_params(axis='both', which='both', bottom='off',
                           top='off', labelbottom='off', right='off',
                           left='off', labelleft='off')

        def _shorten_name(name):
            """ Shorten overlong names for legend etc. """
            MAX_LEN = 10
            return name if len(name) <= MAX_LEN else '..'+name[-MAX_LEN+2:]

        def _get_cycles(cycles):
            """ Get specified cycles from the gait trial """
            if cycles is None:
                cycles = [None]  # listify
            elif cycles == 'all':
                cycles = self.trial.cycles
            elif cycles == 'forceplate':
                cycles = [cyc for cyc in self.trial.cycles
                          if cyc.on_forceplate]
            elif isinstance(cycles, dict):
                for side in ['L', 'R']:  # add L/R side if needed
                    if side not in cycles:
                        cycles[side] = [None]
                # convert ints to lists
                cycles.update({key: [val] for (key, val) in cycles.items()
                              if isinstance(val, int)})
                # get the specified cycles from trial
                cycles = [self.trial.get_cycle(side, ncycle)
                          for side in ['L', 'R']
                          for ncycle in cycles[side] if ncycle]
            return cycles

        model_cycles = _get_cycles(model_cycles)
        emg_cycles = _get_cycles(emg_cycles)

        for i, var in enumerate(self.allvars):
            var_type = self._var_type(var)
            if var_type is None:
                continue
            if sharex and len(plotaxes) > 0:
                ax = plt.subplot(self.gridspec[i], sharex=plotaxes[-1])
            else:
                ax = plt.subplot(self.gridspec[i])

            if var_type == 'model':
                model = models.model_from_var(var)
                for cycle in model_cycles:
                    logging.debug('cycle %s' % cycle)
                    if cycle is not None:  # plot normalized data
                        self.trial.set_norm_cycle(cycle)
                    if split_model_vars and var[0].upper() not in ['L', 'R']:
                        varname = cycle.context + var
                    else:
                        varname = var
                    # check for kinetics variable
                    kin_ok = True
                    if match_pig_kinetics:
                        if model == models.pig_lowerbody:
                            if model.is_kinetic_var(var):
                                kin_ok = cycle.on_forceplate
                    # do the actual plotting if necessary
                    if kin_ok and (varname[0] == cycle.context or not
                       auto_match_model_cycle or cycle is None):
                        logging.debug('plotting data for %s' % varname)
                        x_, data = self.trial[varname]
                        x = (x_ / self.trial.framerate if cycle is None and
                             x_axis_is_time else x_)
                        tcolor = (model_tracecolor if model_tracecolor
                                  else self.cfg.plot.model_tracecolors
                                  [cycle.context])
                        lstyle = (self.cfg.plot.model_linestyles
                                  [cycle.context] if linestyles_context else
                                  model_linestyle)
                        ax.plot(x, data, tcolor, linestyle=lstyle,
                                linewidth=self.cfg.plot.model_linewidth,
                                alpha=model_alpha)
                        # tighten x limits
                        ax.set_xlim(x[0], x[-1])
                    else:
                        logging.debug('not plotting data for %s' % varname)

                    # set labels, ticks, etc. after plotting last cycle
                    if cycle == model_cycles[-1]:
                        ax.set(ylabel=model.ylabels[varname])  # no xlabel now
                        ax.xaxis.label.set_fontsize(self.cfg.
                                                    plot.label_fontsize)
                        ax.yaxis.label.set_fontsize(self.cfg.
                                                    plot.label_fontsize)
                        subplot_title = model.varlabels[varname]
                        prev_title = ax.get_title()
                        if prev_title and prev_title != subplot_title:
                            subplot_title = prev_title + ' / ' + subplot_title
                        ax.set_title(subplot_title)
                        ax.title.set_fontsize(self.cfg.plot.title_fontsize)
                        ax.axhline(0, color='black')  # zero line
                        ax.locator_params(axis='y', nbins=6)  # less tick marks
                        ax.tick_params(axis='both', which='major',
                                       labelsize=self.cfg.plot.ticks_fontsize)
                        if cycle is None and var in self.layout[-1]:
                            xlabel = 'Time (s)' if x_axis_is_time else 'Frame'
                            ax.set(xlabel=xlabel)
                            ax.xaxis.label.set_fontsize(self.cfg.
                                                        plot.label_fontsize)
                        if model.get_normaldata(varname):
                            if plot_model_normaldata and cycle is not None:
                                tnor, ndata = model.get_normaldata(varname)
                                if ndata is not None:
                                    # assume (mean, stddev) for normal data
                                    # fill region between mean-stddev, mean+stddev
                                    nor = ndata[:, 0]
                                    nstd = (ndata[:, 1] if ndata.shape[1] == 2
                                            else 0)
                                    ax.fill_between(tnor, nor-nstd, nor+nstd,
                                                    color=self.cfg.plot.
                                                    model_normals_color,
                                                    alpha=self.cfg.plot.
                                                    model_normals_alpha)

            elif var_type == 'emg':
                for cycle in emg_cycles:
                    if cycle is not None:  # plot normalized data
                        self.trial.set_norm_cycle(cycle)
                    try:
                        x_, data = self.trial[var]
                    except KeyError:  # channel not found
                        _no_ticks_or_labels(ax)
                        if annotate_emg:
                            _axis_annotate(ax, 'not found')
                        break  # skip all cycles
                    if not self.trial.emg.status_ok(var):
                        _no_ticks_or_labels(ax)
                        if annotate_emg:
                            _axis_annotate(ax, 'disconnected')
                        break  # data no good - skip all cycles
                    x = (x_ / self.trial.analograte if cycle is None and
                         x_axis_is_time else x_ / 1.)
                    if cycle is None and not x_axis_is_time:
                        # analog -> frames
                        x /= self.trial.samplesperframe
                    if (cycle is None or var[0] == cycle.context or not
                       auto_match_emg_cycle):
                        # plot data and/or rms
                        if plot_emg_rms != 'rms_only':
                            ax.plot(x, data*self.cfg.plot.emg_multiplier,
                                    emg_tracecolor,
                                    linewidth=self.cfg.plot.emg_linewidth,
                                    alpha=emg_alpha)
                        if plot_emg_rms is not False:
                            rms = numutils.rms(data, self.cfg.emg.rms_win)
                            ax.plot(x, rms*self.cfg.plot.emg_multiplier,
                                    emg_tracecolor,
                                    linewidth=self.cfg.plot.emg_rms_linewidth,
                                    alpha=emg_alpha)
                    if cycle == emg_cycles[-1]:
                        # last cycle; plot scales, titles etc.
                        ax.set(ylabel=self.cfg.plot.emg_ylabel)
                        ax.yaxis.label.set_fontsize(self.cfg.
                                                    plot.label_fontsize)
                        subplot_title = (self.cfg.emg.channel_labels[var] if
                                         var in self.cfg.emg.channel_labels
                                         else var)
                        prev_title = ax.get_title()
                        if prev_title and prev_title != subplot_title:
                            subplot_title = prev_title + ' / ' + subplot_title
                        ax.set_title(subplot_title)
                        ax.title.set_fontsize(self.cfg.plot.title_fontsize)
                        ax.locator_params(axis='y', nbins=4)
                        # tick font size
                        ax.tick_params(axis='both', which='major',
                                       labelsize=self.cfg.plot.ticks_fontsize)
                        ax.set_xlim(min(x), max(x))
                        ysc = self.cfg.plot.emg_yscale
                        ax.set_ylim(ysc[0]*self.cfg.plot.emg_multiplier,
                                    ysc[1]*self.cfg.plot.emg_multiplier)
                        if (plot_emg_normaldata and cycle is not None and
                           var in self.cfg.emg.channel_normaldata):
                            # plot EMG normal bars
                            emgbar_ind = self.cfg.emg.channel_normaldata[var]
                            for k in range(len(emgbar_ind)):
                                inds = emgbar_ind[k]
                                plt.axvspan(inds[0], inds[1], alpha=self.cfg.
                                            plot.emg_normals_alpha,
                                            color=self.cfg.
                                            plot.emg_normals_color)
                        if cycle is None and var in self.layout[-1]:
                            xlabel = 'Time (s)' if x_axis_is_time else 'Frame'
                            ax.set(xlabel=xlabel)
                            ax.xaxis.label.set_fontsize(self.cfg.
                                                        plot.label_fontsize)

            elif var_type in ('model_legend', 'emg_legend'):
                self.legendnames.append('%s   %s   %s' % (
                                        _shorten_name(self.trial.trialname),
                                        self.trial.eclipse_data['DESCRIPTION'],
                                        self.trial.eclipse_data['NOTES']))
                if var_type == 'model_legend':
                    legtitle = ['Model traces:']
                    artists = self.modelartists
                    artists.append(plt.Line2D((0, 1), (0, 0),
                                   color=model_tracecolor, linewidth=2,
                                   linestyle=lstyle))
                else:
                    legtitle = ['EMG traces:']
                    artists = self.emgartists
                    artists.append(plt.Line2D((0, 1), (0, 0), linewidth=2,
                                              color=emg_tracecolor))
                plt.axis('off')
                nothing = [plt.Rectangle((0, 0), 1, 1, fc="w", fill=False,
                                         edgecolor='none', linewidth=0)]
                ax.legend(nothing+artists,
                          legtitle+self.legendnames, loc='upper center',
                          ncol=2,
                          prop={'size': self.cfg.plot.legend_fontsize})
            plotaxes.append(ax)

        plt.suptitle(maintitle, fontsize=self.cfg.plot.maintitle_fontsize,
                     fontweight="bold")
        self.tight_layout()
        
        if show:
            self.show()

    def title_with_eclipse_info(self, prefix=''):
        """ Create title: prefix + trial name + Eclipse description and
        notes """
        desc = self.trial.eclipse_data['DESCRIPTION']
        notes = self.trial.eclipse_data['NOTES']
        maintitle = ('%s %s' % (prefix, self.trial.trialname) if prefix else
                     self.trial.trialname)
        maintitle += ' (%s)' % desc if desc else ''
        maintitle += ' (%s)' % notes if notes else ''
        return maintitle

    def show(self):
        """ Show all figures """
        plt.show()

    def create_pdf(self, pdf_name=None, pdf_prefix=None):
        """ Make a pdf out of the created figure into the Nexus session dir.
        If pdf_name is not specified, automatically name according to current
        trial. """
        if not self.fig:
            raise ValueError('No figure to save!')
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
            logger.debug('writing %s' % pdf_name)
            with PdfPages(pdf_name) as pdf:
                pdf.savefig(self.fig)
        except IOError:
            raise IOError('Error writing PDF file, '
                          'check that file is not already open.')
