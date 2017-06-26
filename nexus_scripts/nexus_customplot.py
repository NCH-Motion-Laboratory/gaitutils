# -*- coding: utf-8 -*-
"""
Created on Tue Apr 28 11:37:51 2015

Example of a custom plot

Copy to nexus_scripts/nexus_customplot.py

@author: Jussi
"""

from gaitutils import Plotter, register_gui_exception_handler, cfg
import logging


# this function does the actual plotting - edit it to your needs
def do_plot():
    # create a plotter instance and open trial from Nexus
    pl = Plotter()
    pl.open_nexus_trial()
    # the prefix for the PDF filename
    pdf_prefix = 'Custom_'
    # the plot title, including some Eclipse info
    maintitle = pl.title_with_eclipse_info('Custom plot for')
    # we can define a layout either here or in the user specific config file
    # for the latter option, use pl.layout = cfg.layouts.your_layout_name
    pl.layout = [['PelvisAnglesX', 'PelvisAnglesY', 'PelvisAnglesZ'],
                 ['HipAnglesX', 'HipAnglesY', 'HipAnglesZ'],
                 ['KneeAnglesX', 'KneeAnglesY', 'KneeAnglesZ'],
                 ['AnkleAnglesX', 'FootProgressAnglesZ', 'AnkleAnglesZ']]
    # plot trial
    pl.plot_trial(maintitle=maintitle)
    # create PDF
    pl.create_pdf(pdf_prefix=pdf_prefix)


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    register_gui_exception_handler()
    do_plot()
