#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""

gaitutils + dash report proof of concept

(choosable) gait plot + videos

TODO next POC:

    dlg boxes also for individual kin* vars
    force EMG y scale
    subplot title fontsize
    session chooser?
    variable video speed?

NOTES:

    problems w/ server - see:
    https://stackoverflow.com/questions/40247025/flask-socket-error-errno-10053-an-established-connection-was-aborted-by-the
    dcc.Dropdown dicts need to have str values

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
from itertools import cycle

import gaitutils
from gaitutils.nexus import find_tagged
from gaitutils import cfg, models

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


graphind = 0


def _plot_trials(trials, layout):
    """Make a plotly plot of modelvar, including given trials"""

    label_fontsize = 12

    nrows = len(layout)
    ncols = len(layout[0])

    if len(trials) > len(plotly.colors.DEFAULT_PLOTLY_COLORS):
        logger.warning('Not enough colors for plot')

    colors = cycle(plotly.colors.DEFAULT_PLOTLY_COLORS)
    allvars = [item for row in layout for item in row]
    # would be nicer to set in main plotting loop
    titles = [_var_title(var) for var in allvars]

    fig = plotly.tools.make_subplots(rows=nrows, cols=ncols,
                                     subplot_titles=titles)
    tracegroups = set()
    for trial in trials:
        trial_color = colors.next()
        for context in ['R', 'L']:
            cycle_ind = 1  # FIXME
            cyc = trial.get_cycle(context, cycle_ind)
            trial.set_norm_cycle(cyc)
            for i, row in enumerate(layout):
                for j, var in enumerate(row):
                    plot_ind = i * ncols + j + 1  # plotly subplot index
                    yaxis = 'yaxis%d' % plot_ind  # name of plotly yaxis
                    # in legend, traces will be grouped according to tracegroup (which is also the label)
                    # tracegroup = '%s / %s' % (trial.name_with_description, cycle_desc[context])  # include cycle
                    # tracegroup = '%s' % (trial.name_with_description)  # no cycle info (group both cycles from trial)
                    tracegroup = trial.eclipse_data['NOTES']  # short one
                    # only show the legend for the first trace in the tracegroup, so we do not repeat legends
                    show_legend = tracegroup not in tracegroups

                    mod = models.model_from_var(var)
                    if mod:
                        if var in mod.varnames_noside:
                            var = context + var
                        if mod.is_kinetic_var(var):
                            if var[0] != context:
                                continue
                        t, y = trial[var]
                        line = {'color': trial_color}
                        if context == 'L':
                            line['dash'] = 'dash'
                        trace = go.Scatter(x=t, y=y, name=tracegroup,
                                           legendgroup=tracegroup,
                                           showlegend=show_legend,
                                           line=line)
                        tracegroups.add(tracegroup)
                        fig.append_trace(trace, i+1, j+1)
                        # LaTeX does not render, so remove units from ylabel
                        ylabel = ' '.join(mod.ylabels[var].split(' ')[k] for k in [0, -1])
                        fig['layout'][yaxis].update(title=ylabel, titlefont={'size': label_fontsize})

                    elif trial.emg.is_channel(var) or var in cfg.emg.channel_labels:
                        # EMG channel context matches cycle context
                        if var[0] != context:
                            continue
                        t, y = trial[var]
                        line = {'width': 1, 'color': trial_color}
                        y *= 1e3  # plot mV
                        trace = go.Scatter(x=t, y=y, name=tracegroup,
                                           legendgroup=tracegroup,
                                           line=line,
                                           showlegend=show_legend)
                        tracegroups.add(tracegroup)
                        fig.append_trace(trace, i+1, j+1)

                    elif var is None:
                        continue

                    elif 'legend' in var:
                        continue

                    else:
                        raise Exception('Unknown variable %s' % var)

    # put x labels on last row
    inds_last = range((nrows-1)*ncols, nrows*ncols)
    axes_last = ['xaxis%d' % (ind+1) for ind in inds_last]
    for ax in axes_last:
        fig['layout'][ax].update(title='% of gait cycle',
                                 titlefont={'size': label_fontsize})

    margin = go.Margin(l=50, r=0, b=50, t=50, pad=4)
    layout = go.Layout(legend=dict(x=100, y=.5), margin=margin)

    fig['layout'].update(layout)
    global graphind
    graphind += 1
    return dcc.Graph(figure=fig, id='graph%d' % graphind)

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

# template of layout names -> layouts
_dd_opts_multi = [
                  {'label': 'Kinematics', 'value': cfg.layouts.lb_kinematics},
                  {'label': 'Kinetics', 'value': cfg.layouts.lb_kinetics},
                  {'label': 'EMG', 'value': cfg.layouts.std_emg[4:]},  # FIXME: hack to show lower body EMGs only
                  {'label': 'Kinetics-EMG left', 'value': cfg.layouts.lb_kinetics_emg_l},
                  {'label': 'Kinetics-EMG right', 'value': cfg.layouts.lb_kinetics_emg_r},
                 ]

# pick desired single variables from model and append
singlevars = [{'label': varlabel, 'value': [[var]]} for var, varlabel in
              models.pig_lowerbody.varlabels_noside.items()]
singlevars = sorted(singlevars, key=lambda it: it['label'])
_dd_opts_multi.extend(singlevars)

# precreate dcc.Graphs
# need separate sets of graphs for upper/lower panel
dd_opts_multi_upper = [{'label': di['label'], 'value': _plot_trials(trials_, di['value'])} for di in _dd_opts_multi]
opts_multi, mapper_multi_upper = _make_dropdown_lists(dd_opts_multi_upper)
dd_opts_multi_lower = [{'label': di['label'], 'value': _plot_trials(trials_, di['value'])} for di in _dd_opts_multi]
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
                             
                '<br>',

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


app.css.append_css({
    'external_url': 'https://codepen.io/chriddyp/pen/bWLwgP.css'
})


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    app.run_server(debug=True, threaded=True)
