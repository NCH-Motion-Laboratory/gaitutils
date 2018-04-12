#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""

gaitutils + dash report proof of concept

(choosable) gait plot + videos

TODO:
    
    free text at top


@author: jussi
"""

# -*- coding: utf-8 -*-
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


def _video_element(data):
    """Create dash Video element from given base64 data"""
    return html.Video(src='data:video/ogg;base64,%s' % data, controls=True,
                      loop=True, width='100%')


def _static_image_element(data):
    """Create static image element from given base64 data"""
    return html.Img(src='data:image/png;base64,%s' % data, width='100%')


def _plot_modelvar_plotly(trial, modelvar):
    """Make a plotly plot of modelvar"""

    trial.set_norm_cycle(1)
    t, y = trial[modelvar]

    trace = go.Scatter(x=t, y=y)
    traces = [trace]

    figure =  {'data': traces,
               'layout': go.Layout(
                       xaxis={'title': '% of gait cycle'},
                       yaxis={'title': modelvar})
               }

    return dcc.Graph(figure=figure, id='testfig')

print 'plots...'

# one plot
pl = gaitutils.Plotter()
pl.open_nexus_trial()
pl.layout = gaitutils.cfg.layouts.std_emg
pl.plot_trial(show=False)
# encode plot as base64
buf = io.BytesIO()
pl.fig.savefig(buf, dpi=200)
buf.seek(0)
img_emg = _static_image_element(base64.b64encode(buf.read()))

# another plot
pl.layout = gaitutils.cfg.layouts.lb_kin
pl.plot_trial(show=False)
buf = io.BytesIO()
pl.fig.savefig(buf, dpi=200)
buf.seek(0)
img_kin = _static_image_element(base64.b64encode(buf.read()))

# plotly plot
plotlyfig = _plot_modelvar_plotly(pl.trial, 'LPelvisAnglesX')

print 'videos...'
# encode trial video as base64
vidfiles = pl.trial.video_files[0:]
vids_conv = gaitutils.report.convert_videos(vidfiles)
vids_enc = [base64.b64encode(open(f, 'rb').read()) for f in vids_conv]


images = {'img_kin': img_kin, 'img_emg': img_emg, 'plotlyfig': plotlyfig}

gait_dropdown_choices=[{'label': 'EMG', 'value': 'img_emg'},
                       {'label': 'Kinematics', 'value': 'img_kin'},
                       {'label': 'Pelvic tilt', 'value': 'plotlyfig'}]


print 'page...'

app = dash.Dash()

app.layout = html.Div([

    html.Div([
        html.Div([
                html.H3('Gait data'),

                dcc.Dropdown(id='dd-data', clearable=False,
                             options=gait_dropdown_choices,
                             value='img_kin'),

                html.Div(id='imgdiv')

        ], className='eight columns'),

        html.Div([html.H3('Videos')] + [_video_element(v) for v in vids_enc],
                  className='four columns'),

    ], className='row')

])


@app.callback(
        Output(component_id='imgdiv', component_property='children'),
        [Input(component_id='dd-data', component_property='value')]
    )
def update_contents(element):
    print element
    return images[element]


app.css.append_css({
    'external_url': 'https://codepen.io/chriddyp/pen/bWLwgP.css'
})


if __name__ == '__main__':
    app.run_server(debug=True)
