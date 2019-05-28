# -*- coding: utf-8 -*-
"""
plotly based plotting functions

@author: Jussi (jnu@iki.fi)
"""

import logging
from builtins import range
from itertools import cycle

import numpy as np
import plotly
import plotly.graph_objs as go
from plotly.matplotlylib.mpltools import merge_color_and_opacity
import plotly.tools

from .. import GaitDataError, cfg, layouts, models, normaldata, numutils
from ..stats import AvgTrial
from .plot_common import (_get_cycle_name, _var_title, IteratorMapper,
                          _style_mpl_to_plotly,
                          _handle_style_and_color_args)


logger = logging.getLogger(__name__)


def _plot_vels(vels, labels):
    """Plot trial velocities as a stem plot"""
    trace = go.Scatter(y=vels, x=labels, mode='markers')
    layout = go.Layout(xaxis=dict(title='Trial', automargin=True),
                       yaxis=dict(title='Velocity (m/s)'))
    return dict(data=[trace], layout=layout)


def _plot_timedep_vels(vels, labels):
    """Plot trial time-dependent velocities"""
    traces = list()
    for vel, label in zip(vels, labels):
        trace = go.Scatter(y=vel, text=label, name=label, hoverinfo='x+y+text')
        traces.append(trace)
    # FIXME: labels get truncated, not fixed by automargin
    layout = go.Layout(xaxis=dict(title='% of trial', automargin=True),
                       yaxis=dict(title='Velocity (m/s)'))
    return dict(data=traces, layout=layout)


def _plotly_fill_between(x, ylow, yhigh, **kwargs):
    """Fill area between ylow and yhigh"""
    x_ = np.concatenate([x, x[::-1]])  # construct a closed curve
    y_ = np.concatenate([yhigh, ylow[::-1]])
    return go.Scatter(x=x_, y=y_, fill='toself', mode='none',
                      hoverinfo='none', **kwargs)


def plot_trials_browser(trials, layout, **kwargs):
    """ Convenience plotter, uses plotly.offline to plot directly to browser"""
    fig = plot_trials(trials, layout, **kwargs)
    plotly.offline.plot(fig)


def _get_plotly_axis_labels(i, j, ncols):
    """Gets plotly axis labels from subplot indices i, j"""
    plot_ind = i * ncols + j + 1  # plotly subplot index
    return 'xaxis%d' % plot_ind, 'yaxis%d' % plot_ind


_plot_cache = dict()  # global for plot_trials


