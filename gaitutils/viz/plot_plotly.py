# -*- coding: utf-8 -*-
"""
plotly based plotting functions

@author: Jussi (jnu@iki.fi)
"""

import logging
from collections import defaultdict
from functools import partial

import numpy as np
import plotly
import plotly.graph_objs as go
from plotly.matplotlylib.mpltools import merge_color_and_opacity
import plotly.tools
import plotly.subplots

from ..envutils import GaitDataError
from ..config import cfg
from ..stats import AvgTrial
from ..timedist import _pick_common_vars
from .. import models, normaldata, utils
from . import layouts
from .plot_common import (
    _get_cycle_name,
    _var_title,
    _cyclical_mapper,
    _style_mpl_to_plotly,
    _handle_cyclespec,
    _handle_style_and_color_args,
    _color_by_params,
    _style_by_params,
    _emg_yscale,
    _get_trial_cycles,
    _triage_var,
    _compose_varname,
    _nested_get,
    _tick_spacing,
)


logger = logging.getLogger(__name__)


def plot_extracted_box(curve_vals, vardefs):
    """Plot comparison of extracted gait curve values as box plot.

    Parameters
    ----------
    vardefs : list
        Nested list of variable definitions. The definitions are
    curve_vals : dict
        The curve extracted data, keyed by session.
    """

    contexts = utils.get_contexts()
    nvars = len(vardefs)
    subtitles = [_compose_varname(nested_keys) for nested_keys in vardefs]
    fig = plotly.subplots.make_subplots(rows=nvars, cols=1, subplot_titles=subtitles)
    legendgroups = set()

    # the plotting logic is a bit weird due to the way go.Box() works:
    # -we first consolidate a single variable's data from all sessions into a 1-d array
    # -this is done separately for L/R
    # -the consolidated data is then plotted along with the session identifiers
    for row, vardef in enumerate(vardefs):
        for ctxt, _ in contexts:
            vals = list()
            groupnames = list()
            vardef_ctxt = [ctxt + vardef[0]] + vardef[1:]
            for session, session_vals in curve_vals.items():
                if vardef_ctxt[0] not in session_vals:
                    logger.debug(f"{vardef_ctxt[0]} was not collected for this session")
                    continue
                this_vals = _nested_get(session_vals, vardef_ctxt)
                vals.extend(this_vals)
                # do not add session label on x axis if we only have a single session
                label = session if len(curve_vals) > 1 else ""
                groupnames.extend([label] * len(this_vals))
            # show entry in legend only if it was not already shown
            show_legend = ctxt not in legendgroups
            legendgroups.add(ctxt)
            box = go.Box(
                x=groupnames,
                y=vals,
                boxpoints=False,
                name=ctxt,
                offsetgroup=ctxt,
                legendgroup=ctxt,
                showlegend=show_legend,
                opacity=0.5,
                # mode='lines+markers',
                marker_color=cfg.plot.context_colors[ctxt],
            )
            fig.append_trace(box, row=row + 1, col=1)
            ylabel = _plotly_var_ylabel(vardef_ctxt[0])
            _, yaxis = _get_plotly_axis_labels(row, 0, ncols=1)
            fig["layout"][yaxis].update(
                title={
                    "font": {"size": cfg.plot_plotly.label_fontsize},
                    "text": ylabel,
                    "standoff": 0,
                }
            )
    # group together boxes of the different traces for each value of x
    fig.update_layout(boxmode="group")
    # set subplot title font size
    for anno in fig["layout"]["annotations"]:
        anno["font"]["size"] = cfg.plot_plotly.subtitle_fontsize
    return fig


