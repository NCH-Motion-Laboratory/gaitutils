# -*- coding: utf-8 -*-
"""
plotly based plotting functions

@author: Jussi (jnu@iki.fi)
"""
from __future__ import division

from builtins import zip
import logging
from builtins import range
from collections import defaultdict
from functools import partial
import sys

import numpy as np
import plotly
import plotly.graph_objs as go
from plotly.matplotlylib.mpltools import merge_color_and_opacity
import plotly.tools
import plotly.subplots

from .. import GaitDataError, cfg, models, normaldata, numutils
from ..stats import AvgTrial
from ..timedist import _pick_common_vars
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
)


logger = logging.getLogger(__name__)


def time_dist_barchart(
    values,
    stddev=None,
    thickness=0.5,
    color=None,
    stddev_bars=True,
    plotvars=None,
    title=None,
    big_fonts=False,
    figtitle=None,
):
    """Multi-variable and multi-condition barchart plot.
    values dict is keyed as values[condition][var][context],
    given by e.g. get_c3d_analysis()
    stddev can be None or a dict keyed as stddev[condition][var][context].
    plotvars gives variables to plot (if not all) and their order.
    """
    conds, vars, units = _pick_common_vars(values, plotvars)
    vars = vars[::-1]  # plotly yaxis starts from bottom
    units = units[::-1]

    legend_fontsize = cfg.plot_plotly.legend_fontsize
    label_fontsize = cfg.plot_plotly.label_fontsize
    subtitle_fontsize = cfg.plot_plotly.subtitle_fontsize
    if big_fonts:
        legend_fontsize += 2
        label_fontsize += 2
        subtitle_fontsize += 2

    data = dict()
    texts = dict()
    ctxts = ['Left', 'Right']
    for cond in conds:
        data[cond] = dict()
        texts[cond] = dict()
        for ctxt in ctxts:
            # flatten data into simple arrays of nvars x 1
            data[cond][ctxt] = np.array([values[cond][var][ctxt] for var in vars])
            if stddev:
                stddevs = np.array([stddev[cond][var][ctxt] for var in vars])
            if stddevs.max() > 0:
                texts[cond][ctxt] = [
                    u'%.2f ± %.2f %s' % (val, std, unit)
                    for val, std, unit in zip(data[cond][ctxt], stddevs, units)
                ]
            else:
                texts[cond][ctxt] = [
                    u'%.2f %s' % (val, unit)
                    for val, unit in zip(data[cond][ctxt], units)
                ]

    # scale vars according to their maximums over all conditions
    scaler = dict()
    for ctxt in ctxts:
        scaler[ctxt] = np.max(np.array([data[c][ctxt] for c in conds]), axis=0)
    for cond in conds:
        for ctxt in ctxts:
            data[cond][ctxt] /= scaler[ctxt] * 0.01

    fig = plotly.subplots.make_subplots(
        rows=1,
        cols=2,
        specs=[[{}, {}]],
        shared_xaxes=True,
        shared_yaxes=True,
        vertical_spacing=0,
        horizontal_spacing=0.05,
        subplot_titles=ctxts,
    )

    # ordering the bars properly is a bit tricky. seemingly, there's no way to control
    # ordering of bars within a category, and they seem to be plotted from bottom to up by default.
    # a dirty solution is to plot in reversed order and then reverse the legend also.
    varlabels = [s + ' ' for s in vars]  # hack: add spaces to create some margin
    for condn, cond in enumerate(reversed(conds)):
        barcolor = cfg.plot.colors[condn]
        for k, ctxt in enumerate(ctxts, 1):
            show_legend = k == 1
            trace_l = go.Bar(
                y=varlabels,
                x=data[cond][ctxt],
                orientation='h',
                name=cond,
                legendgroup=cond,
                text=texts[cond][ctxt],
                textfont={'size': label_fontsize + 2},
                textposition='auto',
                showlegend=show_legend,
                hoverlabel=dict(namelength=-1),
                hoverinfo='y+text+name',
                marker_color=barcolor,
            )
            fig.add_trace(trace_l, 1, k)
            fig['layout']['legend']['traceorder'] = 'reversed'
            # increase var label size a bit
            fig['layout']['yaxis%d' % k].update(tickfont={'size': label_fontsize + 2})
            fig['layout']['xaxis%d' % k].update(
                title={'text': '% of maximum', 'font': {'size': label_fontsize}}
            )

    margin = go.layout.Margin(l=50, r=0, b=50, t=50, pad=4)  # NOQA: 741
    legend = dict(font=dict(size=legend_fontsize))
    plotly_layout = go.Layout(
        margin=margin,
        legend=legend,
        paper_bgcolor='rgba(255,255,255,0)',  # no background please
        plot_bgcolor='rgba(255,255,255,0)',
        font={'size': label_fontsize},
        hovermode='closest',
        title=figtitle,
    )

    fig['layout'].update(plotly_layout)
    for anno in fig['layout']['annotations']:
        anno['font']['size'] = subtitle_fontsize

    return fig


