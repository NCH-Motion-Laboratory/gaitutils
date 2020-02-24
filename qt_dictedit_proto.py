"""
Prototype for a Qt list/dict editor

parameters: existing dict/list


TODO:
    add dynamic headers (e.g. 'age range' and 'file' for age-specific normal data)
    add option to use a file browser button instead of string editor (for dicts/lists of files)
    lists are ordered, so maybe should have numbers on left column
    use QListView instead of a grid layout?

"""

from PyQt5 import QtWidgets
from PyQt5.QtWidgets import QDialogButtonBox, QPushButton


class QCompoundEditor(QtWidgets.QDialog):

    def __init__(self, data, key_hdr=None, val_hdr=None, parent=None):        
        super(QCompoundEditor, self).__init__(parent=parent)
        root_layout = QtWidgets.QVBoxLayout()
        self.datable = QtWidgets.QTableWidget()
        self.data = data
        self.list_mode = isinstance(data, list)
        self.buttonbox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        insertbutton = QPushButton('Insert')
        deletebutton = QPushButton('Delete')
        self.buttonbox.addButton(insertbutton, QDialogButtonBox.ActionRole)
        self.buttonbox.addButton(deletebutton, QDialogButtonBox.ActionRole)
        self.datable = QtWidgets.QTableWidget()
        if self.list_mode:
            self._init_for_list()
        else:
            self._init_for_dict()
        root_layout.addWidget(self.datable)
        root_layout.addWidget(self.buttonbox)
        self.datable.resizeColumnsToContents()
        self.datable.setSelectionBehavior(QtWidgets.QTableView.SelectRows)
        self.setLayout(root_layout)

    def _init_for_dict(self):
        self.datable.setColumnCount(2)
        self.datable.setHorizontalHeaderLabels(['Key', 'Value'])
        for k, (key, val) in enumerate(data.items()):
            key = str(key)
            self.datable.insertRow(k)
            self.datable.setItem(k, 0, QtWidgets.QTableWidgetItem(key))
            self.datable.setItem(k, 1, QtWidgets.QTableWidgetItem(val))

    def _init_for_list(self):
        self.datable.setColumnCount(1)
        self.datable.setHorizontalHeaderLabels(['Value'])
        for k, val in enumerate(data):
            key = str(key)
            self.datable.insertRow(k)
            self.datable.setItem(k, 0, QtWidgets.QTableWidgetItem(val))

    def _add_item(self):
        """Add a new dict/list item"""
        pass


if __name__ == '__main__':
    app = QtWidgets.QApplication([])
    data = list('abcdef')
    data = {'a': 1, 'b': 2}
    #data = list(range(100))
    #data = ['Toe standing', 'Unipedal right', 'Unipedal left']
    data = {(7, 12): 'Z:\\PXD_files\\muscle_length_7_12.xlsx', (3, 6): 'Z:\\PXD_files\\muscle_length_3_6.xlsx', (13, 19): 'Z:\\PXD_files\\muscle_length_13_19.xlsx'}
    #data = [['AnkleAnglesX', 'AnkleAnglesY', 'AnkleAnglesZ'], ['ForeFootAnglesX', 'ForeFootAnglesZ', 'ForeFootAnglesY']]
    window = QCompoundEditor(data, key_hdr='Key', val_hdr='Value')
    window.show()
    app.exec_()