def time_dist_barchart(
    values,
    stddev=None,
    thickness=0.5,
    color=None,
    stddev_bars=True,
    plotvars=None,
    timedist_normaldata=None,
    big_fonts=False,
    figtitle=None,
):

    """Multi-variable and multi-condition barchart plot.

    Used mostly for plotting time-distance variables.

    Parameters
    ----------
    values : dict
        Nested dict of values to plot. The data values are given in
        values[condition][var][context] where context is 'Left' or 'Right' and
        their units in values[condition][var]['unit']. Usually it is the output
        of timedist._group_analysis_trials().
    stddev : dict | None
        Dict with structure similar to values, but provides standard deviation
        for each variable.
    thickness : float, optional
        Y direction thickness of the bars. XXX: not implemented
    color : list, optional
        List of colors for the different conditions. If None, use default values.
        XXX: not implemented
    stddev_bars : bool, optional
        Whether to plot standard deviation as bars. XXX: not implemented
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
    dict
        The chart.
    """

    def _space_unit(unit):
        """Inserts a space before unit, except for %"""
        return f"{unit}" if unit == "%" else f" {unit}"

    if timedist_normaldata is None:
        timedist_normaldata = normaldata._read_timedist_normaldata_file(
            cfg.general.timedist_normaldata
        )

    conds, thevars, units = _pick_common_vars(values, plotvars)
    thevars = thevars[::-1]  # plotly yaxis starts from bottom
    units = units[::-1]

    legend_fontsize = cfg.plot_plotly.legend_fontsize
    label_fontsize = cfg.plot_plotly.label_fontsize
    subtitle_fontsize = cfg.plot_plotly.subtitle_fontsize
    if big_fonts:
        legend_fontsize += 2
        label_fontsize += 2
        subtitle_fontsize += 2

    ctxts = ["Left", "Right"]

    # flatten data into simple arrays of nvars x 1
    data = dict()
    for cond in conds:
        data[cond] = dict()
        for ctxt in ctxts:
            data[cond][ctxt] = np.array([values[cond][var][ctxt] for var in thevars])

    # flatten the scaling the same way as the data, replace missing vars with np.nan
    _timedist_normaldata = list()
    for var in thevars:
        if var in timedist_normaldata and timedist_normaldata[var] is not None:
            _timedist_normaldata.append(timedist_normaldata[var])
        else:
            _timedist_normaldata.append(np.nan)

    # scale the data
    scaler = dict()
    for ctxt in ctxts:
        # preferentially use given scales; if not available, use max value of
        # variable over all conditions
        max_scaler = np.max(np.array([data[c][ctxt] for c in conds]), axis=0)
        scaler[ctxt] = np.array(
            [
                x if not np.isnan(x) else max_scaler[k]
                for k, x in enumerate(_timedist_normaldata)
            ]
        )
    data_scaled = dict()
    for cond in conds:
        data_scaled[cond] = dict()
        for ctxt in ctxts:
            data_scaled[cond][ctxt] = 100 * data[cond][ctxt] / scaler[ctxt]

    # create bar labels
    bar_labels = dict()
    for cond in conds:
        bar_labels[cond] = dict()
        for ctxt in ctxts:
            if stddev:
                stddevs = np.array([stddev[cond][var][ctxt] for var in thevars])
            else:
                stddevs = [""] * len(thevars)
            bar_labels[cond][ctxt] = list()
            do_stddevs = stddev and stddevs.max() > 0
            for val, scaled_val, std, unit in zip(
                data[cond][ctxt], data_scaled[cond][ctxt], stddevs, units
            ):
                stddev_txt = f"±{std:.2f}" if do_stddevs else ""
                unit_s = _space_unit(unit)
                txt = f"{val:.2f}{stddev_txt}{unit_s} ({scaled_val:.0f}%)"
                bar_labels[cond][ctxt].append(txt)

    # compose bold subplot titles
    subplot_titles = [f"<b>{s}</b>" for s in ctxts]

    fig = plotly.subplots.make_subplots(
        rows=1,
        cols=2,
        specs=[[{}, {}]],
        shared_xaxes=True,
        shared_yaxes=True,
        vertical_spacing=0,
        horizontal_spacing=0.05,
        subplot_titles=subplot_titles,
    )

    # ordering the bars properly is a bit tricky. seemingly, there's no way to control
    # ordering of bars within a category, and they seem to be plotted from bottom to up by default.
    # a dirty solution is to plot in reversed order and then reverse the legend also.
    varlabels = list()
    for var, unit in zip(thevars, units):
        # insert reference values if we have them
        if var in timedist_normaldata:
            ref = timedist_normaldata[var]
            unit_s = _space_unit(unit)
            this_label = f"{var} (ref. {ref:.2f}{unit_s}) "
            varlabels.append(this_label)
        else:
            varlabels.append(f"{var} ")
    for condn, cond in enumerate(reversed(conds)):
        barcolor = cfg.plot.colors[condn]
        for k, ctxt in enumerate(ctxts, 1):
            show_legend = k == 1  # legend entry is created only once per condition
            trace_l = go.Bar(
                y=varlabels,
                x=data_scaled[cond][ctxt],
                orientation="h",
                name=cond,
                legendgroup=cond,
                text=bar_labels[cond][ctxt],
                textfont={"size": label_fontsize + 2},
                textposition="auto",
                showlegend=show_legend,
                hoverlabel=dict(namelength=-1),
                hoverinfo="y+text+name",
                marker_color=barcolor,
            )
            fig.add_trace(trace_l, 1, k)
            fig["layout"]["legend"]["traceorder"] = "reversed"
            # increase var label size a bit
            fig["layout"]["yaxis%d" % k].update(tickfont={"size": label_fontsize + 2})
            fig["layout"]["xaxis%d" % k].update(
                title={"text": "% of reference", "font": {"size": label_fontsize}}
            )
            # this sets the full x scale for all bars simultaneously; it is set
            # to the maximum scaled value among all vars and conditions (i.e. if
            # biggest scaled variable is 160% of its reference value, the full x
            # scale will be 160%)
            max_val_this = np.nanmax(np.array([data_scaled[c][ctxt] for c in conds]))
            # set ticks
            tickvals = _tick_spacing(0, max_val_this)
            fig["layout"]["xaxis%d" % k].update({"range": [0, max(tickvals)]})
            fig["layout"]["xaxis%d" % k].update(
                {"tickmode": "array", "tickvals": tickvals}
            )

    margin = go.layout.Margin(l=50, r=0, b=50, t=50, pad=4)  # NOQA: 741
    legend = dict(font=dict(size=legend_fontsize))
    plotly_layout = go.Layout(
        margin=margin,
        legend=legend,
        paper_bgcolor="rgba(255,255,255,0)",  # no background please
        plot_bgcolor="rgba(255,255,255,0)",
        font={"size": label_fontsize},
        hovermode="closest",
        title=figtitle,
    )

    fig["layout"].update(plotly_layout)
    for anno in fig["layout"]["annotations"]:
        anno["font"]["size"] = subtitle_fontsize

    # add vertical line at 100%
    fig.add_vline(x=100, line_width=1, line_dash="dash", opacity=0.5)
    # add annotation "reference" for reference values
    # this is a bit hacky, since negative x coords don't seem to work
    anno_text = f"<b>Reference values{10 * ' '}</b>"  # margin by spaces
    fig.add_annotation(
        x=0,
        y=len(thevars),
        text=anno_text,
        xref="x",
        yref="y",
        showarrow=False,
        font={"size": subtitle_fontsize},
        xanchor="right",
    )

    return fig


