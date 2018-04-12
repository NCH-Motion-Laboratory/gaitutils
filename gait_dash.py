#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""

gaitutils + dash report proof of concept

(choosable) gait plot + videos

TODO:

    session chooser ?
    
    smarter plotter (use gaitutils layouts)    
    
    do not recreate the dcc.Graph but just redef figure prop with new data

    pre-base64 for video data?

    new video player?
        -kb control
        -variable speed
        -zoom

NOTES:

    dcc.Dropdown dicts cannot have complex objects as values

@author: jussi
"""

# -*- coding: utf-8 -*-
import logging
import dash
import dash_core_components as dcc
import dash_html_components as html
from dash.dependencies import Input, Output
import plotly.tools
import base64
import io
import plotly.plotly as py
import plotly.graph_objs as go

import gaitutils
from gaitutils.nexus import find_tagged

logger = logging.getLogger(__name__)


def _video_element(data):
    """Create dash Video element from given base64 data"""
    return html.Video(src='data:video/ogg;base64,%s' % data, controls=True,
                      loop=True, width='100%')


def _trial_videos(trial):
    """Videos from given trial"""
    vids_conv = gaitutils.report.convert_videos(trial.video_files)
    return [base64.b64encode(open(f, 'rb').read()) for f in vids_conv]


def _static_image_element(data):
    """Create static image element from given base64 data"""
    return html.Img(src='data:image/png;base64,%s' % data, width='100%')


def _plot_modelvar_plotly(trials, modelvar):
    """Make a plotly plot of modelvar, including given trials"""

    traces = list()

    for trial in trials:
        trial.set_norm_cycle(1)
        logger.debug(modelvar)
        t, y = trial[modelvar]
        trace = go.Scatter(x=t, y=y)
        traces.append(trace)

    figure =  {'data': traces,
               'layout': go.Layout(
                       xaxis={'title': '% of gait cycle'},
                       yaxis={'title': modelvar})
               }

    return dcc.Graph(figure=figure, id='testfig')


session = "C:/Users/hus20664877/Desktop/Vicon/vicon_data/problem_cases/2018_3_12_seur_RH"
# get trials
c3ds = find_tagged(sessionpath=session)
trials_ = [gaitutils.Trial(c3d) for c3d in c3ds]
trials_di = {tr.trialname: tr for tr in trials_}

# build the dcc.Dropdown options list for the trials
trials_dd = list()
for tr in trials_:
    lbl = '%s (%s, %s)' % (tr.trialname, tr.eclipse_data['DESCRIPTION'],
                           tr.eclipse_data['NOTES'])
    trials_dd.append({'label': lbl, 'value': tr.trialname})

trial = trials_[0]

# encode trial video as base64
vidfiles = trial.video_files[0:]
vids_conv = gaitutils.report.convert_videos(vidfiles)
vids_enc = [base64.b64encode(open(f, 'rb').read()) for f in vids_conv]

gait_dropdown_choices=[{'label': 'Pelvic tilt', 'value': 'LPelvisAnglesX'},
                       {'label': 'Ankle dorsi/plant', 'value': 'LAnkleAnglesX'}
                       ]

app = dash.Dash()

app.layout = html.Div([

    html.Div([
        html.Div([
                html.H3('Gait data'),

                'Select trials:',

                dcc.Dropdown(id='dd-trials', clearable=True, multi=True,
                             options=trials_dd),

                'Select variables:',

                dcc.Dropdown(id='dd-vars', clearable=False,
                             options=gait_dropdown_choices,
                             value='LPelvisAnglesX'),

                html.Div(id='imgdiv')

        ], className='eight columns'),

        html.Div([
                html.H3('Videos'),

                'Select trials:',

                dcc.Dropdown(id='dd-videos', clearable=False,
                             options=trials_dd),

                html.Div(id='videos'),
            ], className='four columns'),

    ], className='row')

])


@app.callback(
        Output(component_id='imgdiv', component_property='children'),
        [Input(component_id='dd-trials', component_property='value'),
         Input(component_id='dd-vars', component_property='value')]
    )
def update_contents(sel_trial_labels, sel_vars):
    sel_trials = [trials_di[lbl] for lbl in sel_trial_labels]
    return _plot_modelvar_plotly(sel_trials, sel_vars)


@app.callback(
        Output(component_id='videos', component_property='children'),
        [Input(component_id='dd-videos', component_property='value')]
    )
def update_videos(trial_lbl):
    trial = trials_di[trial_lbl]
    vid_elements = [_video_element(data) for data in _trial_videos(trial)]
    return vid_elements or 'No videos'


app.css.append_css({
    'external_url': 'https://codepen.io/chriddyp/pen/bWLwgP.css'
})


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    app.run_server(debug=True)
