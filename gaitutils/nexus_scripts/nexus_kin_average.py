# -*- coding: utf-8 -*-
"""

Average cycles over the session trials.

@author: Jussi (jnu@iki.fi)
"""

import logging

import gaitutils
from gaitutils import (cfg, nexus, layouts, GaitDataError,
                       register_gui_exception_handler)


def do_plot(show=True, make_pdf=True):

    figs = []

    sessionpath = nexus.get_sessionpath()

    c3ds = nexus.find_tagged(eclipse_keys=['TYPE'], tags=['DYNAMIC'])

    if not c3ds:
        raise GaitDataError('No dynamic trials found for current session')

    atrial = gaitutils.stats.AvgTrial(c3ds)

    pl = gaitutils.Plotter()
    pl.trial = atrial

    layout = cfg.layouts.lb_kin

    maintitle_ = '%d trial average from %s' % (atrial.nfiles, sessionpath)

    for side in ['R', 'L']:
        side_str = 'right' if side == 'R' else 'left'
        maintitle = maintitle_ + ' (%s)' % side_str
        pl.layout = layouts.onesided_layout(layout, side)
        figs.append(pl.plot_trial(split_model_vars=False,
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