def _plot_vels(vels, labels, title=None):
    """Plot trial velocities as a stem plot"""
    trace = dict(y=vels, x=labels, mode="markers")
    layout = dict(
        title=title,
        xaxis=dict(title="Trial", automargin=True),
        yaxis=dict(title="Speed (m/s)", rangemode="tozero"),
    )

    return dict(data=[trace], layout=layout)


def _plot_timedep_vels(vels, labels, title=None):
    """Plot trial time-dependent velocities"""
    traces = list()
    for vel, label in zip(vels, labels):
        trace = dict(y=vel, text=label, name=label, hoverinfo="x+y+text")
        traces.append(trace)
    # FIXME: labels get truncated, not fixed by automargin
    layout = dict(
        title=title,
        xaxis=dict(title="% of trial", automargin=True),
        yaxis=dict(title="Velocity (m/s)"),
    )
    return dict(data=traces, layout=layout)


def _plotly_fill_between(x, ylow, yhigh, **kwargs):
    """Fill area between ylow and yhigh"""
    x_ = np.concatenate([x, x[::-1]])  # construct a closed curve
    y_ = np.concatenate([yhigh, ylow[::-1]])
    return dict(x=x_, y=y_, fill="toself", mode="none", hoverinfo="none", **kwargs)


def plot_trials_browser(trials, layout, **kwargs):
    """Convenience plotter, uses plotly.offline to plot directly to browser"""
    fig = plot_trials(trials, layout, **kwargs)
    plotly.offline.plot(fig)


