#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""

gaitutils + dash report proof of concept

(choosable) gait plot + videos

TODO next POC:

    session chooser ?
    variable video speed?


TODO:
    
    video player fixes:
        -preconvert to ogv before starting dash app (otherwise app hangs on conversion)
        -variable speed

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
import plotly.plotly as py
import plotly.graph_objs as go

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


def _plot_modelvar_plotly(trials, layout):
    """Make a plotly plot of modelvar, including given trials
    TODO:
        context, colors?
            -EMG should use color cycles
            -trials can use B/R for right/left
        y and x labels, ticks
        proper subplot titles from model
    """

    nrows = len(layout)
    ncols = len(layout[0])
    allvars = [item for row in layout for item in row]

    fig = plotly.tools.make_subplots(rows=nrows, cols=ncols,
                                     subplot_titles=allvars)
    tracegroups = set()
    for trial in trials:
        for context in ['L', 'R']:
            cycle_ind = 1  # FIXME
            cyc = trial.get_cycle(context, cycle_ind)
            trial.set_norm_cycle(cyc)
            for i, row in enumerate(layout):
                for j, var in enumerate(row):
                    # in legend, traces will be grouped according to tracegroup (which is also the label)
                    # tracegroup = '%s / %s' % (trial.name_with_description, cycle_desc[context])  # include cycle
                    # tracegroup = '%s' % (trial.name_with_description)  # no cycle info (group both cycles from trial)
                    tracegroup = trial.eclipse_data['NOTES']  # short one
                    # only show the legend for the first trace in the tracegroup, so we do not repeat legends
                    show_legend = tracegroup not in tracegroups

                    if models.model_from_var(var):  # plot model variable
                        var_ = context + var
                        t, y = trial[var_]
                        color = 'rgb(0, 0, 200)' if context == 'R' else 'rgb(200, 0, 0)'
                        line = {'color': color}
                        trace = go.Scatter(x=t, y=y, name=tracegroup,
                                           legendgroup=tracegroup,
                                           showlegend=show_legend,
                                           line=line)
                        tracegroups.add(tracegroup)
                        fig.append_trace(trace, i+1, j+1)

                    elif trial.emg.is_channel(var) or var in cfg.emg.channel_labels:
                        # EMG channel context matches cycle context
                        if var[0] != context:
                            continue
                        t, y = trial[var]
                        line = {'color': 'rgb(0, 0, 0)', 'width': .5}
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

    margin=go.Margin(l=50, r=0, b=0, t=50, pad=4)

    layout = go.Layout(legend=dict(x=100, y=.5), margin=margin)
    fig['layout'].update(layout)
    return dcc.Graph(figure=fig, id='testfig')

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
# and for the vars
vars_dropdown_choices = [
                         {'label': 'Pelvic tilt', 'value': [['PelvisAnglesX']]},
                         {'label': 'Ankle dorsi/plant', 'value': [['AnkleAnglesX']]},
                         {'label': 'All kinematics', 'value': cfg.layouts.lb_kinematics},
                         {'label': 'Kinetics/EMG', 'value': cfg.layouts.lb_kinetics_emg_r},
                         {'label': 'EMG', 'value': cfg.layouts.std_emg}
                        ]
vars_options, vars_mapper = _make_dropdown_lists(vars_dropdown_choices)

# create the app
app = dash.Dash()
app.layout = html.Div([

    html.Div([
        html.Div([
                html.H3('Gait data'),

                'Select trials:',

                dcc.Dropdown(id='dd-trials', clearable=True, multi=True,
                             options=trials_dd, value=trials_dd[0]['value']),

                'Select variables:',

                dcc.Dropdown(id='dd-vars', clearable=False,
                             options=vars_options,
                             value=vars_options[0]['value']),

                html.Div(id='imgdiv')

        ], className='eight columns'),

        html.Div([
                html.H3('Videos'),

                'Select trials:',

                dcc.Dropdown(id='dd-videos', clearable=False,
                             options=trials_dd, value=trials_dd[0]['value']),

                html.Div(id='videos'),
            ], className='four columns'),

    ], className='row')

])


@app.callback(
        Output(component_id='imgdiv', component_property='children'),
        [Input(component_id='dd-trials', component_property='value'),
         Input(component_id='dd-vars', component_property='value')]
    )
def update_contents(sel_trial_labels, sel_var):
    if not isinstance(sel_trial_labels, list):  # either single item or list
        sel_trial_labels = [sel_trial_labels]
    sel_vars = vars_mapper[sel_var]
    logger.debug('got trials %s, vars %s' % (sel_trial_labels, sel_vars))
    sel_trials = [trials_di[lbl] for lbl in sel_trial_labels]
    return _plot_modelvar_plotly(sel_trials, sel_vars)


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
