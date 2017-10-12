# -*- coding: utf-8 -*-
"""

Average cycles over the session trials.

@author: Jussi (jnu@iki.fi)
"""

import gaitutils
from gaitutils import cfg, nexus, layouts, eclipse
import logging


def do_plot():

    files = [nexus.enf2c3d(enf) for enf in nexus.get_session_enfs() if
             eclipse.get_eclipse_keys(enf)['TYPE'] == 'Dynamic']
    models = [gaitutils.models.pig_lowerbody]

    atrial = gaitutils.stats.AvgTrial(files, models)

    pl = gaitutils.Plotter()
    pl.trial = atrial

    layout = cfg.layouts.lb_kin

    for side in ['R', 'L']:
        pl.layout = layouts.onesided_layout(layout, side)
        pl.plot_trial(split_model_vars=False, plot_model_normaldata=False,
                      model_stddev=atrial.stddev_data)


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    do_plot()
