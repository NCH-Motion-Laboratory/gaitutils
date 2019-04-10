# -*- coding: utf-8 -*-
"""

matplotlib based plotting functions

@author: Jussi (jnu@iki.fi)
"""

from __future__ import division

from builtins import zip
from builtins import range
from builtins import object
from itertools import cycle
import matplotlib
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.lines import Line2D
import matplotlib.gridspec as gridspec
import os.path as op
import numpy as np
import logging

from .plot_common import _truncate_trialname, _get_legend_entry, _var_title
from .. import models, numutils, normaldata, layouts, cfg, GaitDataError
from ..trial import Trial, nexus_trial, Gaitcycle
from ..stats import AvgTrial


logger = logging.getLogger(__name__)


def _plot_height_ratios(layout):
    """Calculate height ratios for mpl plot"""
    plotheightratios = []
    for row in layout:
        if all([models.model_from_var(var) for var in row]):
            plotheightratios.append(1)
        else:
            plotheightratios.append(cfg.plot.analog_plotheight)
    return plotheightratios


def _annotate_axis(ax, text):
    """Annotate at center of mpl axis"""
    ax.annotate(text, xy=(.5, .5), xycoords='axes fraction',
                ha="center", va="center", fontsize=cfg.plot.title_fontsize)


def _remove_ticks_and_labels(ax):
    ax.tick_params(axis='both', which='both', bottom=False,
                   top=False, labelbottom=False, right=False,
                   left=False, labelleft=False)


