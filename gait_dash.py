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
import logging

import gaitutils

logger = logging.getLogger(__name__)

session = "C:/Users/hus20664877/Desktop/Vicon/vicon_data/problem_cases/2018_3_12_seur_tuet_RH"


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    app = gaitutils.report._single_session_app(session)
    app.run_server(debug=True, threaded=True)
