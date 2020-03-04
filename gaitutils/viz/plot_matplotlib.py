# -*- coding: utf-8 -*-
"""
matplotlib based plotting functions

@author: Jussi (jnu@iki.fi)
"""

from __future__ import division

from builtins import zip
from builtins import range
from itertools import cycle
from collections import OrderedDict, defaultdict
from matplotlib.figure import Figure
from matplotlib.backends.backend_pdf import PdfPages
import matplotlib.gridspec as gridspec
import numpy as np
import logging

from .plot_common import (
    _get_cycle_name,
    _var_title,
    _handle_cyclespec,
    _cyclical_mapper,
    _handle_style_and_color_args,
    _color_by_params,
    _style_by_params,
    _emg_yscale,
)
from .. import models, normaldata, cfg, GaitDataError, numutils
from ..stats import AvgTrial
from ..timedist import _pick_common_vars
from . import layouts

logger = logging.getLogger(__name__)


def _plot_vels(vels, labels):
    """Stem plot of trial velocities"""
    fig = Figure()
    ax = fig.add_subplot(111)
    ax.stem(vels)
    ax.set_xticks(range(len(vels)))
    ax.set_xticklabels(labels, rotation='vertical')
    ax.set_ylabel('Speed (m/s)')
    ax.tick_params(axis='both', which='major', labelsize=8)
    vavg = np.nanmean(vels)
    ax.set_title('Walking speed for dynamic trials (average %.2f m/s)' % vavg)
    fig.set_tight_layout(True)
    return fig


def _plot_timedep_vels(vels, labels):
    """Time-dependent velocity curves"""
    fig = Figure()
    ax = fig.add_subplot(111)
    ax.set_ylabel('Speed (m/s)')
    ax.set_xlabel('% of trial')
    for vel in vels:
        ax.plot(vel)
    fig.set_tight_layout(True)
    return fig


def _plot_height_ratios(layout):
    """Calculate height ratios for mpl plot"""
    plotheightratios = []
    for row in layout:
        if all([models.model_from_var(var) for var in row]):
            plotheightratios.append(1)
        else:
            plotheightratios.append(cfg.plot_matplotlib.analog_plotheight)
    return plotheightratios


def time_dist_barchart(
    values,
    stddev=None,
    thickness=0.5,
    color=None,
    stddev_bars=True,
    plotvars=None,
    title=None,
    big_fonts=None,
):
    """ Multi-variable and multi-condition barchart plot.
    values dict is keyed as values[condition][var][context],
    given by e.g. get_c3d_analysis()
    stddev can be None or a dict keyed as stddev[condition][var][context].
    plotvars gives variables to plot (if not all) and their order.
    """
    fig = Figure()

    def _plot_label(ax, rects, texts):
        """Plot a label inside each rect"""
        # FIXME: just a rough heuristic for font size
        fontsize = 6 if len(rects) >= 3 else 8
        for rect, txt in zip(rects, texts):
            ax.text(
                rect.get_width() * 0.0,
                rect.get_y() + rect.get_height() / 2.0,
                txt,
                ha='left',
                va='center',
                size=fontsize,
            )

    def _plot_oneside(vars, context, col):
        """Do the bar plots for given context and column"""
        for ind, var in enumerate(vars):
            ax = fig.add_subplot(gs[ind, col])
            if ind == 0:
                if col == 0:
                    ax.set_title('Left')
                elif col == 2:
                    ax.set_title('Right')

            ax.axis('off')
            # may have several bars (conditions) per variable
            vals_this = [values[cond][var][context] for cond in conds]
            if not np.count_nonzero(~np.isnan(vals_this)):
                continue
            if stddev is None:
                stddevs_this = [None for cond in conds]
            else:
                stddevs_this = [stddev[cond][var][context] for cond in conds]
            units_this = len(conds) * [units[ind]]
            ypos = np.arange(len(vals_this) * thickness, 0, -thickness)
            xerr = stddevs_this if stddev_bars else None
            rects = ax.barh(
                ypos, vals_this, thickness, align='edge', color=color, xerr=xerr
            )
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
        color = [
            'tab:green',
            'tab:orange',
            'tab:red',
            'tab:brown',
            'tab:pink',
            'tab:gray',
            'tab:olive',
        ]

    conds, vars, units = _pick_common_vars(values, plotvars)

    # 3 columns: bars, labels, bars
    gs = gridspec.GridSpec(len(vars), 3, width_ratios=[1, 1 / 3.0, 1])

    # variable names into the center column
    for ind, (var, unit) in enumerate(zip(vars, units)):
        textax = fig.add_subplot(gs[ind, 1])
        textax.axis('off')
        label = '%s (%s)' % (var, unit) if unit else var
        textax.text(0, 0.5, label, ha='center', va='center')

    rects = _plot_oneside(vars, 'Left', 0)
    rects = _plot_oneside(vars, 'Right', 2)

    if len(conds) > 1:
        fig.legend(
            rects,
            conds,
            fontsize=7,
            bbox_to_anchor=(0.5, 0),
            loc="lower right",
            bbox_transform=fig.transFigure,
        )

    if title is not None:
        fig.suptitle(title)
    return fig


