#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
Try out video + mpl plot in dash

@author: jussi
"""

# -*- coding: utf-8 -*-
import dash
import dash_core_components as dcc
import dash_html_components as html
import plotly.tools
import matplotlib.pyplot as plt

fig1 = plt.figure()
plt.subplot(221)
plt.plot(range(10))

fig2 = plt.figure()
plt.subplot(221)
plt.plot(range(10, 0 ,-1))

fig1p = plotly.tools.mpl_to_plotly(fig1)
fig2p = plotly.tools.mpl_to_plotly(fig2)

app = dash.Dash()

app.layout = html.Div(children=[
    html.H1(children='Hello Dash'),

    html.Div(children='''
        Dash: A web application framework for Python.
    '''),

    dcc.Graph(
        id='example-graph1',
        figure=fig1p
    ),

    html.Video(id='myvid', title='video',
               src='https://www.w3schools.com/html/mov_bbb.mp4')

])

if __name__ == '__main__':
    app.run_server(debug=True)