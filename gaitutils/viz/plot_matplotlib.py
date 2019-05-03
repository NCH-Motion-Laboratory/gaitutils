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
from collections import OrderedDict, defaultdict
import matplotlib
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.lines import Line2D
import matplotlib.gridspec as gridspec
import os.path as op
import numpy as np
import logging

from .plot_common import (_truncate_trialname, _get_cycle_name, _var_title,
                          IteratorMapper)
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
                ha="center", va="center", fontsize=cfg.plot_matplotlib.title_fontsize)


def _remove_ticks_and_labels(ax):
    ax.tick_params(axis='both', which='both', bottom=False,
                   top=False, labelbottom=False, right=False,
                   left=False, labelleft=False)


def plot_trials(trials, layout, model_normaldata=None, model_cycles=None,
                emg_cycles=None, legend_type=None, style_by=None,
                color_by=None, supplementary_data=None, model_stddev=None,
                figtitle=None):
    """plot trials and return Figure instance"""

    if not trials:
        raise GaitDataError('No trials')

    if not isinstance(trials, list):
        trials = [trials]

    style_by_defaults = {'model': 'session'}
    if style_by is None:
        style_by = dict()
    elif isinstance(style_by, basestring):
        style_by = {'model': style_by}
    elif not isinstance(style_by, dict):
        raise ValueError('style_by must be str or dict')
    for k in style_by_defaults.viewkeys() - style_by.viewkeys():
        style_by[k] = style_by_defaults[k]  # update missing values

    color_by_defaults = {'model': 'trial', 'EMG': 'trial'}
    if color_by is None:
        color_by = dict()
    elif isinstance(color_by, basestring):
        color_by = {'model': color_by, 'EMG': color_by}
    elif not isinstance(color_by, dict):
        raise ValueError('color_by must be str or dict')
    for k in color_by_defaults.viewkeys() - color_by.viewkeys():
        color_by[k] = color_by_defaults[k]  # update missing values

    if legend_type is None:
        legend_type = 'short_name_with_cyclename'

    if supplementary_data is None:
        supplementary_data = dict()

    if model_normaldata is None:
        model_normaldata = normaldata.read_all_normaldata()

    nrows, ncols = layouts.check_layout(layout)

    # IteratorMappers generate and keep track of key -> linestyle mappings
    trace_colors = IteratorMapper(cycle(cfg.plot.colors))
    emg_trace_colors = IteratorMapper(cycle(cfg.plot.colors))
    trace_styles = IteratorMapper(cycle(cfg.plot.linestyles))

    # compute figure width and height
    figh = min(nrows*cfg.plot_matplotlib.inch_per_row + 1, cfg.plot_matplotlib.maxh)
    figw = min(ncols*cfg.plot_matplotlib.inch_per_col, cfg.plot_matplotlib.maxw)
    figw, figh = (20, 10)
    fig = Figure(figsize=(figw, figh), constrained_layout=True)

    plotheightratios = _plot_height_ratios(layout)
    plotheightratios.append(.5)  # for legend
    gridspec_ = gridspec.GridSpec(nrows+1, ncols, figure=fig,
                                  height_ratios=plotheightratios,
                                  width_ratios=None)
    # spacing adjustments for the plot, see Figure.tight_layout()
    # pad == plot margins
    # w_pad, h_pad == horizontal and vertical subplot padding
    # rect leaves extra space for figtitle
    # auto_spacing_params = dict(pad=.2, w_pad=.3, h_pad=.3,
    #                            rect=(0, 0, 1, .95))
    # fig = Figure(figsize=(figw, figh),
    #              tight_layout=auto_spacing_params)
    #fig = Figure(figsize=(figw, figh))

    model_cycles = (cfg.plot.default_model_cycles if model_cycles is None
                    else model_cycles)
    emg_cycles = (cfg.plot.default_emg_cycles if emg_cycles is None else
                  emg_cycles)
    if model_cycles == 'unnormalized' or emg_cycles == 'unnormalized':
        normalized = False
        model_cycles = emg_cycles = 'unnormalized'
    else:
        normalized = True

    axes = dict()
    leg_entries = dict()
    mod_normal_lines_ = None
    emg_normal_lines_ = None
    emg_any_ok = defaultdict(lambda: False)

    # plot actual data
    for trial_ind, trial in enumerate(trials):
        # these are the actual Gaitcycle instances
        model_cycles_ = trial.get_cycles(model_cycles)
        emg_cycles_ = trial.get_cycles(emg_cycles)
        allcycles = list(set.union(set(model_cycles_), set(emg_cycles_)))
        if not allcycles:
            logger.debug('trial %s has no cycles of specified type' %
                         trial.trialname)

        logger.debug('plotting total of %d cycles for %s (%d model, %d EMG)'
                     % (len(allcycles), trial.trialname, len(model_cycles),
                        len(emg_cycles)))

        for cyc_ind, cyc in enumerate(allcycles):
            first_cyc = trial_ind == 0 and cyc_ind == 0
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

                    # tracegroup is the legend entry for this cycle
                    # depending on name_type, one tracegroup may end up
                    # holding several cycles, which will be under the same
                    # legend entry.
                    tracegroup = _get_cycle_name(trial, cyc, 
                                                 name_type=legend_type)
                    cyclename_full = _get_cycle_name(trial, cyc,
                                                     name_type='full')

                    mod = models.model_from_var(var)
                    if mod:
                        do_plot = True

                        if cyc not in model_cycles_:
                            do_plot = False

                        if var in mod.varnames_noside:
                            # var context was unspecified, so choose it
                            # according to cycle context
                            var = context + var
                        elif var[0] != context:
                            # var context was specified and does not match cycle
                            do_plot = False

                        if mod.is_kinetic_var(var):
                            # kinetic var cycles are required to have valid
                            # forceplate data
                            if normalized and not cyc.on_forceplate:
                                do_plot = False

                        # plot normal data
                        if (model_normaldata is not None and first_cyc and
                            normalized):
                            nvar = var if var in mod.varlabels_noside else var[1:]
                            key = nvar if nvar in model_normaldata else None
                            ndata = (model_normaldata[key] if key in
                                     model_normaldata else None)
                            if ndata is not None:
                                normalx = np.linspace(0, 100, ndata.shape[0])
                                mod_normal_lines_ = ax.fill_between(normalx, ndata[:, 0],
                                                ndata[:, 1],
                                                color=cfg.plot.
                                                model_normals_color,
                                                alpha=cfg.plot.
                                                model_normals_alpha)
                            ax.set_xlim(normalx[0], normalx[-1])

                        if do_plot:
                            t, y = trial.get_model_data(var)

                            # decide style and color 
                            if style_by['model'] == 'context':
                                sty = cfg.plot.context_styles[context]
                            elif style_by['model'] == 'session':
                                sty = trace_styles.get_prop(trial.sessiondir)
                            elif style_by['model'] == 'trial':
                                sty = trace_styles.get_prop(trial)
                            elif style_by['model'] == 'cycle':
                                sty = trace_styles.get_prop(cyc)

                            if color_by['model'] == 'context':
                                col = cfg.plot.context_colors[context]
                            elif color_by['model'] == 'session':
                                col = trace_colors.get_prop(trial.sessiondir)
                            elif color_by['model'] == 'trial':
                                col = trace_colors.get_prop(trial)
                            elif color_by['model'] == 'cycle':
                                col = trace_colors.get_prop(cyc)

                            line_ = ax.plot(t, y, color=col, linestyle=sty,
                                            linewidth=cfg.plot_matplotlib.model_linewidth,
                                            alpha=cfg.plot.model_alpha)[0]
                            leg_entries[tracegroup] = line_

                            # add toeoff marker
                            if cyc.toeoffn is not None:
                                toeoff = int(cyc.toeoffn)
                                toeoff_marker = ax.plot(t[toeoff:toeoff+1],
                                                        y[toeoff:toeoff+1],
                                                        'black',
                                                        marker='^')

                            # each cycle gets its own stddev plot
                            if (model_stddev is not None and normalized and
                               y is not None and var in model_stddev):
                                sdata = model_stddev[var]
                                stdx = np.linspace(0, 100, sdata.shape[0])
                                stddev_ = ax.fill_between(stdx, y-sdata,
                                                y+sdata,
                                                color=cfg.plot.
                                                model_stddev_colors[cyc.context],
                                                alpha=cfg.plot.
                                                model_stddev_alpha)
                                # tighten x limits
                                ax.set_xlim(stdx[0], stdx[-1])
                                leg_entries['Stddev for %s' % tracegroup] = stddev_

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


                            # axis adjustments for model variable
                            if not ax.get_ylabel():
                                yunit = mod.units[var]
                                if yunit == 'deg':
                                    yunit = u'\u00B0'  # degree sign
                                ydesc = [s[:3] for s in mod.ydesc[var]]  # shorten
                                ylabel_ = '%s %s %s' % (ydesc[0], yunit, ydesc[1])
                                ax.set(ylabel=ylabel_)

                                ax.xaxis.label.set_fontsize(cfg.plot_matplotlib.label_fontsize)
                                ax.yaxis.label.set_fontsize(cfg.plot_matplotlib.label_fontsize)
                                title = _var_title(var)
                                if title:
                                    ax.set_title(title)
                                    ax.title.set_fontsize(cfg.plot_matplotlib.title_fontsize)
                                ax.tick_params(axis='both', which='major',
                                            labelsize=cfg.plot_matplotlib.ticks_fontsize)
                                ax.locator_params(axis='y', nbins=6)  # less tick marks

                                # FIXME: add n of averages for AvgTrial
                                is_avg_trial = False
                                if is_avg_trial:
                                    subplot_title += (' (avg of %d cycles)' %
                                                      trial.n_ok[var])

                    # plot EMG variable
                    elif (trial.emg is not None and trial.emg.is_channel(var) or var in
                          cfg.emg.channel_labels):
                        do_plot = True
                        # plot only if EMG channel context matches cycle ctxt
                        # FIXME: this assumes that EMG names begin with context
                        if (var[0] != context or not trial.emg.status_ok(var)
                           or cyc not in emg_cycles_):
                            do_plot = False

                        if do_plot:
                            t_, y = trial.get_emg_data(var)
                            t = t_ if normalized else t_ / trial.samplesperframe

                            if color_by['EMG'] == 'session':
                                col = emg_trace_colors.get_prop(trial.sessiondir)
                            elif color_by['EMG'] == 'trial':
                                col = emg_trace_colors.get_prop(trial)
                            elif color_by['EMG'] == 'cycle':
                                col = emg_trace_colors.get_prop(cyc)

                            line_ = ax.plot(t, y*cfg.plot.emg_multiplier, color=col,
                                            linewidth=cfg.plot_matplotlib.
                                            emg_linewidth)[0]
                            leg_entries['EMG: '+tracegroup] = line_

                        # do normal data & plot adjustments for last EMG cycle
                        # keeps track of whether any trials have valid EMG data for this
                        # variable; otherwise, we annotatate channel as disconnected
                        emg_any_ok[var] |= trial.emg.status_ok(var)
                        remaining = allcycles[cyc_ind+1:]
                        last_emg = (trial == trials[-1] and not
                                    any(c in remaining for c in emg_cycles_))
                        if last_emg:
                            title = _var_title(var)
                            if not emg_any_ok[var]:
                                _remove_ticks_and_labels(ax)
                                _annotate_axis(ax, '%s disconnected' % title)
                            else:
                                if title:
                                    ax.set_title(title)
                                    ax.title.set_fontsize(cfg.plot_matplotlib.title_fontsize)
                                ax.set(ylabel=cfg.plot.emg_ylabel)
                                ax.yaxis.label.set_fontsize(cfg.plot_matplotlib.label_fontsize)
                                ax.locator_params(axis='y', nbins=4)
                                # tick font size
                                ax.tick_params(axis='both', which='major',
                                            labelsize=cfg.plot_matplotlib.ticks_fontsize)
                                ax.set_xlim(min(t), max(t))
                                ysc = [-cfg.plot.emg_yscale, cfg.plot.emg_yscale]
                                ax.set_ylim(ysc[0]*cfg.plot.emg_multiplier,
                                            ysc[1]*cfg.plot.emg_multiplier)

                                if normalized and var in cfg.emg.channel_normaldata:
                                    emgbar_ind = cfg.emg.channel_normaldata[var]
                                    for inds in emgbar_ind:
                                        emg_normal_lines_=ax.axvspan(inds[0], inds[1], alpha=cfg.
                                                plot.emg_normals_alpha,
                                                color=cfg.plot.
                                                emg_normals_color)

                    elif var is None:
                        continue

                    else:
                        raise GaitDataError('Unknown variable %s' % var)

                    # adjustments common to all plots
                    # set x labels on bottom row of plot
                    if row == layout[-1]:
                        xlabel = '% of gait cycle' if normalized else 'frame'
                        ax.set(xlabel=xlabel)
                        ax.xaxis.label.set_fontsize(cfg.plot_matplotlib.label_fontsize)

    if figtitle is not None:
        # constrained_layout does not work well with suptitle
        # (https://github.com/matplotlib/matplotlib/issues/13672)
        # add extra \n to create whitespace
        fig.suptitle('%s\n' % figtitle, fontsize=10)
    # put legend into its own axis, since constrained_layout does not handle fig.legend yet
    axleg = fig.add_subplot(gridspec_[i+1, :])
    axleg.axis('off')
    leg_entries_ = OrderedDict()
    if mod_normal_lines_:
        leg_entries_['Norm.'] = mod_normal_lines_
    if emg_normal_lines_:
        leg_entries_['EMG norm.'] = emg_normal_lines_
    leg_entries_.update(leg_entries)
    leg_ncols = ncols
    leg = axleg.legend(leg_entries_.values(), leg_entries_.keys(),
                 fontsize=cfg.plot_matplotlib.legend_fontsize,
                 loc='upper center', bbox_to_anchor=(.5, 1.05), ncol=leg_ncols)
    # legend lines may be too thin to see
    for li in leg.get_lines():
        li.set_linewidth(2.0)
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


