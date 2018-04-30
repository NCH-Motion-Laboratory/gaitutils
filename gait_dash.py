#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
gaitutils + dash report proof of concept
(choosable) gait plot + videos


TODO next POC (live test):

    report launcher
        -qt session(s) selector
        -check session validity
        -preconv videos

    comparison / single


TODO later:

    fix subplot title fontsize
        -hardcoded to 16pt, see https://github.com/plotly/plotly.py/issues/985

    rm dead emg channels (see emg_consistency)

    annotate disconnected EMG
    
    color name conversions (from cfg)


NOTES:

    -firefox html5 player:
        can change playback speed
        some limited kb controls
        browsing back/forth worse than chrome
    -IE not working at all
    -if using default server, need recent enough werkzeug (>=0.12.2?) otherwise
    video not seekable due to HTTP 206 not implemented
    -cannot choose dir using dcc.Upload component
    -should not use global vars (at least not modify) see:
    https://dash.plot.ly/sharing-data-between-callbacks
    -problems w/ server - see:
    https://stackoverflow.com/questions/40247025/flask-socket-error-errno-10053-an-established-connection-was-aborted-by-the
    -dcc.Dropdown dicts need to have str values

@author: jussi
"""

# -*- coding: utf-8 -*-
from __future__ import print_function
import os.path as op
import logging
import dash
import dash_core_components as dcc
import dash_html_components as html
from dash.dependencies import Input, Output
import plotly.tools
import base64
import io
import sys
import flask
import plotly
import plotly.plotly as py
import plotly.graph_objs as go
import numpy as np
from itertools import cycle

import gaitutils
from gaitutils.nexus import find_tagged
from gaitutils import cfg, models, normaldata

logger = logging.getLogger(__name__)


def _video_element_from_base64(data):
    """Create dash Video element from given base64 data"""
    return html.Video(src='data:video/ogg;base64,%s' % data, controls=True,
                      loop=True, width='100%')


def _video_element_from_url(url):
    """Create dash Video element from given url"""
    return html.Video(src='%s' % url, controls=True, loop=True, width='100%')


def _trial_videos(trial):
    """(converted) videos from given trial"""
    vids_conv = gaitutils.report.convert_videos(trial.video_files)
    return vids_conv


def _static_image_element(data):
    """Create static image element from given base64 data"""
    return html.Img(src='data:image/png;base64,%s' % data, width='100%')


def _make_dropdown_lists(options):
    """This takes a list of label/value dicts (with arbitrary type values)
    and returns list and dict. Needed since dcc.Dropdown can only take str
    values. identity is fed to dcc.Dropdown() and mapper is used for getting
    the actual values at the callback."""
    identity = list()
    mapper = dict()
    for option in options:
        identity.append({'label': option['label'], 'value': option['label']})
        mapper[option['label']] = option['value']
    return identity, mapper


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


def _plotly_fill_between(x, ylow, yhigh, **kwargs):
    """Fill area between ylow and yhigh"""
    x_ = np.concatenate([x, x[::-1]])  # construct a closed curve
    y_ = np.concatenate([yhigh, ylow[::-1]])
    return go.Scatter(x=x_, y=y_, fill='toself', **kwargs)



# FIXME: global
graphind = 0

model_normaldata = dict()
for fn in cfg.general.normaldata_files:
    ndata = normaldata.read_normaldata(fn)
    model_normaldata.update(ndata)

def _plot_trials(trials, layout):
    """Make a plotly plot of modelvar, including given trials"""

    # configurabe opts (here for now)
    trial_specific_colors = False
    label_fontsize = 12

    nrows = len(layout)
    ncols = len(layout[0])

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

    for trial in trials:
        trial_color = colors.next()

        for context in ['R', 'L']:
            # FIXME: hardcoded to 1st cycle
            cycle_ind = 1
            cyc = trial.get_cycle(context, cycle_ind)
            trial.set_norm_cycle(cyc)

            for i, row in enumerate(layout):
                for j, var in enumerate(row):
                    plot_ind = i * ncols + j + 1  # plotly subplot index
                    xaxis = 'xaxis%d' % plot_ind  # name of plotly xaxis
                    yaxis = 'yaxis%d' % plot_ind  # name of plotly yaxis
                    # in legend, traces will be grouped according to tracegroup (which is also the label)
                    # tracegroup = '%s / %s' % (trial.name_with_description, cycle_desc[context])  # include cycle
                    # tracegroup = '%s' % (trial.name_with_description)  # no cycle info (group both cycles from trial)
                    tracegroup = trial.eclipse_data['NOTES']  # short one
                    # only show the legend for the first trace in the tracegroup, so we do not repeat legends
                    show_legend = tracegroup not in tracegroups

                    mod = models.model_from_var(var)
                    if mod:  # plot model variable
                        do_plot = True
                        if var in mod.varnames_noside:
                            var = context + var
                        # FIXME: configurable? skip kinetic for no context

                        if mod.is_kinetic_var(var):
                            if var[0] != context:
                                do_plot = False

                        if do_plot:
                            t, y = trial[var]

                            if trial_specific_colors:
                                line = {'color': trial_color}
                                if context == 'L':
                                    line['dash'] = 'dash'
                            else:
                                line = {'color':
                                        cfg.plot.model_tracecolors[context]}

                            trace = go.Scatter(x=t, y=y, name=tracegroup,
                                               legendgroup=tracegroup,
                                               showlegend=show_legend,
                                               line=line)

                            tracegroups.add(tracegroup)
                            fig.append_trace(trace, i+1, j+1)

                        # last model trace was plotted
                        # FIXME: is this logic also working for EMG?
                        if trial == trials[-1] and context == 'L':
                            # plot model normal data
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
                                ntrace = _plotly_fill_between(normalx, ndata[:, 0],
                                                              ndata[:, 1], fillcolor='rgba(100, 100, 100, 0.3)',
                                                              name='Norm.',
                                                              legendgroup='Norm.',
                                                              showlegend=model_normaldata_legend,
                                                              line=go.Line(color='transparent'))
                                fig.append_trace(ntrace, i+1, j+1)
                                model_normaldata_legend = False  # add to legend only once

                            # LaTeX does not render, so remove units from ylabel
                            ylabel = ' '.join(mod.ylabels[var].split(' ')[k]
                                              for k in [0, -1])
                            fig['layout'][yaxis].update(title=ylabel, titlefont={'size': label_fontsize})
                                                        
                    # plot EMG variable
                    elif trial.emg.is_channel(var) or var in cfg.emg.channel_labels:
                        do_plot = True
                        # EMG channel context matches cycle context
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
                            y *= 1e3  # plot mV
                            trace = go.Scatter(x=t, y=y, name=tracegroup,
                                               legendgroup=tracegroup,
                                               showlegend=show_legend,
                                               line=line)
                            tracegroups.add(tracegroup)
                            fig.append_trace(trace, i+1, j+1)

                        # last trace was plotted
                        if trial == trials[-1] and context == 'L':
                            # plot EMG normal bars
                            if var in cfg.emg.channel_normaldata:
                                emgbar_ind = cfg.emg.channel_normaldata[var]
                                for inds in emgbar_ind:
                                    # FIXME: hardcoded color
                                    ntrace = _plotly_fill_between(inds, [-1e10]*2, [1e10]*2,  # simulate x range fill by high y values
                                                                  name='EMG norm.',
                                                                  legendgroup='EMG norm.',
                                                                  showlegend=emg_normaldata_legend,
                                                                  fillcolor='rgba(255, 0, 0, 0.3)',
                                                                  line=go.Line(color='transparent'))                                                                  
                                    fig.append_trace(ntrace, i+1, j+1)
                                    emg_normaldata_legend = False  # add to legend only once
                        
                            emg_yrange = np.array([-cfg.plot.emg_yscale, cfg.plot.emg_yscale]) * cfg.plot.emg_multiplier
                            fig['layout'][yaxis].update(title=cfg.plot.emg_ylabel, titlefont={'size': label_fontsize},
                                                        range=emg_yrange)  # FIXME: cfg
                            fig['layout'][xaxis].update(range=[0, 100])  # prevent changes due to legend clicks etc.

                    elif var is None:
                        continue

                    elif 'legend' in var:  # for the mpl plotter only
                        continue

                    else:
                        raise Exception('Unknown variable %s' % var)

    # put x labels on last row only
    inds_last = range((nrows-1)*ncols, nrows*ncols)
    axes_last = ['xaxis%d' % (ind+1) for ind in inds_last]
    for ax in axes_last:
        fig['layout'][ax].update(title='% of gait cycle',
                                 titlefont={'size': label_fontsize})

    margin = go.Margin(l=50, r=0, b=50, t=50, pad=4)
    layout = go.Layout(legend=dict(x=100, y=.5), margin=margin,
                       font={'size': label_fontsize})

    fig['layout'].update(layout)
    return fig

#session = "C:/Users/hus20664877/Desktop/Vicon/vicon_data/test/Verrokki10v_OK/2015_10_12_boy10v_OK"
#session = "C:/Users/hus20664877/Desktop/Vicon/vicon_data/problem_cases/2018_3_12_seur_RH"
session = "C:/Users/hus20664877/Desktop/Vicon/vicon_data/problem_cases/2018_3_12_seur_tuet_RH"
c3ds = find_tagged(sessionpath=session)
trials_ = [gaitutils.Trial(c3d) for c3d in c3ds]
trials_di = {tr.trialname: tr for tr in trials_}

# build the dcc.Dropdown options list for the trials
trials_dd = list()
for tr in trials_:
    trials_dd.append({'label': tr.name_with_description,
                      'value': tr.trialname})

# template of layout names -> layouts for dropdown
_dd_opts_multi = [
                  {'label': 'Kinematics', 'value': cfg.layouts.lb_kinematics},
                  {'label': 'Kinetics', 'value': cfg.layouts.lb_kinetics},
                  {'label': 'EMG', 'value': cfg.layouts.std_emg[2:]},  # FIXME: hack to show lower body EMGs only
                  {'label': 'Kinetics-EMG left', 'value': cfg.layouts.lb_kinetics_emg_l},
                  {'label': 'Kinetics-EMG right', 'value': cfg.layouts.lb_kinetics_emg_r},
                 ]

# pick desired single variables from model and append
singlevars = [{'label': varlabel, 'value': [[var]]} for var, varlabel in
              models.pig_lowerbody.varlabels_noside.items()]
singlevars = sorted(singlevars, key=lambda it: it['label'])
_dd_opts_multi.extend(singlevars)

# precreate graphs
dd_opts_multi_upper = list()
dd_opts_multi_lower = list()
for k, di in enumerate(_dd_opts_multi):
    label = di['label']
    layout = di['value']
    logger.debug('creating %s' % label)
    fig_ = _plot_trials(trials_, layout)
    # need to create dcc.Graphs with unique ids for upper/lower panel(?)
    graph_upper = dcc.Graph(figure=fig_, id='gaitgraph%d' % k)
    dd_opts_multi_upper.append({'label': label, 'value': graph_upper})
    graph_lower = dcc.Graph(figure=fig_, id='gaitgraph%d'
                            % (len(_dd_opts_multi)+k))
    dd_opts_multi_lower.append({'label': label, 'value': graph_lower})

opts_multi, mapper_multi_upper = _make_dropdown_lists(dd_opts_multi_upper)
opts_multi, mapper_multi_lower = _make_dropdown_lists(dd_opts_multi_lower)

# create the app
app = dash.Dash()
app.layout = html.Div([

    html.Div([
        html.Div([

                dcc.Dropdown(id='dd-vars-upper-multi', clearable=False,
                             options=opts_multi,
                             value=opts_multi[0]['value']),

                html.Div(id='div-upper'),

                dcc.Dropdown(id='dd-vars-lower-multi', clearable=False,
                             options=opts_multi,
                             value=opts_multi[0]['value']),

                html.Div(id='div-lower')


        ], className='eight columns'),

        html.Div([

                dcc.Dropdown(id='dd-videos', clearable=False,
                             options=trials_dd, value=trials_dd[0]['value']),

                html.Div(id='videos'),
            ], className='four columns'),

    ], className='row')

])


@app.callback(
        Output(component_id='div-upper', component_property='children'),
        [Input(component_id='dd-vars-upper-multi', component_property='value')]
    )
def update_contents_upper_multi(sel_var):
    return mapper_multi_upper[sel_var]


@app.callback(
        Output(component_id='div-lower', component_property='children'),
        [Input(component_id='dd-vars-lower-multi', component_property='value')]
    )
def update_contents_lower_multi(sel_var):
    return mapper_multi_lower[sel_var]


@app.callback(
        Output(component_id='videos', component_property='children'),
        [Input(component_id='dd-videos', component_property='value')]
    )
def update_videos(trial_lbl):
    trial = trials_di[trial_lbl]
    vid_urls = ['/static/%s' % op.split(fn)[1] for fn in _trial_videos(trial)]
    vid_elements = [_video_element_from_url(url) for url in vid_urls]
    return vid_elements or 'No videos'


# add a static route to serve session data. be careful outside firewalls
@app.server.route('/static/<resource>')
def serve_file(resource):
    return flask.send_from_directory(session, resource)


# the 12-column external css
# FIXME: local copy?
app.css.append_css({
    'external_url': 'https://codepen.io/chriddyp/pen/bWLwgP.css'
})


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    app.run_server(debug=True, threaded=True)