def plot_trials(trials, layout, model_normaldata=None, model_cycles=None,
                emg_cycles=None, legend_type='full', trial_linestyles='same',
                supplementary_data=None, maintitle=None):
    """plot trials and return Figure instance"""

    if not trials:
        raise GaitDataError('No trials')

    if supplementary_data is None:
        supplementary_data = dict()

    if model_normaldata is None:
        model_normaldata = normaldata.read_all_normaldata()

    nrows, ncols = layouts.check_layout(layout)

    # mpl default colors as a cycle
    colors = matplotlib.rcParams['axes.prop_cycle']()
    #if len(trials) > len(colors_list):
    #    logger.warning('Not enough colors for plot')

    session_linestyles = dict()
    linestyles = cycle(['solid', 'dash', 'dot', 'dashdot'])

    # compute figure width and height - only used for interactive figures
    figh = min(nrows*cfg.plot.inch_per_row + 1, cfg.plot.maxh)
    figw = min(ncols*cfg.plot.inch_per_col, cfg.plot.maxw)
    fig = Figure(figsize=(figw, figh), constrained_layout=True)

    plotheightratios = _plot_height_ratios(layout)
    plotheightratios.append(1)  # for legend
    gridspec_ = gridspec.GridSpec(nrows+1, ncols, figure=fig,
                                  height_ratios=plotheightratios,
                                  width_ratios=None)
    # spacing adjustments for the plot, see Figure.tight_layout()
    # pad == plot margins
    # w_pad, h_pad == horizontal and vertical subplot padding
    # rect leaves extra space for maintitle
    # auto_spacing_params = dict(pad=.2, w_pad=.3, h_pad=.3,
    #                            rect=(0, 0, 1, .95))
    # fig = Figure(figsize=(figw, figh),
    #              tight_layout=auto_spacing_params)
    #fig = Figure(figsize=(figw, figh))

    model_cyclespec = (cfg.plot.default_model_cycles if model_cycles is None
                       else model_cycles)
    emg_cyclespec = (cfg.plot.default_emg_cycles if emg_cycles is None else
                     emg_cycles)

    axes = dict()
    leg_entries = dict()

    for trial in trials:
        trial_color = next(colors)

        model_cycles = trial.get_cycles(model_cyclespec)
        emg_cycles = trial.get_cycles(emg_cyclespec)
        allcycles = list(set.union(set(model_cycles), set(emg_cycles)))
        if not allcycles:
            raise GaitDataError('Trial %s has no cycles of specified type' %
                                trial.trialname)

        logger.debug('plotting total of %d cycles for %s (%d model, %d EMG)'
                     % (len(allcycles), trial.trialname, len(model_cycles),
                        len(emg_cycles)))

        cycs_unnorm = [cyc.start is None for cyc in allcycles]
        is_unnormalized = any(cycs_unnorm)
        if is_unnormalized and not all(cycs_unnorm):
            raise GaitDataError('Cannot mix normalized and unnormalized data')

        for cyc_ind, cyc in enumerate(allcycles):
            trial.set_norm_cycle(cyc)
            context = cyc.context

            for i, row in enumerate(layout):
                if i not in axes:
                    axes[i] = dict()
                for j, var in enumerate(row):

                    # create axis or get existing axis to use
                    if j not in axes[i]:
                        sharex = axes[0][0] if i > 0 or j > 0 else None
                        ax = fig.add_subplot(gridspec_[i, j], sharex=sharex)
                        axes[i][j] = ax
                    else:
                        ax = axes[i][j]

                    if var is None:
                        ax.axis('off')
                        continue

                    tracegroup = _get_legend_entry(trial, cyc, legend_type)
                    tracename_full = '%s (%s) / %s' % (trial.trialname,
                                                       trial.eclipse_tag,
                                                       cyc.name)

                    mod = models.model_from_var(var)

                    if mod:
                        do_plot = True

                        if cyc not in model_cycles:
                            do_plot = False

                        if var in mod.varnames_noside:
                            # var context was unspecified, so choose it
                            # according to cycle context
                            var = context + var
                        elif var[0] != context:
                            # var context was specified, and has to match cycle
                            do_plot = False

                        if mod.is_kinetic_var(var):
                            # kinetic var cycles are required to have valid
                            # forceplate data
                            if not is_unnormalized and not cyc.on_forceplate:
                                do_plot = False

                        # plot normaldata before other data so that its z order
                        # is lowest (otherwise normaldata will mask other
                        # traces on hover) and it gets the 1st legend entry
                        if (model_normaldata is not None and trial == trials[0]
                            and cyc == allcycles[0] and not is_unnormalized):
                            nvar = var[1:]  # normal vars are without context
                            key = nvar if nvar in model_normaldata else None
                            ndata = (model_normaldata[key] if key in
                                     model_normaldata else None)
                            if ndata is not None:
                                normalx = np.linspace(0, 100, ndata.shape[0])
                                ax.fill_between(normalx, ndata[:, 0],
                                                ndata[:, 1],
                                                color=cfg.plot.
                                                model_normals_color,
                                                alpha=cfg.plot.
                                                model_normals_alpha)
                                model_normaldata_legend = False
                            ax.set_xlim(normalx[0], normalx[-1])

                        if do_plot:
                            t, y = trial.get_model_data(var)

                            if trial_linestyles == 'trial':
                                # trial specific color, left side dashed
                                linecolor = trial_color['color']
                                if context == 'L':
                                    linestyle = '--'
                            elif trial_linestyles == 'same':
                                # identical color for all trials
                                linecolor = cfg.plot.model_tracecolors[context]
                                linestyle = '-'
                            elif trial_linestyles == 'session':
                                # session specific line style
                                linecolor = cfg.plot.model_tracecolors[context]
                                if trial.sessiondir in session_linestyles:
                                    linestyle = session_linestyles[trial.sessiondir]
                                else:
                                    linestyle = next(linestyles)
                                    session_linestyles[trial.sessiondir] = linestyle

                            line_ = ax.plot(t, y, linecolor, linestyle=linestyle,
                                            linewidth=cfg.plot.model_linewidth)[0]
                            leg_entries[tracegroup] = line_                            
                           
                            # add toeoff marker
                            if cyc.toeoffn is not None:
                                toeoff = int(cyc.toeoffn)
                                toeoff_marker = ax.plot(t[toeoff:toeoff+1],
                                                        y[toeoff:toeoff+1],
                                                        'black',
                                                        marker='^')

                            # add supplementary data
                            # if cyc in supplementary_data:
                            #     supdata = supplementary_data[cyc]
                            #     if var in supdata:
                            #         logger.debug('plotting supplementary data '
                            #                      'for var %s' % var)
                            #         t_sup = supdata[var]['t']
                            #         data_sup = supdata[var]['data']
                            #         label_sup = supdata[var]['label']
                            #         strace = go.Scatter(x=t_sup, y=data_sup,
                            #                             name=label_sup,
                            #                             text=label_sup,
                            #                             line=line,
                            #                             legendgroup=tracegroup,
                            #                             hoverinfo='x+y+text',
                            #                             showlegend=False)
                            #         fig.append_trace(strace, i+1, j+1)


                            # axis adjustments
                            if not ax.get_ylabel():
                                yunit = mod.units[var]
                                if yunit == 'deg':
                                    yunit = u'\u00B0'  # degree sign
                                ydesc = [s[:3] for s in mod.ydesc[var]]  # shorten
                                ylabel_ = '%s %s %s' % (ydesc[0], yunit, ydesc[1])
                                ax.set(ylabel=ylabel_)
                                ax.xaxis.label.set_fontsize(cfg.
                                                            plot.label_fontsize)
                                ax.yaxis.label.set_fontsize(cfg.
                                                            plot.label_fontsize)
                                title = _var_title(var)
                                if title:
                                    ax.set_title(title)
                                    ax.title.set_fontsize(cfg.plot.title_fontsize)

                                # FIXME: add n of averages for AvgTrial
                                is_avg_trial = False
                                if is_avg_trial:
                                    subplot_title += (' (avg of %d cycles)' %
                                                    trial.n_ok[var])

                                ax.locator_params(axis='y', nbins=6)  # less tick marks
                                ax.tick_params(axis='both', which='major',
                                               labelsize=cfg.plot.ticks_fontsize)

                                # only set x labels for the bottom row of plot
                                if row == layout[-1]:
                                    xlabel = 'frame' if is_unnormalized else '% of gait cycle'
                                    ax.set(xlabel=xlabel)
                                    ax.xaxis.label.set_fontsize(cfg.plot.label_fontsize)

                    # plot EMG variable
                    elif (trial.emg.is_channel(var) or var in
                          cfg.emg.channel_labels):
                        do_plot = True
                        # plot only if EMG channel context matches cycle ctxt
                        # FIXME: this assumes that EMG names begin with context
                        if (var[0] != context or not trial.emg.status_ok(var)
                            or cyc not in emg_cycles):
                            do_plot = False

                        if do_plot:
                            t_, y = trial.get_emg_data(var)
                            t = (t_ / trial.samplesperframe if is_unnormalized
                                 else t_)
                            line_ = ax.plot(t, y*cfg.plot.emg_multiplier,
                                            linewidth=cfg.plot.emg_linewidth,
                                            **trial_color)[0]
                            leg_entries[tracegroup] = line_

                        # do normal data & plot adjustments for last EMG cycle
                        remaining = allcycles[cyc_ind+1:]
                        last_emg = (trial == trials[-1] and not
                                    any(c in remaining for c in emg_cycles))
                        if last_emg:

                            title = _var_title(var)

                            if not trial.emg.status_ok(var):
                                _remove_ticks_and_labels(ax)
                                _annotate_axis(ax, '%s disconnected' % title)
                            else:
                                if title:
                                    ax.set_title(title)
                                    ax.title.set_fontsize(cfg.plot.title_fontsize)
                                ax.set(ylabel=cfg.plot.emg_ylabel)
                                ax.yaxis.label.set_fontsize(cfg.
                                                            plot.label_fontsize)
                                ax.locator_params(axis='y', nbins=4)
                                # tick font size
                                ax.tick_params(axis='both', which='major',
                                            labelsize=cfg.plot.ticks_fontsize)
                                ax.set_xlim(min(t), max(t))
                                ysc = [-cfg.plot.emg_yscale, cfg.plot.emg_yscale]
                                ax.set_ylim(ysc[0]*cfg.plot.emg_multiplier,
                                            ysc[1]*cfg.plot.emg_multiplier)

                                if not is_unnormalized and var in cfg.emg.channel_normaldata:
                                    emgbar_ind = cfg.emg.channel_normaldata[var]
                                    for inds in emgbar_ind:
                                        ax.axvspan(inds[0], inds[1], alpha=cfg.
                                                plot.emg_normals_alpha,
                                                color=cfg.plot.
                                                emg_normals_color)
                                        emg_normaldata_legend = False  # add to legend only once

                    elif var is None:
                        continue

                    else:
                        raise GaitDataError('Unknown variable %s' % var)
    if maintitle is not None:
        # constrained_layout does not work well with suptitle
        # (https://github.com/matplotlib/matplotlib/issues/13672)
        # add extra \n to create whitespace
        fig.suptitle('%s\n' % maintitle, fontsize=10)
    # put legend into its own axis, since constrained_layout does not handle fig.legend yet
    axleg = fig.add_subplot(gridspec_[i+1, :])
    axleg.axis('off')
    axleg.legend(leg_entries.values(), leg_entries.keys(), fontsize=cfg.plot.legend_fontsize,
                 loc='upper center', bbox_to_anchor=(.5, 1.05), ncol=2)

    return fig


