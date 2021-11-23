# -*- coding: utf-8 -*-
"""

Console script wrappers for the plotters. These are used as setuptools
entry points.

@author: Jussi (jnu@iki.fi)
"""


import logging
import argparse

from . import plots
from .plot_misc import show_fig
from ..envutils import _register_gui_exception_handler
from .. import nexus


def _console_init():
    """Set up some things for console scripts"""
    logging.basicConfig(level=logging.DEBUG)
    _register_gui_exception_handler()

def plot_nexus_session():
    """Plot tagged dynamic trials from current Nexus session"""
    _console_init()
    parser = argparse.ArgumentParser()
    parser.add_argument('--layout', type=str)
    parser.add_argument('--backend', type=str)
    parser.add_argument('--tags', nargs='+')
    args = parser.parse_args()
    sessions = [nexus.get_sessionpath()]
    fig = plots._plot_sessions(
        sessions, tags=args.tags, backend=args.backend, layout=args.layout
    )
    show_fig(fig)


def plot_nexus_session_average():
    """Kin average plot for session"""
    _console_init()
    parser = argparse.ArgumentParser()
    parser.add_argument('--layout', type=str)
    parser.add_argument('--backend', type=str)
    args = parser.parse_args()
    session = nexus.get_sessionpath()
    fig = plots._plot_session_average(
        session, layout=args.layout, backend=args.backend
    )
    show_fig(fig)
