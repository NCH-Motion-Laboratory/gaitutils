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


class QCompoundEditor(QtWidgets.QDialog):

    def __init__(self, data, key_hdr=None, val_hdr=None, parent=None):

        self.data = data
        self.is_list = isinstance(data, list)
        super(QCompoundEditor, self).__init__(parent=parent)
        # the root layout
        box_layout = QtWidgets.QVBoxLayout()
        # the scroll area
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        # we cannot directly add the layout to the scroll area, but have to
        # use a proxy widget that is a QWidget instance
        scroll_contents = QtWidgets.QWidget()
        scroll.setWidget(scroll_contents)
        #
        hdr_widget = QtWidgets.QWidget()
        hdr_grid = QtWidgets.QGridLayout(hdr_widget)
        hdr_grid.addWidget(QtWidgets.QLabel(key_hdr), 0, 0)
        hdr_grid.addWidget(QtWidgets.QLabel(val_hdr), 0, 1)

        box_layout.addWidget(hdr_widget)
        box_layout.addWidget(scroll)

        grid_layout = QtWidgets.QGridLayout(scroll_contents)

        std_buttons = QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        buttonbox = QtWidgets.QDialogButtonBox(std_buttons)

        add_button = QtWidgets.QPushButton('Add')
        del_button = QtWidgets.QPushButton('Delete')
        buttonbox.addButton(add_button, QtWidgets.QDialogButtonBox.ActionRole)
        buttonbox.addButton(del_button, QtWidgets.QDialogButtonBox.ActionRole)
        #loadButton.clicked.connect(self.load_config_dialog)
        #saveButton.clicked.connect(self.save_config_dialog)
        buttonbox.accepted.connect(self.accept)
        buttonbox.rejected.connect(self.reject)

        #box_layout.add
        box_layout.addWidget(buttonbox)

        # generate the grid layout from the input data
        if self.is_list:
            for k, item in enumerate(self.data):
                le_val = QtWidgets.QLineEdit()
                grid_layout.addWidget(le_val, k, 0)
                le_val.setText(str(item))
        else:  # dict
            for k, (key, val) in enumerate(self.data.items()):
                le_key = QtWidgets.QLineEdit()
                grid_layout.addWidget(le_key, k, 0)
                le_key.setText(str(key))
                le_val = QtWidgets.QLineEdit()
                grid_layout.addWidget(le_val, k, 1)
                le_val.setText(str(val))
        self.setLayout(box_layout)

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