def _get_plotly_axis_labels(row, col, ncols):
    """Gets plotly axis labels from zero-based row and col indices"""
    plot_ind = row * ncols + col + 1  # plotly subplot index
    return f"xaxis{plot_ind}", f"yaxis{plot_ind}"


def _plotly_var_ylabel(var, themodel=None):
    """Make ylabel for model variable var"""
    if themodel is None:
        themodel = models.model_from_var(var)
    yunit = themodel.units[var]
    if yunit == "deg":
        yunit = "\u00B0"  # Unicode degree sign
    ydesc = [s[:3] for s in themodel.ydesc[var]]  # shorten
    return f"{ydesc[0]} {yunit} {ydesc[1]}"


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
    big_fonts=False,
):
    """Plot gait trials using Plotly.

    Parameters
    ----------
    trials : list
        List of Trial instances to plot.
    layout : list
        The plot layout to use.
    model_normaldata : dict | None
        Normal data for model variables. If None, taken from config.
    emg_normaldata : dict | None
        Normal data for EMG variables. If None, taken from config.
    cycles : dict | str | None
        Gait cycles to plot.
        If dict, specifies cycles to plot for each variable type. Currently
        allowed keys are 'model', 'marker' and 'emg'. Currently allowed
        specifier values are: 'forceplate' to get forceplate cycles, 'all' to
        get all cycles, 'unnormalized' to get data without cycle normalization.
        Alternatively, integer values can be supplied to get a specific cycle
        index (note that indices start from 0).
        If str, the same specifier will be applied to all variable types. The
        allowed specifiers are same as above. Examples:
        Plot all cycles for all variable types:
        cycles = 'all'
        Plot forceplate cycles for model variables:
        cycles = {'model': 'forceplate'}
        Plot 1st cycle for EMG:
        cycles = {'emg': 0}
    max_cycles : dict | None
        Maximum number of cycles to plot for each variable type. Values not
        specified are taken from config. If None, all values are taken from
        config.
    emg_mode : str | None
        If 'envelope', plot EMG in envelope mode.
    legend_type : str | None
        Legend type for gait cycles (see _get_cycle_name for options). If None,
        taken from config.
    style_by : dict | None
        How to style each variable type. If None, taken from config.
    color_by : dict | None
        How to color each variable type. If None, taken from config.
    supplementary_data : dict | None
        Supplementary data to plot for each variable.
    legend : bool
        If True, plot the legend.
    figtitle : str | None
        Main title for the figure.
    big_fonts : bool
        If True, increase font sizes somewhat.

    Returns
    -------
    dict
        The Plotly figure object.
    """

    if not trials:
        raise GaitDataError("No trials")

    if not isinstance(trials, list):
        trials = [trials]

    style_by, color_by = _handle_style_and_color_args(style_by, color_by)

    if legend_type is None:
        legend_type = "short_name_with_cyclename"

    if supplementary_data is None:
        supplementary_data = dict()

    if model_normaldata is None:
        model_normaldata = normaldata._read_configured_model_normaldata()

    if emg_normaldata is None:
        emg_normaldata = normaldata._read_emg_normaldata_file(cfg.emg.normaldata_file)

    if emg_mode not in (None, "envelope"):
        raise ValueError("invalid EMG mode parameter")
    use_envelope = emg_mode == "envelope"

    nrows, ncols = layouts._check_layout(layout)

    # these generate and keep track of key -> linestyle (or color) mappings
    trace_colors = _cyclical_mapper(cfg.plot.colors)
    emg_trace_colors = _cyclical_mapper(cfg.plot.colors)
    trace_styles = _cyclical_mapper(cfg.plot.linestyles)

    allvars = [item for row in layout for item in row]
    titles = [_var_title(var) for var in allvars]
    fig = plotly.subplots.make_subplots(
        rows=nrows, cols=ncols, print_grid=False, subplot_titles=titles
    )
    legendgroups = set()
    model_normaldata_legend = True
    emg_normaldata_legend = True

    normalized = cycles != "unnormalized"
    cycles = _handle_cyclespec(cycles)
    if max_cycles is None:
        max_cycles = cfg.plot.max_cycles

    legend_fontsize = cfg.plot_plotly.legend_fontsize
    label_fontsize = cfg.plot_plotly.label_fontsize
    subtitle_fontsize = cfg.plot_plotly.subtitle_fontsize
    if big_fonts:
        legend_fontsize += 2
        label_fontsize += 2
        subtitle_fontsize += 2

    # plot normaldata first to ensure that its z order is lowest
    # and it gets the 1st legend entries
    if normalized:
        for i, row in enumerate(layout):
            for j, var in enumerate(row):
                themodel = models.model_from_var(var)
                if themodel and model_normaldata:
                    nvar = var if var in themodel.varlabels_nocontext else var[1:]
                    key = nvar if nvar in model_normaldata else None
                    ndata = model_normaldata[key] if key in model_normaldata else None
                    if ndata is not None:
                        normalx = np.linspace(0, 100, ndata.shape[0])
                        fillcolor = merge_color_and_opacity(
                            cfg.plot.model_normals_color, cfg.plot.model_normals_alpha
                        )
                        ntrace = _plotly_fill_between(
                            normalx,
                            ndata[:, 0],
                            ndata[:, 1],
                            fillcolor=fillcolor,
                            name="Norm.",
                            legendgroup="Norm.",
                            showlegend=model_normaldata_legend,
                            line=dict(width=0),
                        )  # no border lines
                        fig.add_trace(ntrace, i + 1, j + 1)
                        model_normaldata_legend = False  # mark as plotted

                # plot EMG normal data as a heatmap
                elif var in cfg.emg.channel_labels and var in emg_normaldata:
                    # build x, y, z triplets for the heatmap
                    # cell size is automatically determined from y values, which is a bit clumsy
                    # the idea is to build two strips of normal data at nearby y values, which fixes
                    # the cell size at a small value (dy)
                    _emg_y_extent = _emg_yscale(emg_mode)
                    extent_y0 = _emg_y_extent[0]
                    extent_y1 = extent_y0 + (_emg_y_extent[1] - _emg_y_extent[0]) / 20.0
                    Npts = 101
                    x = np.concatenate(
                        (np.linspace(0, 100, Npts), np.linspace(0, 100, Npts))
                    )
                    y = np.concatenate(
                        (extent_y0 * np.ones(Npts), extent_y1 * np.ones(Npts))
                    )
                    z = np.concatenate((emg_normaldata[var], emg_normaldata[var]))
                    heatmap = go.Heatmap(
                        z=z,
                        y=y,
                        x=x,
                        colorscale="reds",
                        zmin=0,
                        zmax=1,
                        opacity=0.5,
                        showscale=False,
                        name="EMG norm.",
                        legendgroup="EMG norm.",
                        showlegend=emg_normaldata_legend,
                    )
                    fig.add_trace(heatmap, i + 1, j + 1)
                    emg_normaldata_legend = False  # mark as plotted

    # plot the actual data
    for trial in trials:
        subplot_adjusted = defaultdict(lambda: False)
        cyclebunch = _get_trial_cycles(trial, cycles, max_cycles)
        # the idea here is to sort the trial cycles by their legend key, so they
        # appear in the legend in correct order
        sorter = partial(_get_cycle_name, trial, name_type=legend_type)
        allcycles = sorted(cyclebunch.allcycles, key=sorter)

        for cyc in allcycles:

            context = cyc.context

            for i, row in enumerate(layout):
                for j, var in enumerate(row):

                    vartype = _triage_var(var, trial)
                    if vartype is None:
                        continue

                    xaxis, yaxis = _get_plotly_axis_labels(i, j, ncols)

                    cyclename = _get_cycle_name(trial, cyc, name_type=legend_type)
                    cyclename_full = _get_cycle_name(trial, cyc, name_type="full")

                    if vartype == "model":
                        do_plot = cyc in cyclebunch.model_cycles
                        themodel = models.model_from_var(var)
                        if var in themodel.varnames_nocontext:
                            # var context was unspecified, so choose it
                            # according to cycle context
                            var = context + var
                        elif var[0] != context:
                            # var context was specified and does not match cycle
                            do_plot = False

                        # kinetic var cycles are required to have valid
                        # forceplate data
                        if (
                            normalized
                            and themodel.is_kinetic_var(var)
                            and not cyc.on_forceplate
                        ):
                            do_plot = False

                        t, y = trial.get_model_data(var, cycle=cyc)
                        if y is None:
                            do_plot = False

                        if do_plot:
                            sty = _style_by_params(
                                style_by["model"], trace_styles, trial, cyc, context
                            )
                            sty = _style_mpl_to_plotly(sty)
                            col = _color_by_params(
                                color_by["model"], trace_colors, trial, cyc, context
                            )

                            line = dict(
                                width=cfg.plot.model_linewidth, dash=sty, color=col
                            )

                            # for model variables, put traces into legend groups
                            # according to trial/cycle info
                            legendgroup = cyclename
                            show_legend = cyclename not in legendgroups

                            trace = dict(
                                x=t,
                                y=y,
                                name=cyclename,
                                text=cyclename_full,
                                legendgroup=legendgroup,
                                showlegend=show_legend,
                                hoverlabel=dict(namelength=-1),
                                hoverinfo="x+y+text",
                                line=line,
                            )

                            # add toeoff marker
                            if cyc.toeoffn is not None:
                                marker = dict(color=col, symbol="triangle-up", size=8)
                                toeoff_marker = dict(
                                    x=t[cyc.toeoffn : cyc.toeoffn + 1],
                                    y=y[cyc.toeoffn : cyc.toeoffn + 1],
                                    showlegend=False,
                                    legendgroup=legendgroup,
                                    hoverinfo="skip",
                                    mode="markers",
                                    marker=marker,
                                )
                                fig.add_trace(toeoff_marker, i + 1, j + 1)

                            # add trace to figure
                            fig.add_trace(trace, i + 1, j + 1)
                            legendgroups.add(legendgroup)

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
                                    fillcolor = merge_color_and_opacity(
                                        col,
                                        cfg.plot.model_stddev_alpha,
                                    )
                                    ntrace = _plotly_fill_between(
                                        stdx,
                                        y - sdata,
                                        y + sdata,
                                        fillcolor=fillcolor,
                                        name=f"Stddev, {cyclename}",
                                        legendgroup=f"Stddev, {cyclename}",
                                        showlegend=show_legend,
                                        line=dict(width=0),
                                    )  # no border lines
                                    fig.add_trace(ntrace, i + 1, j + 1)

                            # add supplementary data
                            if cyc in supplementary_data:
                                supdata = supplementary_data[cyc]
                                if var in supdata:
                                    logger.debug(
                                        f"plotting supplementary data for var {var}"
                                    )
                                    t_sup = supdata[var]["t"]
                                    data_sup = supdata[var]["data"]
                                    label_sup = supdata[var]["label"]

                                    strace = dict(
                                        x=t_sup,
                                        y=data_sup,
                                        name=label_sup,
                                        text=label_sup,
                                        line=line,
                                        legendgroup=cyclename,
                                        hoverinfo="x+y+text",
                                        showlegend=False,
                                    )
                                    fig.add_trace(strace, i + 1, j + 1)
                                    legendgroups.add(cyclename)

                            # adjust subplot once
                            if not subplot_adjusted[(i, j)]:
                                ylabel = _plotly_var_ylabel(var, themodel)
                                fig["layout"][yaxis].update(
                                    title={
                                        "text": ylabel,
                                        "font": {"size": label_fontsize},
                                        "standoff": 0,
                                    }
                                )
                                # less decimals on hover label
                                fig["layout"][yaxis].update(hoverformat=".2f")
                                subplot_adjusted[(i, j)] = True

                    elif vartype == "marker":
                        do_plot = cyc in cyclebunch.marker_cycles
                        t, mdata = trial.get_marker_data(var, cycle=cyc)
                        if mdata is None:
                            do_plot = False

                        if do_plot:

                            for datadim, data in zip("XYZ", mdata.T):
                                sty = _style_by_params(
                                    style_by["marker"],
                                    trace_styles,
                                    trial,
                                    cyc,
                                    context,
                                    datadim,
                                )
                                sty = _style_mpl_to_plotly(sty)
                                col = _color_by_params(
                                    color_by["marker"],
                                    trace_colors,
                                    trial,
                                    cyc,
                                    context,
                                    datadim,
                                )
                                line = dict(
                                    width=cfg.plot.model_linewidth, dash=sty, color=col
                                )
                                # dim-specific tracename
                                tracename_marker = f"mkr_{datadim}:{cyclename}"
                                # dimension- and trial-based grouping
                                # legendgroup = 'mkr_%s:%s' % (datadim, trial.trialname)
                                # dimension- and cycle-based grouping
                                legendgroup = tracename_marker
                                show_legend = legendgroup not in legendgroups
                                trace = dict(
                                    x=t,
                                    y=data,
                                    name=tracename_marker,
                                    text=cyclename_full,
                                    legendgroup=legendgroup,
                                    showlegend=show_legend,
                                    hoverlabel=dict(namelength=-1),
                                    hoverinfo="x+y+name",
                                    line=line,
                                )
                                fig.add_trace(trace, i + 1, j + 1)
                                legendgroups.add(legendgroup)

                                # add toeoff marker
                                if cyc.toeoffn is not None:
                                    cyc.toeoffn = int(cyc.toeoffn)
                                    marker = dict(
                                        color=col, symbol="triangle-up", size=8
                                    )
                                    toeoff_marker = dict(
                                        x=t[cyc.toeoffn : cyc.toeoffn + 1],
                                        y=data[cyc.toeoffn : cyc.toeoffn + 1],
                                        showlegend=False,
                                        legendgroup=legendgroup,
                                        hoverinfo="skip",
                                        mode="markers",
                                        marker=marker,
                                    )
                                    fig.add_trace(toeoff_marker, i + 1, j + 1)

                            # adjust subplot once
                            if not subplot_adjusted[(i, j)]:
                                # fig['layout'][xaxis].update(showticklabels=False)
                                ylabel = "mm"
                                fig["layout"][yaxis].update(
                                    title={
                                        "text": ylabel,
                                        "font": {"size": label_fontsize},
                                        "standoff": 0,
                                    }
                                )
                                # less decimals on hover label
                                fig["layout"][yaxis].update(hoverformat=".2f")
                                subplot_adjusted[(i, j)] = True

                    # plot EMG variable
                    elif vartype == "emg":
                        do_plot = (
                            trial.emg.context_ok(var, cyc.context)
                            and trial.emg.status_ok(var)
                            and cyc in cyclebunch.emg_cycles
                        )
                        # FIXME: maybe annotate disconnected chans
                        # _no_ticks_or_labels(ax)
                        # _axis_annotate(ax, 'disconnected')
                        if do_plot:
                            tracename_emg = "EMG:" + cyclename

                            t_, y = trial.get_emg_data(
                                var, envelope=use_envelope, cycle=cyc
                            )
                            t = t_ if normalized else t_ / trial.samplesperframe

                            col = _color_by_params(
                                color_by["emg"], emg_trace_colors, trial, cyc, context
                            )
                            col = merge_color_and_opacity(col, cfg.plot.emg_alpha)
                            lw = (
                                cfg.plot.emg_envelope_linewidth
                                if use_envelope
                                else cfg.plot.emg_linewidth
                            )
                            line = {"width": lw, "color": col}

                            # EMG traces get grouped according to cycle (same
                            # legendgroup as model traces)
                            # the tracename_emg legend group does not actually exist
                            # in plotly, it's only used to keep track of whether the
                            # EMG trace legend was already shown.
                            show_legend = tracename_emg not in legendgroups
                            legendgroup = cyclename

                            trace = dict(
                                x=t,
                                y=y * cfg.plot.emg_multiplier,
                                name=tracename_emg,
                                legendgroup=legendgroup,
                                showlegend=show_legend,
                                line=line,
                            )
                            legendgroups.add(tracename_emg)
                            fig.add_trace(trace, i + 1, j + 1)

                        # adjust subplot once
                        if not subplot_adjusted[(i, j)]:
                            logger.debug(f'adjusting EMG subplot {i},{j}')
                            fig["layout"][yaxis].update(
                                title={
                                    "text": cfg.plot.emg_ylabel,
                                    "font": {"size": label_fontsize},
                                    "standoff": 0,
                                },
                                range=_emg_yscale(emg_mode),
                            )
                            # prevent changes due to legend clicks etc.
                            if normalized:
                                fig["layout"][xaxis].update(range=[0, 100])
                            # rm x tick labels, plot too crowded
                            # fig['layout'][xaxis].update(showticklabels=False)
                            # less decimals on hover label
                            # XXX: this is not working?
                            fig["layout"][yaxis].update(hoverformat=".2f")
                            subplot_adjusted[(i, j)] = True

                    elif vartype == "unknown":
                        raise GaitDataError(f"cannot interpret variable {var}")

                    else:
                        raise GaitDataError(
                            f"plotting not implemented for variable {var}"
                        )

    # set subplot title font size
    for anno in fig["layout"]["annotations"]:
        anno["font"]["size"] = subtitle_fontsize

    # put x labels on last row only, re-enable tick labels for last row
    inds_last = range((nrows - 1) * ncols, nrows * ncols)
    axes_last = ["xaxis%d" % (ind + 1) for ind in inds_last]
    xlabel = "% of gait cycle" if normalized else "frame"
    for ax in axes_last:
        fig["layout"][ax].update(
            title={"text": xlabel, "font": {"size": label_fontsize}},
            showticklabels=True,
        )

    margin = go.layout.Margin(l=50, r=0, b=50, t=50, pad=4)  # NOQA: 741
    legend = dict(font=dict(size=legend_fontsize))
    plotly_layout = go.Layout(
        margin=margin,
        legend=legend,
        font={"size": label_fontsize},
        hovermode="closest",
        title=figtitle,
    )

    fig["layout"].update(plotly_layout)
    return fig
