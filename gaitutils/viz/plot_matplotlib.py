# -*- coding: utf-8 -*-
"""
matplotlib based plotting functions

@author: Jussi (jnu@iki.fi)
"""


from functools import partial
from collections import defaultdict
import itertools
import matplotlib
from matplotlib.figure import Figure
import matplotlib.gridspec as gridspec
import plotly.graph_objs as go
import plotly.io as pio
import numpy as np
import logging
import io

from .plot_common import (
    _get_cycle_name,
    _var_title,
    _handle_cyclespec,
    _cyclical_mapper,
    _handle_style_and_color_args,
    _color_by_params,
    _style_by_params,
    _emg_yscale,
    _get_trial_cycles,
    _triage_var,
    _compose_varname,
    _nested_get,
    _var_unit,
)
from .. import models, normaldata, utils
from ..config import cfg
from ..envutils import GaitDataError
from ..stats import AvgTrial
from ..timedist import _pick_common_vars
from . import layouts

logger = logging.getLogger(__name__)


def _plot_extracted_table(curve_vals, vardefs):
    """Plot comparison of extracted gait curve values as a table."""
    contexts = utils.get_contexts()
    col_labels = list(curve_vals.keys())
    row_labels = [_compose_varname(vardef) for vardef in vardefs]
    table = list()
    for vardef in vardefs:
        row = list()
        for session_vals in curve_vals.values():
            element = ''
            for ctxt, _ in contexts:
                vardef_ctxt = [ctxt + vardef[0]] + vardef[1:]
                if vardef_ctxt[0] not in session_vals:
                    logger.debug(
                        '%s was not collected for this session' % vardef_ctxt[0]
                    )
                    continue
                this_vals = _nested_get(
                    session_vals, vardef_ctxt
                )  # returns list of values for given session and context = column
                mean, std = np.mean(this_vals), np.std(this_vals)
                unit = _var_unit(vardef_ctxt)
                if unit == 'deg':
                    unit = '\u00B0'  # Unicode degree sign
                else:
                    unit = ' ' + unit
                element += '%s: %.2f±%.2f%s' % (ctxt, mean, std, unit)
            row.append(element)
        table.append(row)
    return _plot_tabular_data(table, row_labels, col_labels)


def _plot_extracted_table_plotly(curve_vals, vardefs):
    """Plot comparison of extracted gait curve values as a table, using Plotly as backend."""
    contexts = utils.get_contexts()
    # make a nested list of column headers; first row is session, second row is context
    session_labels = list(curve_vals.keys())
    col_labels_1 = list(
        itertools.chain.from_iterable(zip(session_labels, itertools.repeat('')))
    )
    context_cycle = itertools.cycle(c[0] for c in contexts)
    col_labels_2 = [next(context_cycle) for k in col_labels_1]
    # transpose
    col_labels = list(zip(col_labels_1, col_labels_2))
    row_labels = [_compose_varname(vardef) for vardef in vardefs]
    table = list()
    for vardef in vardefs:
        row = list()
        for session_vals in curve_vals.values():
            for ctxt, _ in contexts:
                vardef_ctxt = [ctxt + vardef[0]] + vardef[1:]
                if vardef_ctxt[0] not in session_vals:
                    logger.debug(
                        '%s was not collected for this session' % vardef_ctxt[0]
                    )
                    continue
                this_vals = _nested_get(
                    session_vals, vardef_ctxt
                )  # returns list of values for given session and context = column
                mean, std = np.mean(this_vals), np.std(this_vals)
                unit = _var_unit(vardef_ctxt)
                if unit == 'deg':
                    unit = '\u00B0'  # Unicode degree sign
                else:
                    unit = ' ' + unit
                row.append('%.2f±%.2f%s' % (mean, std, unit))
        table.append(row)
    return _plot_tabular_data_via_plotly(table, row_labels, col_labels)


def _plot_tabular_data(data, row_labels=None, col_labels=None):
    """Plot tabular data via matplotlib table()"""
    fig = Figure()
    ax = fig.add_subplot(111)
    the_table = ax.table(
        cellText=data,
        rowLabels=row_labels,
        rowLoc='left',
        colLabels=col_labels,
        loc='center',
        bbox=[0.2, 0.0, 0.9, 0.8],
    )
    # the_table.auto_set_font_size(False)
    # the_table.set_fontsize(7)
    # the_table.scale(1, 1.5)
    ax.get_xaxis().set_visible(False)
    ax.get_yaxis().set_visible(False)
    ax.set_frame_on(False)
    the_table.auto_set_font_size(False)
    the_table.set_fontsize(6)
    return fig


