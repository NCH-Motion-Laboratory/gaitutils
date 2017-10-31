# -*- coding: utf-8 -*-
"""

Average cycles over the session trials.

@author: Jussi (jnu@iki.fi)
"""

import logging

import gaitutils
from gaitutils import (cfg, nexus, layouts, eclipse, GaitDataError,
                       register_gui_exception_handler)


def do_plot(show=True, make_pdf=True):

    figs = []

    sessionpath = nexus.get_sessionpath()

    files = [nexus.enf2c3d(enf) for enf in nexus.get_session_enfs() if
             eclipse.get_eclipse_keys(enf)['TYPE'] == 'Dynamic']
    if not files:
        raise GaitDataError('No dynamic trials found for current session')
    models = [gaitutils.models.pig_lowerbody]

    atrial = gaitutils.stats.AvgTrial(files, models)

    pl = gaitutils.Plotter()
    pl.trial = atrial

    layout = cfg.layouts.lb_kin

    maintitle_ = '%d trial average from %s' % (atrial.nfiles, sessionpath)

    for side in ['R', 'L']:
        maintitle = maintitle_ + ' (side %s)' % side
        pl.layout = layouts.onesided_layout(layout, side)
        figs.append(pl.plot_trial(split_model_vars=False,
                                  plot_model_normaldata=True,
                                  model_stddev=atrial.stddev_data,
                                  maintitle=maintitle,
                                  show=False))

        if make_pdf:
            pl.create_pdf(pdf_name='kin_average_%s.pdf' % side,
                          sessionpath=sessionpath)

    if show:
        pl.show()

    return figs


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    register_gui_exception_handler()
    do_plot()