def _plot_vels(vels, labels, title=None):
    """Plot trial velocities as a stem plot"""
    trace = dict(y=vels, x=labels, mode='markers')
    layout = dict(
        title=title,
        xaxis=dict(title='Trial', automargin=True),
        yaxis=dict(title='Speed (m/s)'),
    )
    return dict(data=[trace], layout=layout)


def _plot_timedep_vels(vels, labels, title=None):
    """Plot trial time-dependent velocities"""
    traces = list()
    for vel, label in zip(vels, labels):
        trace = dict(y=vel, text=label, name=label, hoverinfo='x+y+text')
        traces.append(trace)
    # FIXME: labels get truncated, not fixed by automargin
    layout = dict(
        title=title,
        xaxis=dict(title='% of trial', automargin=True),
        yaxis=dict(title='Velocity (m/s)'),
    )
    return dict(data=traces, layout=layout)


def _plotly_fill_between(x, ylow, yhigh, **kwargs):
    """Fill area between ylow and yhigh"""
    x_ = np.concatenate([x, x[::-1]])  # construct a closed curve
    y_ = np.concatenate([yhigh, ylow[::-1]])
    return dict(x=x_, y=y_, fill='toself', mode='none', hoverinfo='none', **kwargs)


def plot_trials_browser(trials, layout, **kwargs):
    """ Convenience plotter, uses plotly.offline to plot directly to browser"""
    fig = plot_trials(trials, layout, **kwargs)
    plotly.offline.plot(fig)


