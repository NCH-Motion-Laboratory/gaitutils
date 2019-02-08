#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Created on Wed Jun 21 13:48:27 2017

@author: Jussi (jnu@iki.fi)
"""

from builtins import range
from gaitutils import (nexus, utils, sessionutils,
                       register_gui_exception_handler)
import numpy as np
import plotly.graph_objs as go
import plotly
from scipy import signal
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
import os.path as op
import logging

logger = logging.getLogger(__name__)


def _plot_vel_curves():

    sessionpath = nexus.get_sessionpath()
    c3ds = sessionutils.get_c3ds(sessionpath, trial_type='dynamic')
    if len(c3ds) == 0:
        raise Exception('Did not find any dynamic trials in current '
                        'session directory')
    traces = list()        
    for c3d in c3ds[:10]:
        v, vel = utils._trial_median_velocity(c3d, return_curve=True)
        vel = signal.medfilt(vel, 11)
        traces.append(go.Scatter({'y': vel, 'name': op.split(c3d)[-1]}))
    plotly.offline.plot(traces)


def do_plot(show=True, make_pdf=True):

    sessionpath = nexus.get_sessionpath()
    c3ds = sessionutils.get_c3ds(sessionpath, trial_type='dynamic')

    if len(c3ds) == 0:
        raise Exception('Did not find any dynamic trials in current '
                        'session directory')

    labels = [op.splitext(op.split(f)[1])[0] for f in c3ds]
    vels = np.array([utils._trial_median_velocity(trial) for trial in c3ds])
    vavg = np.nanmean(vels)

    fig = plt.figure()
    plt.stem(vels)
    plt.xticks(range(len(vels)), labels, rotation='vertical')
    plt.ylabel('Speed (m/s)')
    plt.tick_params(axis='both', which='major', labelsize=8)
    plt.title('Walking speed for dynamic trials (average %.2f m/s)' % vavg)
    plt.tight_layout()

    if make_pdf:
        pdf_name = op.join(nexus.get_sessionpath(), 'trial_velocity.pdf')
        with PdfPages(pdf_name) as pdf:
            pdf.savefig(fig)

    if show:
        plt.show()

    return fig


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    register_gui_exception_handler()
    do_plot()
