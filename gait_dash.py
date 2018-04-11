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

import gaitutils

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
img_emg = base64.b64encode(buf.read())

# another plot
pl.layout = gaitutils.cfg.layouts.lb_kin
pl.plot_trial(show=False)

# encode plot as base64
buf = io.BytesIO()
pl.fig.savefig(buf, dpi=200)
buf.seek(0)
img_kin = base64.b64encode(buf.read())

print 'videos...'
# encode trial video as base64
vidfiles = pl.trial.video_files[0:]
vids_conv = gaitutils.report.convert_videos(vidfiles)
vids_enc = [base64.b64encode(open(f, 'rb').read()) for f in vids_conv]


WIDTH=800

gait_dropdown_choices=[{'label': 'EMG', 'value': img_emg},
                       {'label': 'Kinematics', 'value': img_kin}]

# TODO
def _videoelement(data):
    return html.Video(src='data:video/ogg;base64,%s' % data, controls=True,
                      width=WIDTH),

print 'page...'

app = dash.Dash()

app.layout = html.Div([

    html.Div([
        html.Div([
                html.H3('Gait data'),

                dcc.Dropdown(id='dd-data',
                        options=gait_dropdown_choices,
                        value=img_kin,
                    ),

                html.Img(id='gaitdata', width='100%'),  #  , width='auto'),

        ], className='eight columns'),

        html.Div([
                html.H3('Videos'),
                html.Video(src='data:video/ogg;base64,%s' % vids_enc[0],
                           controls=True, width='100%'),
                html.Video(src='data:video/ogg;base64,%s' % vids_enc[1],
                           controls=True, width='100%'),
                html.Video(src='data:video/ogg;base64,%s' % vids_enc[2],
                           controls=True, width='100%'),
                html.Button('Play all', id='play-vids'),

        ], className='four columns'),

    ], className='row')

])


@app.callback(
        Output(component_id='gaitdata', component_property='src'),
        [Input(component_id='dd-data', component_property='value')]
    )
def update_img(data):
    return 'data:video/ogg;base64,%s' % data


app.css.append_css({
    'external_url': 'https://codepen.io/chriddyp/pen/bWLwgP.css'
})


if __name__ == '__main__':
    app.run_server(debug=True)
