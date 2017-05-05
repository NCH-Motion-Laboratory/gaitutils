# -*- coding: utf-8 -*-
"""
Created on Tue Jan 26 15:31:11 2016

Misc functions for Gaitplotter (OS dialogs etc)

@author: Jussi
"""

import ctypes
import sys


def error_exit(message):
    """ Custom error handler """
    # graphical error dialog - Windows specific
    # casts to str are needed, since MessageBoxA does not like Unicode
    ctypes.windll.user32.MessageBoxA(0, str(message),
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
