# -*- coding: utf-8 -*-
"""
plotly plotting functions

@author: Jussi (jnu@iki.fi)
"""

from builtins import range
import plotly
import plotly.graph_objs as go
import plotly.tools
import numpy as np
from itertools import cycle
import datetime
import logging

from gaitutils import models, cfg


logger = logging.getLogger(__name__)


def _plotly_fill_between(x, ylow, yhigh, **kwargs):
    """Fill area between ylow and yhigh"""
    x_ = np.concatenate([x, x[::-1]])  # construct a closed curve
    y_ = np.concatenate([yhigh, ylow[::-1]])
    return go.Scatter(x=x_, y=y_, fill='toself', hoverinfo='none', **kwargs)


def _var_title(var):
    """Get proper title for variable"""
    mod = models.model_from_var(var)
    if mod:
        if var in mod.varlabels_noside:
            return mod.varlabels_noside[var]
        elif var in mod.varlabels:
            return mod.varlabels[var]
    elif var in cfg.emg.channel_labels:
        return cfg.emg.channel_labels[var]
    else:
        return ''


def _truncate_trialname(trialname):
    """Remove leading date string from trial names, e.g. 2018_5_12"""
    tn_split = trialname.split('_')
    datetxt = '-'.join(tn_split[:3])
    try:
        datetime.datetime.strptime(datetxt, '%Y-%m-%d')
        return '%s' % '_'.join(tn_split[3:])
    except ValueError:
        return trialname


_plot_cache = dict()


