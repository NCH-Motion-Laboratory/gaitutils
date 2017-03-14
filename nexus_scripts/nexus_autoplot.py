# -*- coding: utf-8 -*-
"""
Kinetics/kinematics/EMG plots from Nexus.
Try to automatically figure out what to plot.
Use kinetics layout if kinetics available, else kinematics only.

"""


from gaitutils import Plotter, register_gui_exception_handler
import nexus_kinematics_emgplot
import nexus_kinetics_emgplot
import nexus_emgplot


def do_plot():

    pl = Plotter()
    pl.open_nexus_trial()

    if pl.trial.fp_valid:
        nexus_kinetics_emgplot.do_plot()
    else:
        nexus_kinematics_emgplot.do_plot()

    nexus_emgplot.do_plot()

if __name__ == '__main__':
    register_gui_exception_handler()
    do_plot()