def _annotate_axis(ax, text):
    """Annotate at center of mpl axis"""
    ax.annotate(
        text,
        xy=(0.5, 0.5),
        xycoords='axes fraction',
        ha="center",
        va="center",
        fontsize=cfg.plot_matplotlib.subtitle_fontsize,
    )


def _remove_ticks_and_labels(ax):
    ax.tick_params(
        axis='both',
        which='both',
        bottom=False,
        top=False,
        labelbottom=False,
        right=False,
        left=False,
        labelleft=False,
    )


def plot_trials(
    trials,
    layout,
    model_normaldata=None,
    cycles=None,
    max_cycles=None,
    emg_mode=None,
    legend_type=None,
    style_by=None,
    color_by=None,
    supplementary_data=None,
    legend=True,
    figtitle=None,
):
    """plot trials and return Figure instance"""

    if not trials:
        raise GaitDataError('No trials')

    if not isinstance(trials, list):
        trials = [trials]

    style_by, color_by = _handle_style_and_color_args(style_by, color_by)

    if legend_type is None:
        legend_type = 'short_name_with_cyclename'

    if supplementary_data is None:
        supplementary_data = dict()

    if model_normaldata is None:
        model_normaldata = normaldata.read_default_normaldata()

    emg_normaldata = normaldata.read_emg_normaldata()

    use_rms = emg_mode == 'rms'

    nrows, ncols = layouts.check_layout(layout)

    # these generate and keep track of key -> linestyle (or color) mappings
    trace_colors = _cyclical_mapper(cfg.plot.colors)
    emg_trace_colors = _cyclical_mapper(cfg.plot.colors)
    trace_styles = _cyclical_mapper(cfg.plot.linestyles)

    # compute figure width and height
    figh = min(nrows * cfg.plot_matplotlib.inch_per_row + 1, cfg.plot_matplotlib.maxh)
    figw = min(ncols * cfg.plot_matplotlib.inch_per_col, cfg.plot_matplotlib.maxw)
    figw, figh = (20, 10)
    fig = Figure(figsize=(figw, figh), constrained_layout=True)

    plotheightratios = _plot_height_ratios(layout)
    plotheightratios.append(0.5)  # for legend
    gridspec_ = gridspec.GridSpec(
        nrows + 1, ncols, figure=fig, height_ratios=plotheightratios, width_ratios=None
    )
    # spacing adjustments for the plot, see Figure.tight_layout()
    # pad == plot margins
    # w_pad, h_pad == horizontal and vertical subplot padding
    # rect leaves extra space for figtitle
    # auto_spacing_params = dict(pad=.2, w_pad=.3, h_pad=.3,
    #                            rect=(0, 0, 1, .95))
    # fig = Figure(figsize=(figw, figh),
    #              tight_layout=auto_spacing_params)
    # fig = Figure(figsize=(figw, figh))

    normalized = cycles != 'unnormalized'
    cycles = _handle_cyclespec(cycles)
    if max_cycles is None:
        max_cycles = cfg.plot.max_cycles

    axes = dict()
    leg_entries = dict()
    mod_normal_lines_ = None
    emg_normal_lines_ = None
    emg_any_ok = defaultdict(lambda: False)

    # plot actual data
    for trial_ind, trial in enumerate(trials):
        # get Gaitcycle instances from trial according to cycle specs
        model_cycles_ = trial.get_cycles(
            cycles['model'], max_cycles_per_context=max_cycles['model']
        )
        emg_cycles_ = trial.get_cycles(
            cycles['emg'], max_cycles_per_context=max_cycles['emg']
        )
        allcycles = list(set.union(set(model_cycles_), set(emg_cycles_)))
        if not allcycles:
            logger.debug('trial %s has no cycles of specified type' % trial.trialname)

        logger.debug(
            'plotting total of %d cycles for %s (%d model, %d EMG)'
            % (len(allcycles), trial.trialname, len(model_cycles_), len(emg_cycles_))
        )

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
                        # set x axis to tightly match data boundaries
                        ax.autoscale(enable=True, axis='x', tight=True)
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
                    tracegroup = _get_cycle_name(trial, cyc, name_type=legend_type)
                    cyclename_full = _get_cycle_name(trial, cyc, name_type='full')

                    mod = models.model_from_var(var)
                    if mod:
                        do_plot = cyc in model_cycles_

                        if var in mod.varnames_noside:
                            # var context was unspecified, so choose it
                            # according to cycle context
                            var = context + var
                        elif var[0] != context:
                            # specified var context does not match cycle
                            do_plot = False

                        # kinetic var cycles are required to have valid
                        # forceplate data
                        if (
                            normalized
                            and mod.is_kinetic_var(var)
                            and not cyc.on_forceplate
                        ):
                            do_plot = False

                        # plot normal data before first cycle
                        if model_normaldata is not None and first_cyc and normalized:
                            nvar = var if var in mod.varlabels_noside else var[1:]
                            key = nvar if nvar in model_normaldata else None
                            ndata = (
                                model_normaldata[key]
                                if key in model_normaldata
                                else None
                            )
                            if ndata is not None:
                                normalx = np.linspace(0, 100, ndata.shape[0])
                                mod_normal_lines_ = ax.fill_between(
                                    normalx,
                                    ndata[:, 0],
                                    ndata[:, 1],
                                    color=cfg.plot.model_normals_color,
                                    alpha=cfg.plot.model_normals_alpha,
                                )

                        t, y = trial.get_model_data(var)
                        if y is None:
                            do_plot = False

                        if do_plot:
                            # decide style and color
                            sty = _style_by_params(
                                style_by['model'], trace_styles, trial, cyc, context
                            )
                            col = _color_by_params(
                                color_by['model'], trace_colors, trial, cyc, context
                            )

                            line_ = ax.plot(
                                t,
                                y,
                                color=col,
                                linestyle=sty,
                                linewidth=cfg.plot.model_linewidth,
                                alpha=cfg.plot.model_alpha,
                            )[0]
                            leg_entries[tracegroup] = line_

                            # add toeoff marker
                            if cyc.toeoffn is not None:
                                toeoff = int(cyc.toeoffn)
                                toeoff_marker = ax.plot(
                                    t[toeoff : toeoff + 1],
                                    y[toeoff : toeoff + 1],
                                    col,
                                    marker='^',
                                )

                            # each cycle gets its own stddev plot
                            if isinstance(trial, AvgTrial):
                                model_stddev = trial.stddev_data
                                if (
                                    model_stddev is not None
                                    and normalized
                                    and y is not None
                                    and var in model_stddev
                                ):
                                    sdata = model_stddev[var]
                                    stdx = np.linspace(0, 100, sdata.shape[0])
                                    stddev_ = ax.fill_between(
                                        stdx,
                                        y - sdata,
                                        y + sdata,
                                        color=col,
                                        alpha=cfg.plot.model_stddev_alpha,
                                    )
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

                                ax.xaxis.label.set_fontsize(
                                    cfg.plot_matplotlib.label_fontsize
                                )
                                ax.yaxis.label.set_fontsize(
                                    cfg.plot_matplotlib.label_fontsize
                                )
                                title = _var_title(var)
                                if title:
                                    ax.set_title(title)
                                    ax.title.set_fontsize(
                                        cfg.plot_matplotlib.subtitle_fontsize
                                    )
                                ax.tick_params(
                                    axis='both',
                                    which='major',
                                    labelsize=cfg.plot_matplotlib.ticks_fontsize,
                                )
                                ax.locator_params(axis='y', nbins=6)  # less tick marks

                                # FIXME: add n of averages for AvgTrial
                                is_avg_trial = False
                                if is_avg_trial:
                                    subplot_title += (
                                        ' (avg of %d cycles)' % trial.n_ok[var]
                                    )

                    # plot EMG variable
                    elif (
                        trial.emg is not None
                        and trial.emg.has_channel(var)
                        or var in cfg.emg.channel_labels
                    ):
                        do_plot = (
                            trial.emg.context_ok(var, context)
                            and trial.emg.status_ok(var)
                            and cyc in emg_cycles_
                        )
                        # FIXME: maybe annotate disconnected chans
                        # _no_ticks_or_labels(ax)
                        # _axis_annotate(ax, 'disconnected')
                        if do_plot:

                            t_, y = trial.get_emg_data(var, rms=use_rms)
                            t = t_ if normalized else t_ / trial.samplesperframe

                            col = _color_by_params(
                                color_by['emg'], emg_trace_colors, trial, cyc, context
                            )
                            lw = (
                                cfg.plot.emg_rms_linewidth
                                if use_rms
                                else cfg.plot.emg_linewidth
                            )
                            line_ = ax.plot(
                                t, y * cfg.plot.emg_multiplier, color=col, linewidth=lw
                            )[0]
                            leg_entries['EMG: ' + tracegroup] = line_

                        # do normal data & plot adjustments for last EMG cycle
                        # keeps track of whether any trials have valid EMG data for this
                        # variable; otherwise, we annotatate channel as disconnected
                        emg_any_ok[var] |= trial.emg.status_ok(var)
                        remaining = allcycles[cyc_ind + 1 :]
                        last_emg = trial == trials[-1] and not any(
                            c in remaining for c in emg_cycles_
                        )
                        if last_emg:
                            title = _var_title(var)
                            if not emg_any_ok[var]:
                                _remove_ticks_and_labels(ax)
                                _annotate_axis(ax, '%s disconnected' % title)
                            else:
                                if title:
                                    ax.set_title(title)
                                    ax.title.set_fontsize(
                                        cfg.plot_matplotlib.subtitle_fontsize
                                    )
                                ax.set(ylabel=cfg.plot.emg_ylabel)
                                ax.yaxis.label.set_fontsize(
                                    cfg.plot_matplotlib.label_fontsize
                                )
                                ax.locator_params(axis='y', nbins=4)
                                # tick font size
                                ax.tick_params(
                                    axis='both',
                                    which='major',
                                    labelsize=cfg.plot_matplotlib.ticks_fontsize,
                                )

                                _emg_y_extent = _emg_yscale(emg_mode)
                                ax.set_ylim(_emg_y_extent)

                                if normalized and var in emg_normaldata:
                                    ndata = emg_normaldata[var][None, :]
                                    # create a color strip below the EMG trace, according to normal data
                                    logger.debug(_emg_y_extent)
                                    extent_y0 = _emg_y_extent[0]
                                    # strip width is total y scale / 10
                                    extent_y1 = (
                                        extent_y0
                                        + (_emg_y_extent[1] - _emg_y_extent[0]) / 10.0
                                    )
                                    emg_normal_lines_ = ax.imshow(
                                        ndata,
                                        extent=[0, 100, extent_y0, extent_y1],
                                        aspect='auto',
                                        cmap='Reds',
                                        vmin=0,
                                        vmax=1,
                                    )

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
        # hack: add extra \n to create whitespace
        # XXX Py3: this hack is no longer necessary in matplotlib 3.x or newer
        if figtitle and figtitle[-1] != '\n':
            figtitle = figtitle + '\n'
        fig.suptitle(figtitle, fontsize=10)

    if legend:
        # put legend into its own axis, since constrained_layout does not handle fig.legend yet
        # see https://github.com/matplotlib/matplotlib/issues/13023
        axleg = fig.add_subplot(gridspec_[i + 1, :])
        axleg.axis('off')
        leg_entries_ = OrderedDict()
        if mod_normal_lines_:
            leg_entries_['Norm.'] = mod_normal_lines_
        if emg_normal_lines_:
            leg_entries_['EMG norm.'] = emg_normal_lines_
        leg_entries_.update(leg_entries)
        leg_ncols = ncols
        leg = axleg.legend(
            leg_entries_.values(),
            leg_entries_.keys(),
            fontsize=cfg.plot_matplotlib.legend_fontsize,
            loc='upper center',
            bbox_to_anchor=(0.5, 1.05),
            ncol=leg_ncols,
        )
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
        raise IOError(
            'Error writing %s, check that file is not already open.' % filename
        )
