# -*- coding: utf-8 -*-
"""
Created on Wed Jun 21 13:48:27 2017

@author: Jussi (jnu@iki.fi)
"""

from gaitutils import (nexus, cfg, utils, read_data, sessionutils,
                       register_gui_exception_handler, GaitDataError)
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
import os.path as op
import logging

logger = logging.getLogger(__name__)


def _trial_median_velocity(source):
    """ Compute median velocity (walking speed) over whole trial by
    differentiation of marker data """
    try:
        frate = read_data.get_metadata(source)['framerate']
        mkr = cfg.autoproc.track_markers[0]
        mdata = read_data.get_marker_data(source, mkr)
        pos_ = mdata[mkr+'_P']
        dim = utils.principal_movement_direction(pos_)
        vel_ = read_data.get_marker_data(source, mkr)[mkr+'_V'][:, dim]
    except (GaitDataError, ValueError):
        return np.nan
    vel = np.median(np.abs(vel_[np.where(vel_)]))
    return vel * frate / 1000.


def do_plot(show=True, make_pdf=True):

    sessionpath = nexus.get_sessionpath()
    c3ds = sessionutils.find_tagged(sessionpath, eclipse_keys=['TYPE'],
                                    tags=['DYNAMIC'])

    if len(c3ds) == 0:
        raise Exception('Did not find any dynamic trials in current '
                        'session directory')

    labels = [op.splitext(op.split(file)[1])[0] for file in c3ds]
    vels = np.array([_trial_median_velocity(trial) for trial in c3ds])
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
