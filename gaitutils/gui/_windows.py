# -*- coding: utf-8 -*-
"""

Non-Qt GUI stuff (Windows native dialogs etc.)

@author: Jussi (jnu@iki.fi)
"""

from builtins import str
import ctypes
import sys
import logging

logger = logging.getLogger(__name__)


def error_exit(message):
    """ Custom error handler """
    ctypes.windll.user32.MessageBoxA(0, message.encode('latin-1'),
                                     "Error in Nexus Python script", 0)
    sys.exit()


def messagebox(message, title=None):
    """ Custom notification handler """
    if title is None:
        title = "Message from Nexus Python script"
    ctypes.windll.user32.MessageBoxA(0, str(message), title, 0)


def yesno_box(message):
    """ Yes/no dialog with message """
    return ctypes.windll.user32.MessageBoxA(0,
                                            str(message), "Question", 1) == 1
