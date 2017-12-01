# -*- coding: utf-8 -*-
"""
Created on Tue Apr 28 11:37:51 2015

Kinetics-EMG plot from Nexus.

@author: Jussi (jnu@iki.fi)
"""
import logging
import argparse

from gaitutils import Plotter, register_gui_exception_handler, cfg


def do_plot(force_side=None):
    """ Side will be autodetected unless force_side is set """

    pl = Plotter()
    pl.open_nexus_trial()

    sides = pl.trial.fp_events['valid'] if force_side is None else force_side

    if force_side:
        sides = [side.upper() for side in force_side]
    else:
        if not sides:
            raise Exception('No kinetics available')

    for side in sides:
        pl.layout = (cfg.layouts.lb_kinetics_emg_r if side == 'R' else
                     cfg.layouts.lb_kinetics_emg_l)

        s = 'right' if side == 'R' else 'left'
        maintitle = 'Kinetics-EMG (%s) for %s' % (s,
                                                  pl.title_with_eclipse_info())
        # for EMG, plot only the cycle that has kinetics info
        pl.plot_trial(maintitle=maintitle, match_pig_kinetics=False
                      if force_side else True)
        pdf_name = 'Kinetics_EMG_%s_%s.pdf' % (pl.trial.trialname, s)
        pl.create_pdf(pdf_name=pdf_name)


if __name__ == '__main__':

    logging.basicConfig(level=logging.DEBUG)

    parser = argparse.ArgumentParser()
    parser.add_argument('--side', type=str, nargs='+',
                        help='side to plot kinetics for',
                        choices=['R', 'L', 'r', 'l'])
    args = parser.parse_args()

    register_gui_exception_handler()
    do_plot(force_side=args.side)