def plot_trials(trials, layout, model_normaldata, legend_type='full',
                trial_linestyles='same'):
    """Make a plotly plot of layout, including given trials.

    trials: list of gaitutils.Trial instances
    layout: list of lists defining plot layout (see plot.py)
    model_normaldata: dict of normal data for model variables
    legend_type: 'tag_only' for Eclipse tag, 'name_with_tag' or 'full'
    trial_linestyles: 'same' for all identical, 'trial' for trial specific
                      style, 'session' for session specific style
    """
    global _plot_cache

    # configurabe opts (here for now)
    label_fontsize = 18  # x, y labels
    subtitle_fontsize = 20  # subplot titles

    nrows = len(layout)
    if nrows == 0:
        raise ValueError('Empty layout')
    ncols = len(layout[0])
    if ncols == 0:
        raise ValueError('Empty layout')

    if len(trials) > len(plotly.colors.DEFAULT_PLOTLY_COLORS):
        logger.warning('Not enough colors for plot')
    colors = cycle(plotly.colors.DEFAULT_PLOTLY_COLORS)

    allvars = [item for row in layout for item in row]
    titles = [_var_title(var) for var in allvars]
    fig = plotly.tools.make_subplots(rows=nrows, cols=ncols,
                                     subplot_titles=titles)
    tracegroups = set()
    model_normaldata_legend = True
    emg_normaldata_legend = True

    session_linestyles = dict()
    dash_styles = cycle(['solid', 'dash', 'dot', 'dashdot'])

    model_cycles_ = cfg.plot.default_model_cycles
    emg_cycles_ = cfg.plot.default_emg_cycles

    for trial in trials:
        trial_color = next(colors)
        model_cycles = trial.get_cycles(model_cycles_)
        emg_cycles = trial.get_cycles(emg_cycles_)

        for cyc in model_cycles + emg_cycles:
            trial.set_norm_cycle(cyc)
            context = cyc.context

            for i, row in enumerate(layout):
                for j, var in enumerate(row):
                    plot_ind = i * ncols + j + 1  # plotly subplot index
                    xaxis = 'xaxis%d' % plot_ind  # name of plotly xaxis
                    yaxis = 'yaxis%d' % plot_ind  # name of plotly yaxis

                    # in legend, traces will be grouped according to tracegroup
                    # (which is also the label)
                    if legend_type == 'name_with_tag':
                        tracegroup = '%s / %s' % (trial.trialname,
                                                  trial.eclipse_tag)
                    elif legend_type == 'short_name_with_tag':
                        tracegroup = '%s / %s' % (_truncate_trialname(trial.trialname),
                                                  trial.eclipse_tag)
                    elif legend_type == 'tag_only':
                        tracegroup = trial.eclipse_tag
                    elif legend_type == 'tag_with_cycle':
                        tracegroup = '%s / %s' % (trial.eclipse_tag,
                                                  cyc.name)
                    elif legend_type == 'full':
                        tracegroup = '%s / %s' % (trial.name_with_description,
                                                  cyc.name)
                    else:
                        raise ValueError('Invalid legend type')

                    # plotly cannot directly handle unicode objects
                    if isinstance(tracegroup, unicode):
                        tracegroup = tracegroup.encode('utf-8')

                    # only show the legend for the first trace in the
                    # tracegroup, so we do not repeat legends
                    show_legend = tracegroup not in tracegroups

                    mod = models.model_from_var(var)
                    if mod:
                        do_plot = True  # FIXME: control flow is clumsy here

                        if var in mod.varnames_noside:
                            var = context + var

                        if cyc not in model_cycles:
                            do_plot = False

                        if mod.is_kinetic_var(var) and not cyc.on_forceplate:
                            do_plot = False

                        # plot model normal data first so that its z order
                        # is lowest (otherwise normaldata will mask other
                        # traces on hover)
                        if trial == trials[0] and context == 'R':
                            if var[0].upper() in ['L', 'R']:
                                nvar = var[1:]
                            if model_normaldata and nvar in model_normaldata:
                                key = nvar
                            else:
                                key = None
                            ndata = (model_normaldata[key] if key in
                                     model_normaldata else None)
                            if ndata is not None:
                                # FIXME: hardcoded color
                                normalx = np.linspace(0, 100, ndata.shape[0])
                                ntrace = _plotly_fill_between(normalx,
                                                              ndata[:, 0],
                                                              ndata[:, 1],
                                                              fillcolor='rgba(100, 100, 100, 0.1)',
                                                              name='Norm.',
                                                              legendgroup='Norm.',
                                                              showlegend=model_normaldata_legend,
                                                              line=dict(width=0))  # no border lines
                                fig.append_trace(ntrace, i+1, j+1)
                                # add to legend only once
                                model_normaldata_legend = False

                        if do_plot:
                            t, y = trial[var]

                            if trial_linestyles == 'trial':
                                # trial specific color, left side dashed
                                line = {'color': trial_color}
                                if context == 'L':
                                    line['dash'] = 'dash'
                            elif trial_linestyles == 'same':
                                # identical color for all trials
                                line = {'color':
                                        cfg.plot.model_tracecolors[context]}
                            elif trial_linestyles == 'session':
                                # session specific line style
                                line = {'color':
                                        cfg.plot.model_tracecolors[context]}
                                if trial.sessiondir in session_linestyles:
                                    dash_style = session_linestyles[trial.
                                                                    sessiondir]
                                else:
                                    dash_style = next(dash_styles)
                                    session_linestyles[trial.sessiondir] = dash_style
                                line['dash'] = dash_style

                            if (trial in _plot_cache and cyc in
                                _plot_cache[trial] and var in
                                _plot_cache[trial][cyc]):
                                        #logger.debug('cache hit for: %s / %s / %s' %
                                        #             (trial.trialname, cyc.name, var))
                                        trace = _plot_cache[trial][cyc][var]
                                        toeoff_marker = _plot_cache[trial][cyc][var+'_toeoff']
                                        trace['name'] = tracegroup
                                        trace['legendgroup'] = tracegroup
                                        trace['showlegend'] = show_legend
                            else:
                                #logger.debug('calling Scatter for: %s / %s / %s' %
                                #             (trial.trialname, cyc.name, var))
                                trace = go.Scatter(x=t, y=y, name=tracegroup,
                                                   legendgroup=tracegroup,
                                                   showlegend=show_legend,
                                                   line=line)
                                marker = dict(color='black',
                                              symbol='triangle-up',
                                              size=8)
                                toeoff = int(cyc.toeoffn)
                                #logger.debug('calling Scatter for: %s / %s / %s' %
                                #             (trial.trialname, cyc.name, var))
                                toeoff_marker = go.Scatter(x=t[toeoff:toeoff+1],
                                                           y=y[toeoff:toeoff+1],
                                                           showlegend=False,
                                                           hoverinfo='skip',
                                                           mode='markers',
                                                           marker=marker)

                                if trial not in _plot_cache:
                                    _plot_cache[trial] = dict()
                                if cyc not in _plot_cache[trial]:
                                    _plot_cache[trial][cyc] = dict()
                                _plot_cache[trial][cyc][var] = trace
                                _plot_cache[trial][cyc][var+'_toeoff'] = toeoff_marker

                            tracegroups.add(tracegroup)
                            fig.append_trace(trace, i+1, j+1)
                            fig.append_trace(toeoff_marker, i+1, j+1)

                            # rm x tick labels, plot too crowded
                            fig['layout'][xaxis].update(showticklabels=False)
                            # LaTeX does not render, so rm units from ylabel
                            ylabel = ' '.join(mod.ylabels[var].split(' ')[k]
                                              for k in [0, -1])
                            fig['layout'][yaxis].update(title=ylabel, titlefont={'size': label_fontsize})
                            # less decimals on hover label
                            fig['layout'][yaxis].update(hoverformat='.2f')

                    # plot EMG variable
                    elif (trial.emg.is_channel(var) or var in
                          cfg.emg.channel_labels):
                        do_plot = True
                        if cyc not in emg_cycles:
                            do_plot = False
                        # plot only if EMG channel context matches cycle ctxt
                        # FIXME: this assumes that EMG names begin with context
                        if var[0] != context:
                            do_plot = False
                        t, y = trial[var]
                        if not trial.emg.status_ok(var):
                            do_plot = False
                            # FIXME: maybe annotate disconnected chans
                            # _no_ticks_or_labels(ax)
                            # _axis_annotate(ax, 'disconnected')
                        if do_plot:
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

                        # last trace was plotted
                        if trial == trials[-1] and context == 'L':
                            # plot EMG normal bars
                            if var in cfg.emg.channel_normaldata:
                                emgbar_ind = cfg.emg.channel_normaldata[var]
                                for inds in emgbar_ind:
                                    # FIXME: hardcoded color
                                    # NOTE: using big values (>~1e3) for the normal bar height triggers a plotly bug
                                    # and screws up the normal bars (https://github.com/plotly/plotly.py/issues/1008)
                                    ntrace = _plotly_fill_between(inds, [-1e1]*2, [1e1]*2,  # simulate x range fill by high y values
                                                                  name='EMG norm.',
                                                                  legendgroup='EMG norm.',
                                                                  showlegend=emg_normaldata_legend,
                                                                  fillcolor='rgba(255, 0, 0, 0.1)',
                                                                  line=dict(width=0))  # no border lines                                                               
                                    fig.append_trace(ntrace, i+1, j+1)
                                    emg_normaldata_legend = False  # add to legend only once
                        
                            emg_yrange = np.array([-cfg.plot.emg_yscale, cfg.plot.emg_yscale]) * cfg.plot.emg_multiplier
                            fig['layout'][yaxis].update(title=cfg.plot.emg_ylabel, titlefont={'size': label_fontsize},
                                                        range=emg_yrange)  # FIXME: cfg
                            # prevent changes due to legend clicks etc.
                            fig['layout'][xaxis].update(range=[0, 100])
                            # rm x tick labels, plot too crowded
                            fig['layout'][xaxis].update(showticklabels=False)

                    elif var is None:
                        continue

                    elif 'legend' in var:  # 'legend' is for mpl plotter only
                        continue

                    else:
                        raise Exception('Unknown variable %s' % var)

    # reduce subplot title font size
    for anno in fig['layout']['annotations']:
        anno['font']['size'] = subtitle_fontsize

    # put x labels on last row only, re-enable tick labels for last row
    inds_last = range((nrows-1)*ncols, nrows*ncols)
    axes_last = ['xaxis%d' % (ind+1) for ind in inds_last]
    for ax in axes_last:
        fig['layout'][ax].update(title='% of gait cycle',
                                 titlefont={'size': label_fontsize},
                                 showticklabels=True)

    margin = go.layout.Margin(l=50, r=0, b=50, t=50, pad=4)  # NOQA: 741
    layout = go.Layout(margin=margin, font={'size': label_fontsize},
                       hovermode='closest')

    fig['layout'].update(layout)
    return fig