def save_pdf(filename, fig):
    """ Save figure fig into pdf filename """
    try:
        logger.debug('writing %s' % filename)
        with PdfPages(filename) as pdf:
            pdf.savefig(fig)
    except IOError:
        raise IOError('Error writing %s, '
                      'check that file is not already open.' % filename)


def time_dist_barchart(values, stddev=None, thickness=.5,
                       color=None, interactive=True, stddev_bars=True,
                       plotvars=None):
    """ Multi-variable and multi-condition barchart plot.
    values dict is keyed as values[condition][var][context],
    given by e.g. get_c3d_analysis()
    stddev can be None or a dict keyed as stddev[condition][var][context].
    If no stddev for a given condition, set stddev[condition] = None
    plotvars gives variables to plot (if not all) and their order.
    """

    if interactive:
        import matplotlib.pyplot as plt
        fig = plt.figure()
    else:
        fig = Figure()
        canvas = FigureCanvasAgg(fig)

    def _plot_label(ax, rects, texts):
        """Plot a label inside each rect"""
        # FIXME: just a rough heuristic for font size
        fontsize = 6 if len(rects) >= 3 else 8
        for rect, txt in zip(rects, texts):
            ax.text(rect.get_width() * .0, rect.get_y() + rect.get_height()/2.,
                    txt, ha='left', va='center', size=fontsize)

    def _plot_oneside(vars_, context, col):
        """ Do the bar plots for given context and column """
        for ind, var in enumerate(vars_):
            # FIXME: adding subplot here is unnnecessary and triggers mpl
            # depreciation
            ax = fig.add_subplot(gs[ind, col])
            ax.axis('off')
            # may have several bars (conditions) per variable
            vals_this = [values[cond][var][context] for cond in conds]
            if not np.count_nonzero(~np.isnan(vals_this)):
                continue
            stddevs_this = ([stddev[cond][var][context] if stddev[cond]
                             else None for cond in conds])
            units_this = len(conds) * [units[ind]]
            ypos = np.arange(len(vals_this) * thickness, 0, -thickness)
            xerr = stddevs_this if stddev_bars else None
            rects = ax.barh(ypos, vals_this, thickness, align='edge',
                            color=color, xerr=xerr)
            # FIXME: set axis scale according to var normal values
            ax.set_xlim([0, 1.5 * max(vals_this)])
            texts = list()
            for val, std, unit in zip(vals_this, stddevs_this, units_this):
                if val == 0:
                    texts += ['']
                elif std:
                    texts += [u'%.2f ± %.2f %s' % (val, std, unit)]
                else:
                    texts += [u'%.2f %s' % (val, unit)]
            _plot_label(ax, rects, texts)
        # return the last set of rects for legend
        return rects

    if color is None:
        color = ['tab:orange', 'tab:green', 'tab:red', 'tab:brown',
                 'tab:pink', 'tab:gray', 'tab:olive']

    conds = values.keys()
    vals_1 = values[conds[0]]
    varsets = [set(values[cond].keys()) for cond in conds]
    # vars common to all conditions
    vars_common = set.intersection(*varsets)

    if plotvars is not None:
        # pick specified vars that appear in all of the conditions
        plotvars_set = set(plotvars)
        vars_ok = set.intersection(plotvars_set, vars_common)
        if plotvars_set - vars_ok:
            logger.warning('some conditions are missing variables: %s'
                           % (plotvars_set - vars_ok))
        # to preserve original order
        vars_ = [var for var in plotvars if var in vars_ok]
    else:
        vars_ = vars_common

    units = [vals_1[var]['unit'] for var in vars_]

    # 3 columns: bar, labels, bar
    gs = gridspec.GridSpec(len(vars_), 3, width_ratios=[1, 1/3., 1])

    # variable names into the center column
    for ind, (var, unit) in enumerate(zip(vars_, units)):
        textax = fig.add_subplot(gs[ind, 1])
        textax.axis('off')
        label = '%s (%s)' % (var, unit)
        textax.text(0, .5, label, ha='center', va='center')

    rects = _plot_oneside(vars_, 'Left', 0)
    rects = _plot_oneside(vars_, 'Right', 2)

    if len(conds) > 1:
        fig.legend(rects, conds, fontsize=7,
                   bbox_to_anchor=(.5, 0), loc="lower right",
                   bbox_transform=fig.transFigure)

    fig.add_subplot(gs[0, 0]).set_title('Left')
    fig.add_subplot(gs[0, 2]).set_title('Right')

    return fig


