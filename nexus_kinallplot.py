# -*- coding: utf-8 -*-
"""
Created on Tue Apr 28 11:37:51 2015

Plot Plug-in Gait outputs (online) from Nexus.

@author: Jussi
"""

from gaitutils import Plotter, layouts, register_gui_exception_handler


def do_plot():

    pl = Plotter()
    pl.open_nexus_trial()
    side = pl.trial.kinetics
    pl.layout = layouts.kinetics_emg(side) if side else layouts.kinematics_emg
    maintitleprefix = 'Kinetics/kinematics plot for '

    for vidfile in pl.trial.video_files:
        pl.external_play_video(vidfile)

    pl.plot_trial(maintitleprefix=maintitleprefix, emg_cycles={side: 1})
    pl.move_plot_window(10, 30)

if __name__ == '__main__':
    register_gui_exception_handler()
    do_plot()
