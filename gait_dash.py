#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""

gaitutils + dash report proof of concept

(choosable) gait plot + videos



@author: jussi
"""

# -*- coding: utf-8 -*-
import dash
import dash_core_components as dcc
import dash_html_components as html
import plotly.tools
import base64
import io

import gaitutils

pl = gaitutils.Plotter()
pl.open_nexus_trial()
pl.layout = gaitutils.cfg.layouts.std_emg
pl.plot_trial(show=False)

# encode plot as base64
buf = io.BytesIO()
pl.fig.savefig(buf, dpi=200)
buf.seek(0)
img_enc = base64.b64encode(buf.read())

# encode trial video as base64
vidfiles = pl.trial.video_files[0:]
vids_conv = gaitutils.report.convert_videos(vidfiles)
vids_enc = [base64.b64encode(open(f, 'rb').read()) for f in vids_conv]


def _videoelement(data):
    return html.Video(src='data:video/ogg;base64,%s' % data, controls=True,
                      width=500),


app = dash.Dash()

app.layout = html.Div([

    html.Div([
        html.Div([
                html.H3('Gait data'),
                html.Img(src='data:image/png;base64,%s' % img_enc,
                         width=500),
        ], className='six columns'),

        html.Div([
                html.H3('Video'),
                html.Video(src='data:video/ogg;base64,%s' % vids_enc[0],
                           controls=True, width=500),
                html.Video(src='data:video/ogg;base64,%s' % vids_enc[1],
                           controls=True, width=500),
                html.Video(src='data:video/ogg;base64,%s' % vids_enc[2],
                           controls=True, width=500),

        ], className='six columns'),

    ], className='row')

])


app.css.append_css({
    'external_url': 'https://codepen.io/chriddyp/pen/bWLwgP.css'
})


if __name__ == '__main__':
    app.run_server(debug=True)
