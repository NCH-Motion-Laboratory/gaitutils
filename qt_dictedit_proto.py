"""
Prototype for a Qt list/dict editor

parameters: existing dict/list

-create scrollable area with as suitable amount of inputs for the dict/list
-use QFormLayout with labels and line edits (list) or two columns of line edits (dict)
-buttons: add / remove / cancel / ok


"""

from PyQt5 import QtWidgets


class QDictEditWindow(QtWidgets.QDialog):

    def __init__(self, data, parent=None):

        super(QDictEditWindow, self).__init__(parent=parent)
        box_layout = QtWidgets.QVBoxLayout()
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_contents = QtWidgets.QWidget()
        scroll.setWidget(scroll_contents)
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

        box_layout.addWidget(buttonbox)


        if isinstance(data, list):
            list_input = True
            data = {k: i for k, i in enumerate(data)}
        else:
            list_input = False
        for k, (key, val) in enumerate(data.items()):
            if list_input:
                grid_layout.addWidget(QtWidgets.QLabel(str(key)), k, 0)
            else:
                le_key = QtWidgets.QLineEdit()
                grid_layout.addWidget(le_key, k, 0)
                le_key.setText(str(key))
            le_val = QtWidgets.QLineEdit()
            grid_layout.addWidget(le_val, k, 1)
            le_val.setText(str(val))
        self.setLayout(box_layout)


if __name__ == '__main__':
    app = QtWidgets.QApplication([])
    data = list('abcdef')
    data = {'a': 1, 'b': 2}
    data = list(range(100))
    window = QDictEditWindow(data)
    window.show()
    app.exec_()