# -*- coding: utf-8 -*-
"""
Created on Tue Apr 28 11:25:38 2015

Muscle length plot from Nexus.

@author: Jussi (jnu@iki.fi)
"""

import logging

from gaitutils import Plotter, register_gui_exception_handler, normaldata
from gaitutils.config import cfg


def do_plot(age=None):
    pl = Plotter()
    if age is not None:
        pl.add_normaldata(normaldata.normaldata_age(age))
    pl.open_nexus_trial()
    pdf_prefix = 'MuscleLen_'
    maintitle = pl.title_with_eclipse_info('Muscle length plot for')

    pl.layout = cfg.layouts.musclelen
    pl.plot_trial(maintitle=maintitle, ylim_to_zero=False)

    pl.create_pdf(pdf_prefix=pdf_prefix)


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    register_gui_exception_handler()
    do_plot()