def _get_plotly_axis_labels(i, j, ncols):
    """Gets plotly axis labels from subplot indices i, j"""
    plot_ind = i * ncols + j + 1  # plotly subplot index
    return 'xaxis%d' % plot_ind, 'yaxis%d' % plot_ind


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
    """Plot gait trials using the plotly backend."""

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
        emg_normaldata = normaldata._read_configured_emg_normaldata()

    use_rms = emg_mode == 'rms'

    nrows, ncols = layouts.check_layout(layout)

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

    normalized = cycles != 'unnormalized'
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
                    nvar = var if var in themodel.varlabels_noside else var[1:]
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
                            name='Norm.',
                            legendgroup='Norm.',
                            showlegend=model_normaldata_legend,
                            line=dict(width=0),
                        )  # no border lines
                        fig.add_trace(ntrace, i + 1, j + 1)
                        model_normaldata_legend = False  # mark as plotted

                elif var in cfg.emg.channel_labels and var in emg_normaldata:
                    # build x, y, z triplets for heatmap
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
                        colorscale='reds',
                        zmin=0,
                        zmax=1,
                        opacity=0.5,
                        showscale=False,
                        name='EMG norm.',
                        legendgroup='EMG norm.',
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
                    cyclename_full = _get_cycle_name(trial, cyc, name_type='full')

                    # plotly cannot directly handle unicode objects
                    # needs to be handled in py2/3 compatible way
                    if sys.version_info.major == 2 and isinstance(cyclename, unicode):
                        cyclename = cyclename.encode('utf-8')

                    if vartype == 'model':
                        do_plot = cyc in cyclebunch.model_cycles
                        themodel = models.model_from_var(var)
                        if var in themodel.varnames_noside:
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
                                style_by['model'], trace_styles, trial, cyc, context
                            )
                            sty = _style_mpl_to_plotly(sty)
                            col = _color_by_params(
                                color_by['model'], trace_colors, trial, cyc, context
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
                                hoverinfo='x+y+text',
                                line=line,
                            )

                            # add toeoff marker
                            if cyc.toeoffn is not None:
                                toeoff = int(cyc.toeoffn)
                                marker = dict(color=col, symbol='triangle-up', size=8)
                                toeoff_marker = dict(
                                    x=t[toeoff : toeoff + 1],
                                    y=y[toeoff : toeoff + 1],
                                    showlegend=False,
                                    legendgroup=legendgroup,
                                    hoverinfo='skip',
                                    mode='markers',
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
                                        col, cfg.plot.model_stddev_alpha,
                                    )
                                    ntrace = _plotly_fill_between(
                                        stdx,
                                        y - sdata,
                                        y + sdata,
                                        fillcolor=fillcolor,
                                        name='Stddev, %s' % cyclename,
                                        legendgroup='Stddev, %s' % cyclename,
                                        showlegend=show_legend,
                                        line=dict(width=0),
                                    )  # no border lines
                                    fig.add_trace(ntrace, i + 1, j + 1)

                            # add supplementary data
                            if cyc in supplementary_data:
                                supdata = supplementary_data[cyc]
                                if var in supdata:
                                    logger.debug(
                                        'plotting supplementary data '
                                        'for var %s' % var
                                    )
                                    t_sup = supdata[var]['t']
                                    data_sup = supdata[var]['data']
                                    label_sup = supdata[var]['label']

                                    strace = dict(
                                        x=t_sup,
                                        y=data_sup,
                                        name=label_sup,
                                        text=label_sup,
                                        line=line,
                                        legendgroup=cyclename,
                                        hoverinfo='x+y+text',
                                        showlegend=False,
                                    )
                                    fig.add_trace(strace, i + 1, j + 1)
                                    legendgroups.add(cyclename)

                            # adjust subplot once
                            if not subplot_adjusted[(i, j)]:
                                # fig['layout'][xaxis].update(showticklabels=False)
                                yunit = themodel.units[var]
                                if yunit == 'deg':
                                    yunit = u'\u00B0'  # Unicode degree sign
                                ydesc = [s[:3] for s in themodel.ydesc[var]]  # shorten
                                ylabel = u'%s %s %s' % (ydesc[0], yunit, ydesc[1])
                                if sys.version_info.major == 2 and isinstance(
                                    ylabel, unicode
                                ):
                                    ylabel = ylabel.encode('utf-8')
                                fig['layout'][yaxis].update(
                                    title={
                                        'text': ylabel,
                                        'font': {'size': label_fontsize},
                                        'standoff': 0,
                                    }
                                )
                                # less decimals on hover label
                                fig['layout'][yaxis].update(hoverformat='.2f')
                                subplot_adjusted[(i, j)] = True

                    elif vartype == 'marker':
                        do_plot = cyc in cyclebunch.marker_cycles
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
                                sty = _style_mpl_to_plotly(sty)
                                col = _color_by_params(
                                    color_by['marker'],
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
                                tracename_marker = 'mkr_%s:%s' % (datadim, cyclename)
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
                                    hoverinfo='x+y+name',
                                    line=line,
                                )
                                fig.add_trace(trace, i + 1, j + 1)
                                legendgroups.add(legendgroup)

                                # add toeoff marker
                                if cyc.toeoffn is not None:
                                    toeoff = int(cyc.toeoffn)
                                    marker = dict(
                                        color=col, symbol='triangle-up', size=8
                                    )
                                    toeoff_marker = dict(
                                        x=t[toeoff : toeoff + 1],
                                        y=data[toeoff : toeoff + 1],
                                        showlegend=False,
                                        legendgroup=legendgroup,
                                        hoverinfo='skip',
                                        mode='markers',
                                        marker=marker,
                                    )
                                    fig.add_trace(toeoff_marker, i + 1, j + 1)

                            # adjust subplot once
                            if not subplot_adjusted[(i, j)]:
                                # fig['layout'][xaxis].update(showticklabels=False)
                                ylabel = 'mm'
                                if sys.version_info.major == 2 and isinstance(
                                    ylabel, unicode
                                ):
                                    ylabel = ylabel.encode('utf-8')
                                fig['layout'][yaxis].update(
                                    title={
                                        'text': ylabel,
                                        'font': {'size': label_fontsize},
                                        'standoff': 0,
                                    }
                                )
                                # less decimals on hover label
                                fig['layout'][yaxis].update(hoverformat='.2f')
                                subplot_adjusted[(i, j)] = True

                    # plot EMG variable
                    elif vartype == 'emg':
                        do_plot = (
                            trial.emg.context_ok(var, cyc.context)
                            and trial.emg.status_ok(var)
                            and cyc in cyclebunch.emg_cycles
                        )
                        # FIXME: maybe annotate disconnected chans
                        # _no_ticks_or_labels(ax)
                        # _axis_annotate(ax, 'disconnected')
                        if do_plot:
                            tracename_emg = 'EMG:' + cyclename

                            t_, y = trial.get_emg_data(var, rms=use_rms, cycle=cyc)
                            t = t_ if normalized else t_ / trial.samplesperframe

                            col = _color_by_params(
                                color_by['emg'], emg_trace_colors, trial, cyc, context
                            )
                            col = merge_color_and_opacity(col, cfg.plot.emg_alpha)
                            lw = (
                                cfg.plot.emg_rms_linewidth
                                if use_rms
                                else cfg.plot.emg_linewidth
                            )
                            line = {'width': lw, 'color': col}

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
                            fig['layout'][yaxis].update(
                                title={
                                    'text': cfg.plot.emg_ylabel,
                                    'font': {'size': label_fontsize},
                                    'standoff': 0,
                                },
                                range=_emg_yscale(emg_mode),
                            )
                            # prevent changes due to legend clicks etc.
                            if normalized:
                                fig['layout'][xaxis].update(range=[0, 100])
                            # rm x tick labels, plot too crowded
                            # fig['layout'][xaxis].update(showticklabels=False)
                            # less decimals on hover label
                            # XXX: this is not working?
                            fig['layout'][yaxis].update(hoverformat='.2f')
                            subplot_adjusted[(i, j)] = True

                    elif vartype == 'unknown':
                        raise GaitDataError('cannot interpret variable %s' % var)

                    else:
                        raise GaitDataError(
                            'plotting not implemented for variable %s' % var
                        )

    # set subplot title font size
    for anno in fig['layout']['annotations']:
        anno['font']['size'] = subtitle_fontsize

    # put x labels on last row only, re-enable tick labels for last row
    inds_last = range((nrows - 1) * ncols, nrows * ncols)
    axes_last = ['xaxis%d' % (ind + 1) for ind in inds_last]
    xlabel = '% of gait cycle' if normalized else 'frame'
    for ax in axes_last:
        fig['layout'][ax].update(
            title={'text': xlabel, 'font': {'size': label_fontsize}},
            showticklabels=True,
        )

    margin = go.layout.Margin(l=50, r=0, b=50, t=50, pad=4)  # NOQA: 741
    legend = dict(font=dict(size=legend_fontsize))
    plotly_layout = go.Layout(
        margin=margin,
        legend=legend,
        font={'size': label_fontsize},
        hovermode='closest',
        title=figtitle,
    )

    fig['layout'].update(plotly_layout)
    return fig
