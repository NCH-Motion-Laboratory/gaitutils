# -*- coding: utf-8 -*-
"""
Created on Tue Apr 28 11:37:51 2015

Plot Plug-in Gait outputs (online) from Nexus.

@author: Jussi
"""

from gaitutils import Plotter, layouts, register_gui_exception_handler
import logging

def do_plot():

    pl = Plotter()
    pl.open_nexus_trial()
    pl.layout = layouts.std_kinall
    maintitleprefix = 'Kinetics/kinematics plot for '

    for vidfile in pl.trial.video_files:
        pl.external_play_video(vidfile)

    pl.plot_trial(maintitleprefix=maintitleprefix)
    pl.move_plot_window(10, 30)

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    register_gui_exception_handler()
    do_plot()
