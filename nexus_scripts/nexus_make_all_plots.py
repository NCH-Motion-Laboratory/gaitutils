# -*- coding: utf-8 -*-
"""
Created on Thu Sep 03 14:54:34 2015

Script to create / update all kinetics/EMG plots for the marked trials

@author: Jussi
"""

from gaitutils import Plotter, cfg, register_gui_exception_handler, layouts
from gaitutils.nexus import enf2c3d, find_trials
import nexus_kin_consistency
import nexus_emg_consistency

import logging
logger = logging.getLogger(__name__)


def do_plot():

    MAX_TRIALS = 8

    # Eclipse trial notes/description must contain one of these strings
    strs = ['R1', 'R2', 'R3', 'R4', 'L1', 'L2', 'L3', 'L4']

    eclkeys = ['DESCRIPTION', 'NOTES']
    marked_trials = list(find_trials(eclkeys, strs))

    if not marked_trials:
        # try to find anything marked with 'ok' (kinematics-only sessions)
        marked_trials = list(find_trials(eclkeys, strs))
        if not marked_trials:
            raise Exception('Did not find any marked trials in current '
                            'session directory')

    if len(marked_trials) > MAX_TRIALS:
        raise Exception('Too many marked trials found!')

    pl = Plotter()
        
    for trial in marked_trials:

        c3d = enf2c3d(trial)
        pl.open_trial(c3d)
    
        side = pl.trial.fp_events['valid']
        if side not in ['L', 'R']:
            raise Exception('Need one kinetics cycle per trial')

        side_str = 'right' if side == 'R' else 'left'

        # kinetics-EMG            
        pl.layout = (cfg.layouts.lb_kinetics_emg_r if side == 'R' else
                     cfg.layouts.lb_kinetics_emg_l)

        maintitle = 'Kinetics-EMG (%s) for %s' % (side_str,
                                                  pl.title_with_eclipse_info())
        pl.plot_trial(maintitle=maintitle, show=False)
        pdf_name = 'Kinetics_EMG_%s_%s.pdf' % (pl.trial.trialname, side_str)
        pl.create_pdf(pdf_name=pdf_name)

        # EMG
        pdf_prefix = 'EMG_'
        maintitle = pl.title_with_eclipse_info('EMG plot for')
        layout = cfg.layouts.std_emg
        pl.layout = layouts.rm_dead_channels(c3d, pl.trial.emg, layout)
        pl.plot_trial(maintitle=maintitle, show=False)
        pl.create_pdf(pdf_prefix=pdf_prefix)

    # consistency plots
    nexus_emg_consistency.do_plot(show=False)
    nexus_kin_consistency.do_plot(show=False)    


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    register_gui_exception_handler()
    do_plot()
