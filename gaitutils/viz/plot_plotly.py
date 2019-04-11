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
import plotly.tools

from .. import GaitDataError, cfg, layouts, models, normaldata
from .plot_common import _get_legend_entry, _truncate_trialname, _var_title

logger = logging.getLogger(__name__)


def _plotly_fill_between(x, ylow, yhigh, **kwargs):
    """Fill area between ylow and yhigh"""
    x_ = np.concatenate([x, x[::-1]])  # construct a closed curve
    y_ = np.concatenate([yhigh, ylow[::-1]])
    return go.Scatter(x=x_, y=y_, fill='toself', mode='none', hoverinfo='none', **kwargs)


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
                emg_cycles=None, legend_type='full', cycle_linestyles=None,
                supplementary_data=None, maintitle=None):
    """Make a plotly plot of layout, including given trials.

    trials: list of gaitutils.Trial instances
    layout: list of lists defining plot layout (see plot.py)
    model_normaldata: dict of normal data for model variables
    legend_type: 'tag_only' for Eclipse tag, 'name_with_tag' or 'full'
    cycle_linestyles: 'same' for all identical, 'trial' for trial specific
                      style, 'session' for session specific style
    supplementary_data: dict of additional data for each cycle and variable
    """
    global _plot_cache

    if not trials:
        raise GaitDataError('No trials')

    if not isinstance(trials, list):
        trials = [trials]

    if cycle_linestyles is None:
        cycle_linestyles = 'by_session'

    if supplementary_data is None:
        supplementary_data = dict()

    if model_normaldata is None:
        model_normaldata = normaldata.read_all_normaldata()

    nrows, ncols = layouts.check_layout(layout)

    colors_list = plotly.colors.DEFAULT_PLOTLY_COLORS
    colors = cycle(colors_list)
    if len(trials) > len(colors_list):
        logger.warning('Not enough colors for plot')

    session_linestyles = dict()
    linestyles = cycle(['solid', 'dash', 'dot', 'dashdot'])

    allvars = [item for row in layout for item in row]
    titles = [_var_title(var) for var in allvars]
    fig = plotly.tools.make_subplots(rows=nrows, cols=ncols, print_grid=False,
                                     subplot_titles=titles)
    tracegroups = set()
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
                        ntrace = _plotly_fill_between(normalx,
                                                    ndata[:, 0],
                                                    ndata[:, 1],
                                                    fillcolor=cfg.plot_plotly.model_normals_color,
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
                        ntrace = _plotly_fill_between(inds,
                                                    [-1e1]*2,
                                                    [1e1]*2,
                                                    name='EMG norm.',
                                                    legendgroup='EMG norm.',
                                                    showlegend=emg_normaldata_legend,
                                                    fillcolor=cfg.plot_plotly.emg_normals_color,
                                                    line=dict(width=0))  # no border lines                                           
                        fig.append_trace(ntrace, i+1, j+1)
                        emg_normaldata_legend = False

    # plot actual data
    for trial in trials:
        trial_color = next(colors)
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

                    tracegroup = _get_legend_entry(trial, cyc, legend_type)
                    tracename_full = '%s (%s) / %s' % (trial.trialname,
                                                       trial.eclipse_tag,
                                                       cyc.name)
                    # plotly cannot directly handle unicode objects
                    if isinstance(tracegroup, unicode):
                        tracegroup = tracegroup.encode('utf-8')

                    # only show the legend for the first trace in the
                    # tracegroup, so we do not repeat legends.
                    show_legend = tracegroup not in tracegroups

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

                        if do_plot:
                            t, y = trial.get_model_data(var)

                            if cycle_linestyles == 'by_context':
                                # color unique to trial, left side indicated by
                                # dashed line
                                line = {'color': trial_color}
                                if context == 'L':
                                    line['dash'] = 'dash'
                            elif cycle_linestyles == 'by_session':
                                line = {'color':
                                        cfg.plot.model_tracecolors[context]}
                                if trial.sessiondir in session_linestyles:
                                    dash_style = session_linestyles[trial.
                                                                    sessiondir]
                                else:
                                    dash_style = next(linestyles)
                                    session_linestyles[trial.sessiondir] = dash_style
                                line['dash'] = dash_style
                            else:
                                raise ValueError('Invalid cycle style specified')

                            # check whether trace was already created
                            if (trial in _plot_cache and cyc in
                                _plot_cache[trial] and var in
                                _plot_cache[trial][cyc]):
                                        trace = _plot_cache[trial][cyc][var]
                                        # update some of the properties
                                        trace['name'] = tracegroup
                                        trace['legendgroup'] = tracegroup
                                        trace['showlegend'] = show_legend
                            else:  # need to create trace
                                trace = go.Scatter(x=t, y=y, name=tracegroup,
                                                   text=tracename_full,
                                                   legendgroup=tracegroup,
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
                                marker = dict(color='black',
                                              symbol='triangle-up',
                                              size=8)
                                toeoff_marker = go.Scatter(x=t[toeoff:toeoff+1],
                                                           y=y[toeoff:toeoff+1],
                                                           showlegend=False,
                                                           legendgroup=tracegroup,
                                                           hoverinfo='skip',
                                                           mode='markers',
                                                           marker=marker)
                                fig.append_trace(toeoff_marker, i+1, j+1)

                            # add trace to figure
                            fig.append_trace(trace, i+1, j+1)
                            tracegroups.add(tracegroup)

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
                                                        legendgroup=tracegroup,
                                                        hoverinfo='x+y+text',
                                                        showlegend=False)
                                    fig.append_trace(strace, i+1, j+1)

                            # set subplot params if not already done
                            if not fig['layout'][yaxis]['title'].text:
                                #fig['layout'][xaxis].update(showticklabels=False)
                                yunit = mod.units[var]
                                if yunit == 'deg':
                                    yunit = u'\u00B0'  # Unicode degree sign
                                ydesc = [s[:3] for s in mod.ydesc[var]]  # shorten
                                ylabel = (u'%s %s %s' % (ydesc[0], yunit, ydesc[1])).encode('utf-8')
                                fig['layout'][yaxis].update(title=ylabel, titlefont={'size': cfg.plot_plotly.label_fontsize})
                                # less decimals on hover label
                                fig['layout'][yaxis].update(hoverformat='.2f')

                    # plot EMG variable
                    elif (trial.emg.is_channel(var) or var in
                          cfg.emg.channel_labels):
                        do_plot = True
                        # plot only if EMG channel context matches cycle ctxt
                        # FIXME: this assumes that EMG names begin with context
                        if (var[0] != context or not trial.emg.status_ok(var)
                            or cyc not in emg_cycles_):
                            do_plot = False
                            # FIXME: maybe annotate disconnected chans
                            # _no_ticks_or_labels(ax)
                            # _axis_annotate(ax, 'disconnected')
                        if do_plot:
                            logger.debug('plotting %s/%s' % (cyc, var))
                            t_, y = trial.get_emg_data(var)
                            t = (t_ / trial.samplesperframe if not normalized
                                 else t_)
                            line = {'width': 1, 'color': trial_color}
                            if (trial in _plot_cache and cyc in
                                _plot_cache[trial] and var in
                                _plot_cache[trial][cyc]):
                                    #logger.debug('cache hit for: %s / %s / %s' %
                                    #             (trial.trialname, cyc.name, var))
                                    trace = _plot_cache[trial][cyc][var]
                                    trace['name'] = tracegroup
                                    trace['legendgroup'] = tracegroup
                                    trace['showlegend'] = show_legend
                            else:
                                #logger.debug('calling Scatter for: %s / %s / %s' %
                                #             (trial.trialname, cyc.name, var))
                                trace = go.Scatter(x=t,
                                                   y=y*cfg.plot.emg_multiplier,
                                                   name=tracegroup,
                                                   legendgroup=tracegroup,
                                                   showlegend=show_legend,
                                                   line=line)
                                if trial not in _plot_cache:
                                    _plot_cache[trial] = dict()
                                if cyc not in _plot_cache[trial]:
                                    _plot_cache[trial][cyc] = dict()
                                _plot_cache[trial][cyc][var] = trace

                            tracegroups.add(tracegroup)
                            fig.append_trace(trace, i+1, j+1)

                        if not fig['layout'][yaxis]['title'].text:
                            logger.debug('setting EMG title')
                            emg_yrange = np.array([-cfg.plot.emg_yscale, cfg.plot.emg_yscale]) * cfg.plot.emg_multiplier
                            fig['layout'][yaxis].update(title=cfg.plot.emg_ylabel, titlefont={'size': cfg.plot_plotly.label_fontsize},
                                                        range=emg_yrange)
                            # prevent changes due to legend clicks etc.
                            if normalized:
                                fig['layout'][xaxis].update(range=[0, 100])
                            # rm x tick labels, plot too crowded
                            #fig['layout'][xaxis].update(showticklabels=False)

                    else:
                        raise GaitDataError('Unknown variable %s' % var)

    # reduce subplot title font size
    for anno in fig['layout']['annotations']:
        anno['font']['size'] = cfg.plot_plotly.subtitle_fontsize

    # put x labels on last row only, re-enable tick labels for last row
    inds_last = range((nrows-1)*ncols, nrows*ncols)
    axes_last = ['xaxis%d' % (ind+1) for ind in inds_last]
    xlabel = '% of gait cycle' if normalized else 'frame'
    for ax in axes_last:
        fig['layout'][ax].update(title=xlabel,
                                 titlefont={'size': cfg.plot_plotly.label_fontsize},
                                 showticklabels=True)

    margin = go.layout.Margin(l=50, r=0, b=50, t=50, pad=4)  # NOQA: 741
    layout = go.Layout(margin=margin, font={'size': cfg.plot_plotly.label_fontsize},
                       hovermode='closest', title=maintitle)

    fig['layout'].update(layout)
    return fig
