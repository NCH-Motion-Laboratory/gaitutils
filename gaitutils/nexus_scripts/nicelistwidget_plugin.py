# -*- coding: utf-8 -*-
"""
Created on Tue Jun 20 11:01:29 2017

@author: HUS20664877
"""

from plotter_gui import NiceListWidget
from PyQt5 import QtGui, QtCore, QtDesigner


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
        return "plotter_gui"
