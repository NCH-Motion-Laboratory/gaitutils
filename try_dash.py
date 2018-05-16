#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
Try out video + mpl plot in dash

@author: jussi
"""

# -*- coding: utf-8 -*-

import gaitutils
import logging


logging.basicConfig(level=logging.DEBUG)


sessions = [r"C:\Users\hus20664877\Desktop\Vicon\vicon_data\test\E0041_ES\2017_1_5_seur_ES",
            r"C:\Users\hus20664877\Desktop\Vicon\vicon_data\test\E0041_ES\2017_1_5_seur_tuet_ES"]

sessions = [r"C:\Users\hus20664877\Desktop\Vicon\vicon_data\problem_cases\2018_3_12_seur_RH",
            r"C:\Users\hus20664877\Desktop\Vicon\vicon_data\problem_cases\2018_3_12_seur_tuet_RH"]

app = gaitutils.report.dash_report(sessions[:2])

app.server.run(threaded=True)