def _plot_tabular_data_via_plotly(data, row_labels=None, col_labels=None):
    """Plot tabular data via plotly and convert to matplotlib"""
    # disable MathJax since it causes slowdowns
    # see https://github.com/plotly/Kaleido/issues/36
    pio.kaleido.scope.mathjax = None
    # transpose into list of columns for go.Table
    data = list(zip(*data))
    data = [row_labels] + data
    col_labels = [''] + col_labels
    thetable = go.Table(cells={'values': data}, header={'values': col_labels})
    pfig = go.Figure(data=[thetable])
    bytes = pfig.to_image(format='png', engine='kaleido', width=1600, height=1200)
    bio = io.BytesIO(bytes)
    # 2: read into matplotlib
    im = matplotlib.image.imread(bio, format='png')
    fig = Figure()
    ax = fig.add_subplot(111)
    ax.imshow(im)
    ax.get_xaxis().set_visible(False)
    ax.get_yaxis().set_visible(False)
    ax.set_frame_on(False)
    return fig


def _plot_vels(vels, labels, title=None):
    """Stem plot of trial velocities"""
    fig = Figure()
    ax = fig.add_subplot(111)
    ax.stem(vels)
    ax.set_xticks(range(len(vels)))
    ax.set_xticklabels(labels, rotation='vertical')
    ax.set_ylabel('Speed (m/s)')
    ax.tick_params(axis='both', which='major', labelsize=8)
    fig.set_tight_layout(True)
    if title:
        fig.suptitle(title)
    return fig


def _plot_timedep_vels(vels, labels, title=None):
    """Time-dependent velocity curves"""
    fig = Figure()
    ax = fig.add_subplot(111)
    ax.set_ylabel('Speed (m/s)')
    ax.set_xlabel('% of trial')
    for vel, label in zip(vels, labels):
        ax.plot(vel, label=label)
    fig.set_tight_layout(True)
    if title:
        fig.suptitle(title)
    # for legend, maybe wait for matplotlib 3
    # ax.legend()
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
    figtitle=None,
    timedist_normaldata=None,
    big_fonts=None,
):
    """Multi-variable and multi-condition barchart plot.

    Used mostly for plotting time-distance variables.

    Parameters
    ----------
    values : dict
        Nested dict of values to plot. Keys are values[condition][var][context].
        Matches the output of group_analysis_trials().
    stddev : dict | None
        Similar to values, but provides standard deviation for each variable. If None,
        do not plot the deviations.
    thickness : float, optional
        Y direction thickness of the bars, by default 0.5.
    color : list, optional
        List of colors for the different conditions. If None, use default values.
    stddev_bars : bool, optional
        Whether to plot standard deviation also as bars.
    plotvars : list, optional
        The variables to plot and their order. If None, plot all variables.
    figtitle : str, optional
        Title of the plot.
    timedist_normaldata : dict | None
        Time-distance normal data. Determines scaling of the bars. Should be a
        dict with varnames as keys and the x scales as values. If None, will be
        read from cfg.
    big_fonts : bool, optional
        If True, increase font sizes somewhat.

    Returns
    -------
    Figure
        The chart.
    """

    XTICK_SPACING = 20  # spacing in %

    fig = Figure()

    if timedist_normaldata is None:
        timedist_normaldata = normaldata._read_timedist_normaldata_file(cfg.general.timedist_normaldata)

    def _plot_label(ax, rects, texts):
        """Plot a label inside each rect"""
        # XXX: just a rough heuristic for font size
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

    def _plot_oneside(vars, context, col, conds):
        """Do the bar plots for given context and column"""
        largest_x = 0
        var_axes = list()
        for ind, var in enumerate(vars):
            ax = fig.add_subplot(gs[ind, col])
            var_axes.append(ax)
            if ind == 0:
                ax.set_title(context)
            if var != vars[-1]:
                ax.axis('off')
            else:  # the last plot
                # we want x axis ticks and label
                ax.set_xlabel('% of reference')
                ax.set_frame_on(False)
                ax.grid(False)
                ax.axes.get_yaxis().set_visible(False)                
            # scale var values to % of reference; if reference is not given, use
            # maximum for the variable over all conditions
            if var in timedist_normaldata and timedist_normaldata[var] is not None:
                scaler = timedist_normaldata[var]
            else:
                scaler = max([values[cond][var][context] for cond in conds])
            # we may have several bars (conditions) per variable
            vals_this = np.array([values[cond][var][context] for cond in conds]) 
            scaled_vals_this = vals_this / scaler * 100
            # use uniform x scaling according to largest relative value
            if vals_this > largest_x:
                largest_x = vals_this
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
                ypos, scaled_vals_this, thickness, align='edge', color=color, xerr=xerr
            )
            texts = list()
            for val, std, unit in zip(vals_this, stddevs_this, units_this):
                if val == 0:
                    texts += ['']
                elif std:
                    texts += [f'{val:.2f} ± {std:.2f} {unit}']
                else:
                    texts += [f'{val:.2f} {unit}']
            _plot_label(ax, rects, texts)
        for ax in var_axes:
            ax.set_xlim([0, largest_x])
            if ax == var_axes[-1]:
                ax.set_xticks(np.arange(0, largest_x, XTICK_SPACING))

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

    conds, thevars, units = _pick_common_vars(values, plotvars)

    # 3 columns: bars, labels, bars
    gs = gridspec.GridSpec(len(thevars), 3, width_ratios=[1/2, 1, 1])

    # variable names go into their own column
    for ind, (var, unit) in enumerate(zip(thevars, units)):
        textax = fig.add_subplot(gs[ind, 0])
        textax.axis('off')
        label = f'{var}'
        #label = '%s (%s)' % (var, unit) if unit else var
        textax.text(0, 0.5, label, ha='left', va='center')

    rects = _plot_oneside(thevars, 'Left', 1, conds)
    rects = _plot_oneside(thevars, 'Right', 2, conds)

    if len(conds) > 1:
        fig.legend(
            rects,
            conds,
            fontsize=7,
            bbox_to_anchor=(0.5, 0),
            loc="lower right",
            bbox_transform=fig.transFigure,
        )

    if figtitle is not None:
        fig.suptitle(figtitle)
    return fig


