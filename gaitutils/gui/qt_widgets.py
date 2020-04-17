# -*- coding: utf-8 -*-
"""
gaitutils custom Qt widgets

@author: Jussi (jnu@iki.fi)
"""

from PyQt5 import QtCore, QtWidgets
from PyQt5.QtCore import QObject, pyqtSignal
import logging
import sys


class NiceListWidgetItem(QtWidgets.QListWidgetItem):
    """Make list items more pythonic"""

    def __init__(self, *args, **kwargs):
        # don't pass this arg to superclass __init__
        checkable = kwargs.pop('checkable')
        super(NiceListWidgetItem, self).__init__(*args, **kwargs)
        if checkable:
            self.setFlags(self.flags() | QtCore.Qt.ItemIsUserCheckable)

    @property
    def text(self):
        return super(NiceListWidgetItem, self).text()

    @property
    def userdata(self):
        return super(NiceListWidgetItem, self).data(QtCore.Qt.UserRole)

    @userdata.setter
    def userdata(self, _data):
        if _data is not None:
            super(NiceListWidgetItem, self).setData(QtCore.Qt.UserRole, _data)

    @property
    def checkstate(self):
        return super(NiceListWidgetItem, self).checkState()

    @checkstate.setter
    def checkstate(self, checked):
        state = QtCore.Qt.Checked if checked else QtCore.Qt.Unchecked
        super(NiceListWidgetItem, self).setCheckState(state)


class NiceListWidget(QtWidgets.QListWidget):
    """Adds some conveniences to QListWidget"""

    def __init__(self, parent=None):
        super(NiceListWidget, self).__init__(parent)

    @property
    def items(self):
        """Yield all list items.
        
        NB: be careful when modifying list items in a loop with the generator -
        count() is evaluated only once, so the generator may return items that
        have already been deleted"""
        for i in range(self.count()):
            yield self.item(i)

    @property
    def checked_items(self):
        """Yield checked items"""
        return (item for item in self.items if item.checkstate)

    def check_all(self):
        """Check all items"""
        for item in self.items:
            item.checkstate = True

    def check_none(self):
        """Uncheck all items"""
        for item in self.items:
            item.checkstate = False

    def add_item(self, txt, data=None, checkable=False, checked=False):
        """Add checkable item with data. Select new item."""
        item = NiceListWidgetItem(txt, self, checkable=checkable)
        item.userdata = data
        if checkable:
            item.checkstate = checked
        self.setCurrentItem(item)

    def rm_current_item(self):
        """Remove currently selected item"""
        return self.takeItem(self.row(self.currentItem()))


class QtHandler(logging.Handler):
    """Qt logging handler"""

    def __init__(self):
        logging.Handler.__init__(self)

    def emit(self, record):
        record = self.format(record)
        if record:
            XStream.stdout().write('%s\n' % record)


class XStream(QtCore.QObject):
    """Stream for Qt logging handler"""

    _stdout = None
    _stderr = None
    messageWritten = QtCore.pyqtSignal(str)

    def flush(self):
        pass

    def fileno(self):
        return -1

    def write(self, msg):
        if not self.signalsBlocked():
            self.messageWritten.emit(msg)

    @staticmethod
    def stdout():
        if not XStream._stdout:
            XStream._stdout = XStream()
            #sys.stdout = XStream._stdout  # also capture stdout
        return XStream._stdout

    @staticmethod
    def stderr():
        if not XStream._stderr:
            XStream._stderr = XStream()
            #sys.stderr = XStream._stderr  # ... and stderr
        return XStream._stderr


class ProgressBar(QtWidgets.QProgressDialog):
    """Qt progress bar with reasonable defaults"""

    # custom signal to indicate that the operation was canceled
    _canceled = pyqtSignal()

    def __init__(self, title):
        super(self.__class__, self).__init__()
        self.setWindowTitle(title)
        self.cancelbutton = QtWidgets.QPushButton('Cancel')
        self.setCancelButton(self.cancelbutton)
        # set a custom cancel signal, since the default one immediately
        # close the progress bar
        self.cancelbutton.disconnect()
        self.cancelbutton.clicked.connect(self._cancel)
        self.setMinimum(0)
        self.setMaximum(100)
        self.setGeometry(500, 300, 500, 100)
        # self.setAutoClose(False)
        self.setAutoReset(False)
        self.show()

    def _cancel(self):
        """Custom cancel handler"""
        self.cancelbutton.setText('Wait...')
        self.cancelbutton.setEnabled(False)
        QtWidgets.QApplication.processEvents()
        self._canceled.emit()

    def update(self, text, p):
        """Update bar, showing text and bar at p%"""
        self.setLabelText(text)
        self.setValue(p)
        # update right away in case that thread is blocked
        QtWidgets.QApplication.processEvents()


class ProgressSignals(QObject):
    """Used to emit progress signals across threads"""

    progress = pyqtSignal(object, object)

    def __init__(self):
        super(ProgressSignals, self).__init__()
        # this flag can be checked to see whether the operation was canceled
        self.canceled = False

    def cancel(self):
        """Raise the cancel flag"""
        self.canceled = True