def plot_trials(trials, layout, model_normaldata=None, model_cycles=None,
                emg_cycles=None, emg_mode=None, legend_type=None, style_by=None,
                color_by=None, supplementary_data=None,
                legend=True, figtitle=None, big_fonts=False):
    """Make a plotly plot of layout, including given trials.
    FIXME: legend is currently ignored
    trials: list of gaitutils.Trial instances
    layout: list of lists defining plot layout (see plot.py)
    model_normaldata: dict of normal data for model variables
    legend_type: 
    cycle_linestyles: 
    supplementary_data: dict of additional data for each cycle and variable
    """
    global _plot_cache

    if not trials:
        raise GaitDataError('No trials')

    if not isinstance(trials, list):
        trials = [trials]

    style_by, color_by = _handle_style_and_color_args(style_by, color_by)

    logger.debug(style_by)
    logger.debug(color_by)    

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

    allvars = [item for row in layout for item in row]
    titles = [_var_title(var) for var in allvars]
    fig = plotly.tools.make_subplots(rows=nrows, cols=ncols, print_grid=False,
                                     subplot_titles=titles)
    legendgroups = set()
    model_normaldata_legend = True
    emg_normaldata_legend = True

    model_cycles = (cfg.plot.default_model_cycles if model_cycles is None
                    else model_cycles)
    emg_cycles = (cfg.plot.default_emg_cycles if emg_cycles is None else
                  emg_cycles)
    if model_cycles == 'unnormalized' or emg_cycles == 'unnormalized':
        normalized = False
        model_cycles = emg_cycles = 'unnormalized'
    else:
        normalized = True

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
                mod = models.model_from_var(var)
                if mod and model_normaldata:
                    nvar = var if var in mod.varlabels_noside else var[1:]                    
                    key = nvar if nvar in model_normaldata else None
                    ndata = (model_normaldata[key] if key in
                             model_normaldata else None)
                    if ndata is not None:
                        normalx = np.linspace(0, 100, ndata.shape[0])
                        fillcolor = merge_color_and_opacity(cfg.plot.model_normals_color, cfg.plot.model_normals_alpha)
                        ntrace = _plotly_fill_between(normalx,
                                                    ndata[:, 0],
                                                    ndata[:, 1],
                                                    fillcolor=fillcolor,
                                                    name='Norm.',
                                                    legendgroup='Norm.',
                                                    showlegend=model_normaldata_legend,
                                                    line=dict(width=0))  # no border lines
                        fig.append_trace(ntrace, i+1, j+1)
                        model_normaldata_legend = False

                elif var in cfg.emg.channel_labels and var in cfg.emg.channel_normaldata:
                    emgbar_ind = cfg.emg.channel_normaldata[var]
                    for inds in emgbar_ind:
                        # simulate x range fill by high y values
                        # NOTE: using big values (>~1e3) for the normal bar height triggers a plotly bug
                        # and screws up the normal bars (https://github.com/plotly/plotly.py/issues/1008)
                        fillcolor = merge_color_and_opacity(cfg.plot.emg_normals_color, cfg.plot.emg_normals_alpha)
                        ntrace = _plotly_fill_between(inds,
                                                    [-1e1]*2,
                                                    [1e1]*2,
                                                    name='EMG norm.',
                                                    legendgroup='EMG norm.',
                                                    showlegend=emg_normaldata_legend,
                                                    fillcolor=fillcolor,
                                                    line=dict(width=0))  # no border lines                                           
                        fig.append_trace(ntrace, i+1, j+1)
                        emg_normaldata_legend = False

    # plot actual data
    for trial in trials:

        # these are the actual Gaitcycle instances
        model_cycles_ = trial.get_cycles(model_cycles)
        emg_cycles_ = trial.get_cycles(emg_cycles)
        allcycles = list(set.union(set(model_cycles_), set(emg_cycles_)))
        if not allcycles:
            logger.debug('trial %s has no cycles of specified type' %
                         trial.trialname)

        logger.debug('plotting total of %d cycles for %s (%d model, %d EMG)'
                     % (len(allcycles), trial.trialname, len(model_cycles_),
                        len(emg_cycles_)))

        for cyc_ind, cyc in enumerate(allcycles):

            trial.set_norm_cycle(cyc)
            context = cyc.context

            for i, row in enumerate(layout):
                for j, var in enumerate(row):

                    if var is None:
                        continue

                    xaxis, yaxis = _get_plotly_axis_labels(i, j, ncols)
                    tracename = _get_cycle_name(trial, cyc, 
                                                name_type=legend_type)
                    cyclename_full = _get_cycle_name(trial, cyc,
                                                     name_type='full')
                    # plotly cannot directly handle unicode objects
                    if isinstance(tracename, unicode):
                        tracename = tracename.encode('utf-8')

                    # tracename determines the legend group
                    # only create a legend entry for the first trace in the
                    # tracegroup, so we do not repeat legends
                    show_legend = tracename not in legendgroups

                    mod = models.model_from_var(var)
                    if mod:
                        do_plot = cyc in model_cycles_

                        if var in mod.varnames_noside:
                            # var context was unspecified, so choose it
                            # according to cycle context
                            var = context + var
                        elif var[0] != context:
                            # var context was specified and does not match cycle
                            do_plot = False

                        # kinetic var cycles are required to have valid
                        # forceplate data
                        if (normalized and mod.is_kinetic_var(var) and
                           not cyc.on_forceplate):
                            do_plot = False

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
                            elif style_by['model'] is None:
                                sty = '-'
                            sty = _style_mpl_to_plotly(sty)

                            if color_by['model'] == 'context':
                                col = cfg.plot.context_colors[context]
                            elif color_by['model'] == 'session':
                                col = trace_colors.get_prop(trial.sessiondir)
                            elif color_by['model'] == 'trial':
                                col = trace_colors.get_prop(trial)
                            elif color_by['model'] == 'cycle':
                                col = trace_colors.get_prop(cyc)
                            elif color_by['model'] is None:
                                col = '#000000'
                            line = dict(width=cfg.plot.model_linewidth,
                                        dash=sty, color=col)

                            # check whether trace was already created
                            if (trial in _plot_cache and cyc in
                                _plot_cache[trial] and var in
                                _plot_cache[trial][cyc]):
                                        trace = _plot_cache[trial][cyc][var]
                                        # update some of the properties
                                        trace['name'] = tracename
                                        trace['legendgroup'] = tracename
                                        trace['showlegend'] = show_legend
                            else:  # need to create trace
                                trace = go.Scatter(x=t, y=y, name=tracename,
                                                   text=cyclename_full,
                                                   legendgroup=tracename,
                                                   showlegend=show_legend,
                                                   hoverlabel=dict(namelength=-1),
                                                   hoverinfo='x+y+text',
                                                   line=line)
                                # add trace to cache
                                if trial not in _plot_cache:
                                    _plot_cache[trial] = dict()
                                if cyc not in _plot_cache[trial]:
                                    _plot_cache[trial][cyc] = dict()
                                _plot_cache[trial][cyc][var] = trace

                            # add toeoff marker
                            if cyc.toeoffn is not None:
                                toeoff = int(cyc.toeoffn)
                                marker = dict(color=col,
                                              symbol='triangle-up',
                                              size=8)
                                toeoff_marker = go.Scatter(x=t[toeoff:toeoff+1],
                                                           y=y[toeoff:toeoff+1],
                                                           showlegend=False,
                                                           legendgroup=tracename,
                                                           hoverinfo='skip',
                                                           mode='markers',
                                                           marker=marker)
                                fig.append_trace(toeoff_marker, i+1, j+1)

                            # add trace to figure
                            fig.append_trace(trace, i+1, j+1)
                            legendgroups.add(tracename)

                            # each cycle gets its own stddev plot
                            if isinstance(trial, AvgTrial):
                                model_stddev = trial.stddev_data
                                if (model_stddev is not None and normalized and
                                   y is not None and var in model_stddev):
                                    sdata = model_stddev[var]
                                    stdx = np.linspace(0, 100, sdata.shape[0])
                                    fillcolor_ = cfg.plot.model_stddev_colors[cyc.context]
                                    fillcolor = merge_color_and_opacity(fillcolor_, cfg.plot.model_stddev_alpha)
                                    ntrace = _plotly_fill_between(stdx,
                                                                y-sdata,
                                                                y+sdata,
                                                                fillcolor=fillcolor,
                                                                name='Stddev, %s' % tracename,
                                                                legendgroup='Stddev, %s' % tracename,
                                                                showlegend=show_legend,
                                                                line=dict(width=0))  # no border lines
                                    fig.append_trace(ntrace, i+1, j+1)

                            # add supplementary data
                            if cyc in supplementary_data:
                                supdata = supplementary_data[cyc]
                                if var in supdata:
                                    logger.debug('plotting supplementary data '
                                                 'for var %s' % var)
                                    t_sup = supdata[var]['t']
                                    data_sup = supdata[var]['data']
                                    label_sup = supdata[var]['label']
                                    strace = go.Scatter(x=t_sup, y=data_sup,
                                                        name=label_sup,
                                                        text=label_sup,
                                                        line=line,
                                                        legendgroup=tracename,
                                                        hoverinfo='x+y+text',
                                                        showlegend=False)
                                    fig.append_trace(strace, i+1, j+1)
                                    legendgroups.add(tracename)

                            # adjust subplot once
                            if cyc_ind == 0:
                                #fig['layout'][xaxis].update(showticklabels=False)
                                yunit = mod.units[var]
                                if yunit == 'deg':
                                    yunit = u'\u00B0'  # Unicode degree sign
                                ydesc = [s[:3] for s in mod.ydesc[var]]  # shorten
                                ylabel = (u'%s %s %s' % (ydesc[0], yunit, ydesc[1])).encode('utf-8')
                                fig['layout'][yaxis].update(title={'text': ylabel, 'font': {'size': label_fontsize}})
                                # less decimals on hover label
                                fig['layout'][yaxis].update(hoverformat='.2f')

                    # plot EMG variable
                    elif (trial.emg.is_channel(var) or var in
                          cfg.emg.channel_labels):
                        # plot only if EMG channel context matches cycle ctxt
                        # FIXME: this assumes that EMG names begin with context
                        do_plot = (var[0] == context and trial.emg.status_ok(var)
                                   and cyc in emg_cycles_)
                        # FIXME: maybe annotate disconnected chans
                        # _no_ticks_or_labels(ax)
                        # _axis_annotate(ax, 'disconnected')
                        if do_plot:
                            tracename_emg = 'EMG:' + tracename

                            t_, y_ = trial.get_emg_data(var)
                            t = (t_ / trial.samplesperframe if not normalized
                                 else t_)
                            y = (numutils.rms(y_, cfg.emg.rms_win)
                                 if emg_mode == 'rms' else y_)

                            if color_by['emg'] == 'session':
                                col = emg_trace_colors.get_prop(trial.sessiondir)
                            elif color_by['emg'] == 'trial':
                                col = emg_trace_colors.get_prop(trial)
                            elif color_by['emg'] == 'cycle':
                                col = emg_trace_colors.get_prop(cyc)
                            elif color_by['emg'] is None:
                                col = '#000000'

                            col = merge_color_and_opacity(col, cfg.plot.emg_alpha)
                            lw = cfg.plot.emg_rms_linewidth if emg_mode == 'rms' else cfg.plot.emg_linewidth
                            line = {'width': lw,
                                    'color': col}

                            # the tracename_emg legend group does not actually exist
                            # in plotly, it's only used to keep track of whether the
                            # EMG trace legend was already shown. In the legend,
                            # EMG traces get grouped with model traces of the
                            # same cycle.
                            show_legend = tracename_emg not in legendgroups

                            if (trial in _plot_cache and cyc in
                                _plot_cache[trial] and var in
                                _plot_cache[trial][cyc]):
                                    trace = _plot_cache[trial][cyc][var]
                                    trace['name'] = tracename_emg
                                    trace['legendgroup'] = tracename
                                    trace['showlegend'] = show_legend
                            else:
                                trace = go.Scatter(x=t,
                                                   y=y*cfg.plot.emg_multiplier,
                                                   name=tracename_emg,
                                                   legendgroup=tracename,
                                                   showlegend=show_legend,
                                                   line=line)
                                if trial not in _plot_cache:
                                    _plot_cache[trial] = dict()
                                if cyc not in _plot_cache[trial]:
                                    _plot_cache[trial][cyc] = dict()
                                _plot_cache[trial][cyc][var] = trace

                            legendgroups.add(tracename_emg)
                            fig.append_trace(trace, i+1, j+1)

                        # adjust subplot once
                        if cyc_ind == 0:
                            emg_yrange = np.array([-cfg.plot.emg_yscale, cfg.plot.emg_yscale]) * cfg.plot.emg_multiplier
                            fig['layout'][yaxis].update(title={'text': cfg.plot.emg_ylabel,
                                                               'font': {'size': label_fontsize}},
                                                        range=emg_yrange)
                            # prevent changes due to legend clicks etc.
                            if normalized:
                                fig['layout'][xaxis].update(range=[0, 100])
                            # rm x tick labels, plot too crowded
                            #fig['layout'][xaxis].update(showticklabels=False)

                    else:
                        raise GaitDataError('Unknown variable %s' % var)

    # set subplot title font size
    for anno in fig['layout']['annotations']:
        anno['font']['size'] = subtitle_fontsize

    # put x labels on last row only, re-enable tick labels for last row
    inds_last = range((nrows-1)*ncols, nrows*ncols)
    axes_last = ['xaxis%d' % (ind+1) for ind in inds_last]
    xlabel = '% of gait cycle' if normalized else 'frame'
    for ax in axes_last:
        fig['layout'][ax].update(title={'text': xlabel,
                                        'font': {'size': label_fontsize}},
                                 showticklabels=True)

    margin = go.layout.Margin(l=50, r=0, b=50, t=50, pad=4)  # NOQA: 741
    legend = dict(font=dict(size=legend_fontsize))
    plotly_layout = go.Layout(margin=margin,
                              legend=legend,
                              font={'size': label_fontsize},
                              hovermode='closest', title=figtitle)

    fig['layout'].update(plotly_layout)
    return fig