def _annotate_axis(ax, text):
    """Annotate at center of matplotlib axis"""
    ax.annotate(
        text,
        xy=(0.5, 0.5),
        xycoords='axes fraction',
        ha="center",
        va="center",
        fontsize=cfg.plot_matplotlib.subtitle_fontsize,
    )


def _remove_ticks_and_labels(ax):
    """Remove all ticks and labels"""
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
    emg_normaldata=None,
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
    """Plot gait trials using matplotlib.

    Parameters
    ----------
    trials : list
        List of Trial instances to plot.
    layout : list
        The plot layout to use.
    model_normaldata : dict | None
        Normaldata for model variables. If None, taken from cfg.
    emg_normaldata : dict | None
        Normal data for EMG variables. If None, taken from cfg.
    cycles : dict | str | int | tuple | list
        Cycles to plot. See Trial.get_cycles() for details.
    max_cycles : dict | None
        Maximum number of cycles to plot for each variable type. If None, taken
        from cfg.
    emg_mode : str | None
        If 'envelope', plot EMG in envelope mode.
    legend_type : str | None
        Legend type for gait cycles (see _get_cycle_name for options). If None,
        taken from cfg.
    style_by : dict | None
        How to style each variable type. If None, taken from cfg.
    color_by : dict | None
        How to color each variable type. If None, taken from cfg.
    supplementary_data : dict | None
        Supplementary data to plot for each variable.
    legend : bool
        If True, plot the legend.
    figtitle : str | None
        Main title for the figure.

    Returns
    -------
    Figure
        The matplotlib figure object.
    """
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
        model_normaldata = normaldata._read_configured_model_normaldata()

    if emg_normaldata is None:
        emg_normaldata = normaldata._read_emg_normaldata_file(cfg.emg.normaldata_file)

    if emg_mode not in (None, 'envelope'):
        raise ValueError('invalid EMG mode parameter')
    use_envelope = emg_mode == 'envelope'

    nrows, ncols = layouts._check_layout(layout)

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

        cyclebunch = _get_trial_cycles(trial, cycles, max_cycles)
        # the idea here is to sort the trial cycles by their legend key, so they
        # appear in the legend in correct order
        sorter = partial(_get_cycle_name, trial, name_type=legend_type)
        allcycles = sorted(cyclebunch.allcycles, key=sorter)

        for cyc_ind, cyc in enumerate(allcycles):

            first_cyc = trial_ind == 0 and cyc_ind == 0
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

                    vartype = _triage_var(var, trial)
                    if vartype is None:
                        ax.axis('off')
                        continue

                    # tracegroup is the legend entry for this cycle
                    # depending on name_type, one tracegroup may end up
                    # holding several cycles, which will be under the same
                    # legend entry.
                    cyclename = _get_cycle_name(trial, cyc, name_type=legend_type)
                    cyclename_full = _get_cycle_name(trial, cyc, name_type='full')

                    if vartype == 'model':
                        do_plot = cyc in cyclebunch.model_cycles
                        themodel = models.model_from_var(var)
                        if var in themodel.varnames_noside:
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
                            and themodel.is_kinetic_var(var)
                            and not cyc.on_forceplate
                        ):
                            do_plot = False

                        # plot normal data before first cycle
                        if model_normaldata is not None and first_cyc and normalized:
                            nvar = var if var in themodel.varlabels_noside else var[1:]
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

                        t, y = trial.get_model_data(var, cycle=cyc)
                        if y is None:
                            do_plot = False

                        if do_plot:
                            # get style and color
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
                            leg_entries[cyclename] = line_

                            # add toeoff marker
                            if cyc.toeoffn is not None:
                                toeoff_marker = ax.plot(
                                    t[cyc.toeoffn : cyc.toeoffn + 1],
                                    y[cyc.toeoffn : cyc.toeoffn + 1],
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
                                    leg_entries['Stddev for %s' % cyclename] = stddev_

                            # add supplementary data
                            # XXX: not implemented for matplotlib

                            # axis adjustments for model variable
                            if not ax.get_ylabel():
                                yunit = themodel.units[var]
                                if yunit == 'deg':
                                    yunit = '\u00B0'  # degree sign
                                ydesc = [s[:3] for s in themodel.ydesc[var]]  # shorten
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

                    # plot marker variable
                    elif vartype == 'marker':
                        do_plot = cyc in cyclebunch.model_cycles

                        t, mdata = trial.get_marker_data(var, cycle=cyc)
                        if mdata is None:
                            do_plot = False

                        if do_plot:

                            for datadim, data in zip('XYZ', mdata.T):
                                sty = _style_by_params(
                                    style_by['marker'],
                                    trace_styles,
                                    trial,
                                    cyc,
                                    context,
                                    datadim,
                                )
                                col = _color_by_params(
                                    color_by['marker'],
                                    trace_colors,
                                    trial,
                                    cyc,
                                    context,
                                    datadim,
                                )

                                line_ = ax.plot(
                                    t,
                                    data,
                                    color=col,
                                    linestyle=sty,
                                    linewidth=cfg.plot.model_linewidth,
                                    alpha=cfg.plot.model_alpha,
                                )[0]

                                # dim-specific tracename
                                tracename_marker = 'mkr_%s:%s' % (datadim, cyclename)
                                leg_entries[tracename_marker] = line_

                                # add toeoff marker
                                if cyc.toeoffn is not None:
                                    toeoff_marker = ax.plot(
                                        t[cyc.toeoffn : cyc.toeoffn + 1],
                                        data[cyc.toeoffn : cyc.toeoffn + 1],
                                        col,
                                        marker='^',
                                    )

                            # adjust subplot once
                            if (
                                not ax.get_ylabel()
                            ):  # this gets modified the first time around
                                ylabel = 'mm'
                                ax.set(ylabel=ylabel)

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

                    # plot EMG variable
                    elif vartype == 'emg':
                        do_plot = (
                            trial.emg is not None
                            and trial.emg.context_ok(var, context)
                            and trial.emg.status_ok(var)
                            and cyc in cyclebunch.emg_cycles
                        )
                        # FIXME: maybe annotate disconnected chans
                        # _no_ticks_or_labels(ax)
                        # _axis_annotate(ax, 'disconnected')
                        if do_plot:

                            t_, y = trial.get_emg_data(
                                var, envelope=use_envelope, cycle=cyc
                            )
                            t = t_ if normalized else t_ / trial.samplesperframe

                            col = _color_by_params(
                                color_by['emg'], emg_trace_colors, trial, cyc, context
                            )
                            lw = (
                                cfg.plot.emg_envelope_linewidth
                                if use_envelope
                                else cfg.plot.emg_linewidth
                            )
                            line_ = ax.plot(
                                t, y * cfg.plot.emg_multiplier, color=col, linewidth=lw
                            )[0]
                            leg_entries['EMG: ' + cyclename] = line_

                        # do normal data & plot adjustments for last EMG cycle
                        # keeps track of whether any trials have valid EMG data for this
                        # variable; otherwise, we annotatate channel as disconnected
                        emg_any_ok[var] |= trial.emg.status_ok(var)
                        remaining = allcycles[cyc_ind + 1 :]
                        last_emg = trial == trials[-1] and not any(
                            c in remaining for c in cyclebunch.emg_cycles
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

                    elif vartype == 'unknown':
                        raise GaitDataError('cannot interpret variable %s' % var)

                    else:
                        raise GaitDataError(
                            'plotting not implemented for variable %s' % var
                        )

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
        # Py2: this hack is no longer necessary in matplotlib 3.x or newer
        if figtitle and figtitle[-1] != '\n':
            figtitle = figtitle + '\n'
        fig.suptitle(figtitle, fontsize=10)

    if legend:
        # put legend into its own axis, since constrained_layout does not handle fig.legend yet
        # see https://github.com/matplotlib/matplotlib/issues/13023
        axleg = fig.add_subplot(gridspec_[i + 1, :])
        axleg.axis('off')
        leg_entries_ = dict()
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