class Plotter(object):

    def __init__(self, layout=None, normaldata_files=None, interactive=True):
        """ Plot gait data.

        layout: list of lists
            Variables to be plotted. Each list is a row of variables.
            If None, must be set before plotting (use plotter.layout = layout,
            where plotter is a Plotter instance)
        normaldata_files: list
            Normal data files to read (.xlsx or .gcd). If None, read the files
            specified from config.
        """
        matplotlib.style.use(cfg.plot.mpl_style)

        self.gridspec = None
        if layout:
            self.layout = layout
        else:
            self._layout = None

        self._normaldata_files = dict()
        self._normaldata = dict()
        if normaldata_files is None:
            for fn in cfg.general.normaldata_files:
                self.add_normaldata(fn)

        self.trial = None
        self.fig = None
        self._footer = None
        self.legendnames = list()
        self.modelartists = list()
        self.emgartists = list()
        self.nrows = 0
        self.ncols = 0
        self.interactive = interactive
        self.fig = None

    def add_normaldata(self, filename):
        """ Read the given normal data file if not already read. Take the
        data from the file into use (i.e. it will be used as the default
        normaldata for the plots) """
        if filename in self._normaldata_files:
            ndata = self._normaldata_files[filename]
        else:
            logger.debug('reading new normal data from %s' % filename)
            ndata = normaldata.read_normaldata(filename)
            self._normaldata_files[filename] = ndata
        logger.debug('updating normal data from %s' % filename)
        self._normaldata.update(ndata)

    @property
    def layout(self):
        return self._layout

    @layout.setter
    def layout(self, layout, plotheightratios=None, plotwidthratios=None):
        """ Set plot layout.
        plotheightratios: list
            Height ratios for the plots. Length must equal number of rows in
            the layout. If None, will be automatically computed.
        plotwidthratios: list
            Width ratios for the plots. Length must equal number of columns in
            the layout. If None, will be equal.
        """
        self.nrows, self.ncols = layouts.check_layout(layout)
        self._layout = layout
        self.allvars = [item for row in layout for item in row]
        self.n_proper_vars = len([v for v in self.allvars if v is not None])

        # compute figure width and height - only used for interactive figures
        self.figh = min(self.nrows*cfg.plot.inch_per_row + 1,
                        cfg.plot.maxh)
        self.figw = min(self.ncols*cfg.plot.inch_per_col,
                        cfg.plot.maxw)

        if plotheightratios is None:
            plotheightratios = self._plot_height_ratios()
        elif len(plotheightratios) != len(self.nrows):
            raise ValueError('n of height ratios must match n of rows')

        self.gridspec = gridspec.GridSpec(self.nrows, self.ncols,
                                          height_ratios=plotheightratios,
                                          width_ratios=plotwidthratios)
        # spacing adjustments for the plot, see Figure.tight_layout()
        # pad == plot margins
        # w_pad, h_pad == horizontal and vertical subplot padding
        # rect leaves extra space for maintitle
        auto_spacing_params = dict(pad=.2, w_pad=.3, h_pad=.3,
                                   rect=(0, 0, 1, .95))
        self.fig = Figure(figsize=(self.figw, self.figh),
                          tight_layout=auto_spacing_params)

    def open_nexus_trial(self):
        self.trial = nexus_trial()

    def open_trial(self, source):
        self.trial = Trial(source)

    def _var_type(self, var):
        """ Helper to return variable type """
        # FIXME: better checks for analog vars
        if var is None:
            return None
        elif models.model_from_var(var):
            return 'model'
        elif var in ('model_legend', 'emg_legend'):
            return var
        # check whether it's a configured EMG channel or exists in the data
        # source (both are ok)
        elif (self.trial and self.trial.emg.is_channel(var) or var in
              cfg.emg.channel_labels):
            return 'emg'
        else:
            raise ValueError('Unknown variable %s' % var)

    def _plot_height_ratios(self):
        """ Automatically adjust height ratios, if they are not specified """
        plotheightratios = []
        for row in self._layout:
            # this should take into account any analog variable
            if all([self._var_type(var) == 'emg' for var in row]):
                plotheightratios.append(cfg.plot.analog_plotheight)
            else:
                plotheightratios.append(1)
        return plotheightratios

    def set_footer(self, txt):
        """ Set footer text for figure """
        if self._footer:
            self._footer.remove()
        self._footer = self.fig.text(0, 0, txt, fontsize=8, color='black',
                                     ha='left', va='bottom')

    def do_autospacing(self):
        """Automatically space plot elements (tight_layout)"""
        if self.gridspec is None:
            return
        logger.debug('setting tight layout')
        self.gridspec.tight_layout(self.fig)
        # space for main title
        top = (self.figh - cfg.plot.titlespace) / self.figh
        # decrease vertical spacing
        hspace = .6
        self.gridspec.update(top=top, hspace=hspace)

    def plot_trial(self, trial=None,
                   model_cycles=None,
                   emg_cycles=None,
                   plotheightratios=None,
                   plotwidthratios=None,  # FIXME: not used?
                   model_tracecolor=None,
                   model_linestyle='-',
                   model_alpha=1.0,
                   split_model_vars=True,
                   auto_match_model_cycle=True,
                   model_stddev=None,
                   x_axis_is_time=False,
                   match_pig_kinetics=True,
                   auto_match_emg_cycle=True,
                   linestyles_context=False,
                   toeoff_markers=None,
                   annotate_emg=True,
                   emg_tracecolor=None,
                   emg_alpha=None,
                   plot_model_normaldata=True,
                   plot_emg_normaldata=True,
                   plot_emg_rms=False,
                   sharex=True,
                   superpose=False,
                   maintitle=None,
                   maintitleprefix=None,
                   add_zeroline=False,
                   legend_maxlen=10):

        """ Create plot of variables. Parameters:

            trial : Trial
                Trial to plot. If None, plot self.trial.
        model_cycles : list | dict of int |  dict of list | 'all' | None |
                       'forceplate'
                Gait cycles to plot. See trial.get_cycle() for options.
        emg_cycles : list | dict of int | int | dict of list | 'all' | None
                Same as above, applied to EMG variables.
        plotheightratios : list
                Force height ratios of subplot rows, e.g. [1 2 2 2] would
                make first row half the height of others.
        plotheightratios : list
                Force width ratios of subplot columns.
        model_tracecolor : Matplotlib colorspec
                Line color for model variables. If None, will be
                taken from config.
        model_linestyle : Matplotlib line style
                Line style for model variables. If None, will be
                taken from config.
        model_alpha : float
                Alpha value for model variable traces (0.0 - 1.0)
        split_model_vars: bool
                If model var does not have a leading context 'L' or 'R', a side
                will be prepended according to the gait cycle context.
                E.g. 'HipMoment' -> 'LHipMoment'.
                This allows convenient L/R overlay of e.g. kinematics variables
                by specifying the variable without context.
        auto_match_model_cycle: bool
                If True, the model variable will be plotted only for cycles
                whose context matches the context of the variable. E.g.
                'LHipMomentX' will be plotted only for left side cycles.
                If False, the variable will be plotted for all cycles.
        auto_match_emg_cycle: bool
                If True, the EMG channel will be plotted only for cycles
                whose context matches the context of the channel name. E.g.
                'LRec' will be plotted only for left side cycles.
                If False, the channel will be plotted for all cycles.
        model_stddev : None or dict
                Specifies 'standard deviation' for model variables. Can be
                used to plot e.g. confidence intervals, or stddev if plotting
                averaged data.
        x_axis_is_time: bool
                For unnormalized variables, whether to plot x axis in seconds
                (default) or in frames.
        match_pig_kinetics: bool
                If True, Plug-in Gait kinetics variables will be plotted only
                for cycles that begin with a valid forceplate strike.
        linestyles_context:
                Automatically select line style for model variables according
                to context (defined in config)
        emg_tracecolor : Matplotlib color
                Select line color for EMG variables. If None, will be
                automatically selected (defined in config)
        emg_alpha : float
                Alpha value for EMG traces (0.0 - 1.0)
        plot_model_normaldata : bool
                Whether to plot normal data for model variables.
        plot_emg_normaldata : bool
                Whether to plot normal data. Uses either default normal data
                (in site_defs) or the data given when creating the plotter
                instance.
        plot_emg_rms : bool | string
                Whether to plot EMG RMS superposed on the EMG signal.
                If 'rms_only', plot only RMS.
        maintitle : str
                Main title for the plot.
        maintitleprefix : str
                If maintitle is not set, title will be set to
                maintitleprefix + trial name.
        sharex : bool
                Link the x axes together (will affect zooming)
        superpose : bool
                If superpose=False, create new figure. Otherwise superpose
                on existing figure.
        add_zeroline : bool
                Add line on y=0

        """
        if trial is None and self.trial is None:
            raise ValueError('No trial, specify one or call open_trial()')
        elif trial is None:
            trial = self.trial

        if self._layout is None:
            raise ValueError('Please set layout before plotting')

        # if not superposing data, make sure that the figure is cleared
        if not superpose:
            self.fig.clear()

        # automatically set title if in interactive mode
        if maintitle is None and self.interactive:
            if maintitleprefix is None:
                maintitleprefix = ''
            maintitle = maintitleprefix + trial.trialname

        # auto adjust plot heights
        if plotheightratios is None:
            plotheightratios = self._plot_height_ratios()
        elif len(plotheightratios) != len(self.nrows):
            raise ValueError('n of height ratios must match n of rows')
        plotaxes = []

        def _empty_artist():
            return matplotlib.patches.Rectangle((0, 0), 1, 1, fc="w",
                                                fill=False, edgecolor='none',
                                                linewidth=0)

        def _axis_annotate(ax, text):
            """ Annotate at center of axis """
            ax.annotate(text, xy=(.5, .5), xycoords='axes fraction',
                        ha="center", va="center")

        def _no_ticks_or_labels(ax):
            ax.tick_params(axis='both', which='both', bottom=False,
                           top=False, labelbottom=False, right=False,
                           left=False, labelleft=False)

        def _shorten_name(name, max_len=10):
            """Shorten overlong names for legend etc."""
            return name if len(name) <= max_len else '..'+name[-max_len+2:]

        def _handle_cycle_arg(cycles):
            """Process the cycle argument"""
            if isinstance(cycles, Gaitcycle):
                return [cycles]
            elif cycles is None or cycles == [None]:
                return [None]
            elif (isinstance(cycles, list) and all([isinstance(c, Gaitcycle)
                  for c in cycles])):
                    return cycles
            else:
                return trial.get_cycles(cycles)

        # set default values for vars
        if toeoff_markers is None:
            toeoff_markers = cfg.plot.toeoff_markers

        if emg_tracecolor is None:
            emg_tracecolor = cfg.plot.emg_tracecolor

        if emg_alpha is None:
            emg_alpha = cfg.plot.emg_alpha

        if model_cycles is None:
            model_cycles = cfg.plot.default_model_cycles

        if emg_cycles is None:
            emg_cycles = cfg.plot.default_emg_cycles

        model_cycles = _handle_cycle_arg(model_cycles)
        emg_cycles = _handle_cycle_arg(emg_cycles)

        if not (model_cycles or emg_cycles):
            raise ValueError('No matching gait cycles found in data')

        is_avg_trial = isinstance(trial, AvgTrial)

        for i, var in enumerate(self.allvars):

            if len(self.fig.axes) == len(self.allvars):
                # looks like all axes were created already (superpose)
                ax = self.fig.axes[i]
            else:
                if sharex and len(plotaxes) > 0:
                    ax = self.fig.add_subplot(self.gridspec[i],
                                              sharex=plotaxes[-1])
                else:
                    ax = self.fig.add_subplot(self.gridspec[i])

            var_type = self._var_type(var)
            if var_type is None:
                ax.axis('off')
                continue

            if var_type == 'model':
                model = models.model_from_var(var)
                for cycle in model_cycles:
                    # logger.debug('cycle %d-%d' % (cycle.start, cycle.end))
                    is_unnormalized = cycle.start is None
                    trial.set_norm_cycle(cycle)

                    if (split_model_vars and cycle.context + var
                       in model.varnames):
                        varname = cycle.context + var
                    else:
                        varname = var

                    # check for kinetics variable
                    kin_ok = True
                    if match_pig_kinetics and model.is_kinetic_var(var):
                        kin_ok = cycle.on_forceplate

                    # whether to plot or not
                    x_, data = trial.get_model_data(varname)
                    # FIXME: varname[0] == cycle.context may not apply to
                    # all model vars
                    if (data is not None and kin_ok and (is_unnormalized or
                        varname[0] == cycle.context or not
                         auto_match_model_cycle)):

                        # logger.debug('plotting data for %s' % varname)
                        x = (x_ / trial.framerate if is_unnormalized and
                             x_axis_is_time else x_)
                        # FIXME: cycle may not have context?
                        tcolor = (model_tracecolor if model_tracecolor
                                  else cfg.plot.model_tracecolors
                                  [cycle.context])
                        lstyle = (cfg.plot.model_linestyles
                                  [cycle.context] if linestyles_context else
                                  model_linestyle)
                        lines_ = ax.plot(x, data, tcolor, linestyle=lstyle,
                                         linewidth=cfg.plot.model_linewidth,
                                         alpha=model_alpha)
                        # generate picker events for line artist
                        # FIXME: also for other vars
                        for line_ in lines_:
                            line_.set_picker(1)
                            line_._trialname = trial.trialname
                            line_._cycle = cycle
                        # add toeoff marker for this cycle
                        if (not is_unnormalized and not is_avg_trial and
                           toeoff_markers):
                            toeoff = cycle.toeoffn
                            ax.axvline(toeoff, color=tcolor, linewidth=.5)
                        # tighten x limits
                        ax.set_xlim(x[0], x[-1])
                    else:
                        # logger.debug('not plotting data for %s' % varname)
                        if data is None:
                            logger.debug('(no data)')

                    # each cycle gets its own stddev plot (if data was found)
                    if (model_stddev is not None and not is_unnormalized and
                       data is not None):
                        if varname in model_stddev:
                            sdata = model_stddev[varname]
                            stdx = np.linspace(0, 100, sdata.shape[0])
                            ax.fill_between(stdx, data-sdata,
                                            data+sdata,
                                            color=cfg.plot.
                                            model_stddev_colors[cycle.context],
                                            alpha=cfg.plot.
                                            model_stddev_alpha)
                            # tighten x limits
                            ax.set_xlim(stdx[0], stdx[-1])

                    # set labels, ticks, etc. after plotting last cycle
                    if cycle == model_cycles[-1]:

                        yunit = model.units[varname]
                        if yunit == 'deg':
                            yunit = u'\u00B0'  # degree sign
                        ydesc = [s[:3] for s in model.ydesc[varname]]  # shorten
                        ylabel_ = '%s  %s  %s' % (ydesc[0], yunit, ydesc[1])
                        ax.set(ylabel=ylabel_)
                        ax.xaxis.label.set_fontsize(cfg.
                                                    plot.label_fontsize)
                        ax.yaxis.label.set_fontsize(cfg.
                                                    plot.label_fontsize)
                        subplot_title = model.varlabels[varname]

                        # add n of averages for AvgTrial
                        if is_avg_trial:
                            subplot_title += (' (avg of %d cycles)' %
                                              trial.n_ok[varname])

                        prev_title = ax.get_title()
                        if prev_title and prev_title != subplot_title:
                            subplot_title = prev_title + ' / ' + subplot_title
                        ax.set_title(subplot_title)
                        ax.title.set_fontsize(cfg.plot.title_fontsize)


                        ax.locator_params(axis='y', nbins=6)  # less tick marks
                        ax.tick_params(axis='both', which='major',
                                       labelsize=cfg.plot.ticks_fontsize)

                        if is_unnormalized and var in self.layout[-1]:
                            xlabel = 'Time (s)' if x_axis_is_time else 'Frame'
                            ax.set(xlabel=xlabel)
                            ax.xaxis.label.set_fontsize(cfg.
                                                        plot.label_fontsize)

                        if plot_model_normaldata and not is_unnormalized:
                            # normaldata vars are without preceding side
                            # this is a bit hackish
                            if varname[0].upper() in ['L', 'R']:
                                nvarname = varname[1:]
                            if nvarname in self._normaldata:
                                key = nvarname
                            else:
                                key = None
                            ndata = (self._normaldata[key] if key in
                                     self._normaldata else None)
                            if ndata is not None:
                                logger.debug('plotting model normaldata for %s'
                                             % varname)
                                normalx = np.linspace(0, 100, ndata.shape[0])
                                ax.fill_between(normalx, ndata[:, 0],
                                                ndata[:, 1],
                                                color=cfg.plot.
                                                model_normals_color,
                                                alpha=cfg.plot.
                                                model_normals_alpha)
                                # tighten x limits
                                ax.set_xlim(normalx[0], normalx[-1])

                        if add_zeroline:
                            ax.axhline(0, color='black', linewidth=.5)

            elif var_type == 'emg':
                # set title first, since we may end up not plotting the emg at
                # all (i.e for missing / disconnected channels)
                subplot_title = (cfg.emg.channel_labels[var] if
                                 var in cfg.emg.channel_labels
                                 else var)
                prev_title = ax.get_title()
                if prev_title and prev_title != subplot_title:
                    subplot_title = prev_title + ' / ' + subplot_title
                ax.set_title(subplot_title)
                ax.title.set_fontsize(cfg.plot.title_fontsize)

                for cycle in emg_cycles:
                    trial.set_norm_cycle(cycle)
                    is_unnormalized = cycle.start is None
                    try:
                        x_, data = trial.get_emg_data(var)
                    except KeyError:  # channel not found
                        _no_ticks_or_labels(ax)
                        if annotate_emg:
                            _axis_annotate(ax, 'not found')
                        break  # skip all cycles
                    if not trial.emg.status_ok(var):
                        _no_ticks_or_labels(ax)
                        if annotate_emg:
                            _axis_annotate(ax, 'disconnected')
                        break  # data no good - skip all cycles
                    x = (x_ / trial.analograte if is_unnormalized and
                         x_axis_is_time else x_ / 1.)

                    if is_unnormalized and not x_axis_is_time:
                        # analog -> frames
                        x /= trial.samplesperframe

                    if (is_unnormalized or var[0] == cycle.context or not
                       auto_match_emg_cycle):
                        # plot data and/or rms
                        if plot_emg_rms != 'rms_only':
                            ax.plot(x, data*cfg.plot.emg_multiplier,
                                    emg_tracecolor,
                                    linewidth=cfg.plot.emg_linewidth,
                                    alpha=emg_alpha)

                        if plot_emg_rms:
                            rms = numutils.rms(data, cfg.emg.rms_win)
                            ax.plot(x, rms*cfg.plot.emg_multiplier,
                                    emg_tracecolor,
                                    linewidth=cfg.plot.emg_rms_linewidth,
                                    alpha=emg_alpha)

                    if cycle == emg_cycles[-1]:
                        # last cycle; plot scales, titles etc.
                        ax.set(ylabel=cfg.plot.emg_ylabel)
                        ax.yaxis.label.set_fontsize(cfg.
                                                    plot.label_fontsize)
                        ax.locator_params(axis='y', nbins=4)
                        # tick font size
                        ax.tick_params(axis='both', which='major',
                                       labelsize=cfg.plot.ticks_fontsize)
                        ax.set_xlim(min(x), max(x))
                        ysc = [-cfg.plot.emg_yscale, cfg.plot.emg_yscale]
                        ax.set_ylim(ysc[0]*cfg.plot.emg_multiplier,
                                    ysc[1]*cfg.plot.emg_multiplier)

                        if (plot_emg_normaldata and not is_unnormalized and
                           var in cfg.emg.channel_normaldata):
                            # plot EMG normal bars
                            emgbar_ind = cfg.emg.channel_normaldata[var]
                            for k in range(len(emgbar_ind)):
                                inds = emgbar_ind[k]
                                ax.axvspan(inds[0], inds[1], alpha=cfg.
                                           plot.emg_normals_alpha,
                                           color=cfg.plot.
                                           emg_normals_color)

                        if is_unnormalized and var in self.layout[-1]:
                            xlabel = 'Time (s)' if x_axis_is_time else 'Frame'
                            ax.set(xlabel=xlabel)
                            ax.xaxis.label.set_fontsize(cfg.
                                                        plot.label_fontsize)

            elif var_type in ('model_legend', 'emg_legend'):
                # add current trial name to legend and update legend
                ax.set_axis_off()
                tr_name = _shorten_name(trial.trialname, legend_maxlen)
                leg_entry = (tr_name, trial.eclipse_data['DESCRIPTION'],
                             trial.eclipse_data['NOTES'])
                self.legendnames.append('%s   %s   %s' % leg_entry)

                if var_type == 'model_legend':
                    if linestyles_context:
                        # indicate line styles in legend if they are used
                        leg_ctxt_titles = ['line style for right foot',
                                           'line style for left foot']
                        leg_ctxt_artists = [Line2D((0, 1), (0, 0),
                                                   color='black',
                                                   linewidth=1,
                                                   linestyle=cfg.plot.
                                                   model_linestyles[ctxt])
                                            for ctxt in ['R', 'L']]
                    else:
                        leg_ctxt_titles = []
                        leg_ctxt_artists = []
                    # FIXME: model tracecolor arg is mandatory here
                    self.modelartists.append(Line2D((0, 1), (0, 0),
                                                    color=model_tracecolor,
                                                    linewidth=2))
                    ncol = (1 if len(self.legendnames) + len(leg_ctxt_titles)
                            < 5 else 2)
                    self.fig.legends = []
                    self.fig.legend(self.modelartists + leg_ctxt_artists,
                                    self.legendnames + leg_ctxt_titles,
                                    loc='lower left', ncol=ncol,
                                    prop={'size': cfg.plot.legend_fontsize},
                                    bbox_to_anchor=[.02, .02])

                else:  # emg_legend
                    self.emgartists.append(Line2D((0, 1), (0, 0),
                                           linewidth=2,
                                           color=emg_tracecolor))
                    ncol = 1 if len(self.legendnames) < 5 else 2
                    self.fig.legends = []
                    self.fig.legend(self.emgartists, self.legendnames,
                                    loc='lower left', ncol=ncol,
                                    prop={'size': cfg.plot.legend_fontsize},
                                    bbox_to_anchor=[.02, .02])

            plotaxes.append(ax)

        self.set_title(maintitle)
        return self.fig

    def set_title(self, title):
        """Set plot title and update spacing"""
        self.fig.suptitle(title, fontsize=cfg.plot.maintitle_fontsize,
                          fontweight="bold")

    def title_with_eclipse_info(self, trial=None, prefix=''):
        """ Create title: prefix + trial name + Eclipse description and
        notes """
        if trial is None:
            trial = self.trial
        desc = self.trial.eclipse_data['DESCRIPTION']
        notes = self.trial.eclipse_data['NOTES']
        maintitle = ('%s %s' % (prefix, self.trial.trialname) if prefix else
                     self.trial.trialname)
        maintitle += ' (%s)' % desc if desc else ''
        maintitle += ' (%s)' % notes if notes else ''
        return maintitle

    def create_pdf(self, pdf_name=None, trial=None, pdf_prefix='Nexus_plot',
                   sessionpath=None):
        """ Make a pdf out of the created figure.

        pdf_name: string
            Name of pdf file to create, without path. If not specified, Nexus
            trial name will be used.
        pdf_prefix: string
            Optional prefix for the name
        sessionpath: string
            Where to write the pdf. If not specified, written into the
            session directory of currently loaded trial.
        """
        if trial is None:
            trial = self.trial
        if not self.fig:
            raise ValueError('No figure to save!')
        if sessionpath is None:
            sessionpath = self.trial.sessionpath
        if not sessionpath:
            raise ValueError('Cannot get session path')
        # resize to A4
        # self.fig.set_size_inches([8.27, 11.69])
        if pdf_name:
            pdf_name = op.join(sessionpath, pdf_name)
        else:
            pdf_name = pdf_prefix + self.trial.trialname + '.pdf'
            pdf_name = op.join(sessionpath, pdf_name)
        if op.isfile(pdf_name):
            pass  # can prevent overwriting here
        try:
            logger.debug('writing %s' % pdf_name)
            with PdfPages(pdf_name) as pdf:
                pdf.savefig(self.fig)
        except IOError:
            raise IOError('Error writing %s, '
                          'check that file is not already open.' % pdf_name)
