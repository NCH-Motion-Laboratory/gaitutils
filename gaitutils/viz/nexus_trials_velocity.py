#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Plot trial velocities.

@author: Jussi (jnu@iki.fi)
"""

import argparse
from builtins import range
import numpy as np
import plotly.graph_objs as go
import plotly
from scipy import signal
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
import os.path as op
import logging

from gaitutils import (nexus, utils, sessionutils,
                       register_gui_exception_handler)

logger = logging.getLogger(__name__)


def _plot_vel_curves(sessionpath=None):
    """Plot time-dependent velocity for each dynamic trial in session."""
    if sessionpath is None:
        sessionpath = nexus.get_sessionpath()
    c3ds = sessionutils.get_c3ds(sessionpath, trial_type='dynamic')
    if len(c3ds) == 0:
        raise Exception('Did not find any dynamic trials in current '
                        'session directory')
    traces = list()
    for c3d in c3ds[:10]:
        v, vel = utils._trial_median_velocity(c3d, return_curve=True)
        #vel = signal.medfilt(vel, 3)  # if spikes
        tname = op.split(c3d)[-1]
        trace = go.Scatter(y=vel, text=tname, name=tname, hoverinfo='x+y+text')
        traces.append(trace)
    plotly.offline.plot(traces)


def do_plot(sessionpath=None, show=True, make_pdf=True):
    """Plot median velocities for each dynamic trial in Nexus session."""
    if sessionpath is None:
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
    parser = argparse.ArgumentParser()
    parser.add_argument('--curves', action='store_true',
                        help='plot velocity curves')
    args = parser.parse_args()
    if args.curves:
        _plot_vel_curves()
    else:
        do_plot()
