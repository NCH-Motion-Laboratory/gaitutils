# -*- coding: utf-8 -*-
"""

Auto process single trial.
Note: does not use stats for event detection -> less accurate

@author: Jussi
"""

import logging
from nexus_autoprocess_session import _do_autoproc
from gaitutils import nexus, register_gui_exception_handler


def autoproc_single():

    vicon = nexus.viconnexus()
    meta = nexus.get_metadata(vicon)
    enfname = meta['sessionpath'] + meta['trialname'] + '.Trial.enf'
    _do_autoproc([enfname])  # need to listify name


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    register_gui_exception_handler()
    autoproc_single()
