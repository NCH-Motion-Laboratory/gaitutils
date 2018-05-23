# -*- coding: utf-8 -*-
"""

Auto process single trial.
Note: does not use stats for event detection -> less accurate

@author: Jussi (jnu@iki.fi)
"""

import logging
import os.path as op

from nexus_autoprocess_session import _do_autoproc
from gaitutils import nexus, register_gui_exception_handler


def autoproc_single():
    fn = nexus.get_trialname() + '.Trial.enf'
    enfname = op.join(nexus.get_sessionpath(), fn)
    _do_autoproc([enfname])


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    register_gui_exception_handler()
    autoproc_single()
