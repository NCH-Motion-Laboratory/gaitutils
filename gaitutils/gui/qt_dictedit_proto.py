"""
Prototype for a Qt list/dict editor

parameters: existing dict/list

"""

import ast
from PyQt5 import QtWidgets
from PyQt5.QtWidgets import QDialogButtonBox, QPushButton


def qt_message_dialog(msg):
    """Show message with 'OK' button"""
    dlg = QtWidgets.QMessageBox()
    dlg.setWindowTitle('Message')
    dlg.setText(msg)
    dlg.addButton(QtWidgets.QPushButton('Ok'), QtWidgets.QMessageBox.YesRole)
    dlg.exec_()


class QCompoundEditorDict(QtWidgets.QDialog):
    """Compound editor for dicts"""

    def __init__(self, data, parent=None):
        super(QCompoundEditorDict, self).__init__(parent=parent)
        root_layout = QtWidgets.QVBoxLayout()
        self.datable = QtWidgets.QTableWidget()
        self.data = data
        # create the button box
        self.buttonbox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        insertbutton = QPushButton('Insert')
        deletebutton = QPushButton('Delete')
        self.buttonbox.addButton(insertbutton, QDialogButtonBox.ActionRole)
        self.buttonbox.addButton(deletebutton, QDialogButtonBox.ActionRole)
        insertbutton.clicked.connect(self._insert_item)
        deletebutton.clicked.connect(self._delete_item)
        self.buttonbox.accepted.connect(self.accept)
        self.buttonbox.rejected.connect(self.reject)
        self.datable = QtWidgets.QTableWidget()
        self._init_table()
        root_layout.addWidget(self.datable)
        root_layout.addWidget(self.buttonbox)
        self.datable.resizeColumnsToContents()
        self.datable.setSelectionBehavior(QtWidgets.QTableView.SelectRows)
        self.setLayout(root_layout)
        self.setWindowTitle('Edit config item')
        if not data:
            self._insert_item()

    def _init_table(self):
        """Init table for dict data"""
        self.datable.setColumnCount(2)
        self.datable.setHorizontalHeaderLabels(['Key', 'Value'])
        for k, (key, val) in enumerate(self.data.items()):
            key_txt, val_txt = repr(key), repr(val)
            self.datable.insertRow(k)
            self.datable.setItem(k, 0, QtWidgets.QTableWidgetItem(key_txt))
            self.datable.setItem(k, 1, QtWidgets.QTableWidgetItem(val_txt))

    def _insert_item(self):
        """Insert a new dict/list item at current position and start editing it"""
        pos = self.datable.currentRow()
        self.datable.insertRow(pos + 1)
        newitem = QtWidgets.QTableWidgetItem()
        self.datable.setItem(pos + 1, 0, newitem)
        self.datable.editItem(newitem)

    def _delete_item(self):
        """Delete dict/list item at current position"""
        pos = self.datable.currentRow()
        self.datable.removeRow(pos)

    def _collect_column(self, col):
        """Collect data from column col"""
        items = (self.datable.item(row, col) for row in range(self.datable.rowCount()))
        items = (it for it in items if it is not None)
        return (it.text() for it in items)

    def accept(self):
        """Do some sanity checks, close dialog if ok"""
        keys, vals = self._collect_column(0), self._collect_column(1)
        _text_data = {k: v for k, v in zip(keys, vals)}
        # keys and vals are now strings (hopefully) representing valid Python expressions
        # return a dict with the actual evaluated expressions
        _result = dict()
        for row, (key_txt, val_txt) in enumerate(_text_data.items(), 1):
            try:
                key = ast.literal_eval(key_txt)
                _result[key] = ast.literal_eval(val_txt)
            except (SyntaxError, ValueError):
                qt_message_dialog(
                    'Invalid input for item %s: %s on row %d\n'
                    'Inputs must be valid Python expressions (e.g. strings must be quoted).\n'
                    'Please fix before closing or cancel dialog'
                    % (key_txt, val_txt, row)
                )
                return
        self.data = _result
        self.done(QtWidgets.QDialog.Accepted)


class QCompoundEditorList(QCompoundEditorDict):
    """Compound editor for lists"""

    def _init_table(self):
        """Init table for list data"""
        self.datable.setColumnCount(1)
        self.datable.setHorizontalHeaderLabels(['Value'])
        for k, val in enumerate(self.data):
            val_txt = repr(val)
            self.datable.insertRow(k)
            self.datable.setItem(k, 0, QtWidgets.QTableWidgetItem(val_txt))

    def accept(self):
        """Do some sanity checks, close dialog if ok"""
        # list elements are now strings (hopefully) representing valid Python expressions
        # return a list with the actual evaluated expressions
        _text_data = list(self._collect_column(0))
        _result = list()
        for row, item_txt in enumerate(_text_data, 1):
            try:
                item = ast.literal_eval(item_txt)
                _result.append(item)
            except (SyntaxError, ValueError):
                qt_message_dialog(
                    'Invalid input for item %s on row %d.\n'
                    'Inputs must be valid Python expressions (e.g. strings must be quoted).\n'
                    'Please fix before closing or cancel dialog' % (item_txt, row)
                )
                return
        self.data = _result
        self.done(QtWidgets.QDialog.Accepted)


if __name__ == '__main__':
    app = QtWidgets.QApplication([])
    data = list('abcdef')
    data = {'a': 1, 'b': 2}
    # data = list(range(100))
    # data = ['Toe standing', 'Unipedal right', 'Unipedal left']
    data = {
        (7, 12): 'Z:\\PXD_files\\muscle_length_7_12.xlsx',
        (3, 6): 'Z:\\PXD_files\\muscle_length_3_6.xlsx',
        (13, 19): 'Z:\\PXD_files\\muscle_length_13_19.xlsx',
    }
    dlg = QCompoundEditorDict(data)
    data = [
        ['AnkleAnglesX', 'AnkleAnglesY', 'AnkleAnglesZ'],
        ['ForeFootAnglesX', 'ForeFootAnglesZ', 'ForeFootAnglesY'],
    ]
    data = []
    dlg = QCompoundEditorList(data)
    dlg.show()
    if dlg.exec_():
        print(dlg.data)
