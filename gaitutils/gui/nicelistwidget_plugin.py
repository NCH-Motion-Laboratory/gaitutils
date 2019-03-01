# -*- coding: utf-8 -*-
"""
Widget plugin for Qt Designer

@author: Jussi (jnu@iki.fi)
"""
from __future__ import absolute_import

from qt_widgets import NiceListWidget
from PyQt5 import QtDesigner


class NiceListWidgetPlugin(QtDesigner.QPyDesignerCustomWidgetPlugin):

    def __init__(self, parent=None):

        QtDesigner.QPyDesignerCustomWidgetPlugin.__init__(self)
        self.initialized = False

    def initialize(self, core):

        if self.initialized:
            return

        self.initialized = True

    def isInitialized(self):

        return self.initialized

    def createWidget(self, parent):
        return NiceListWidget(parent)

    def name(self):
        return "NiceListWidget"

    def group(self):
        return "Custom Widgets"

    def isContainer(self):
        return False

    def includeFile(self):
        return "gaitutils.gui.qt_widgets"
