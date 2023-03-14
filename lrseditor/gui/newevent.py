# -*- coding: utf-8 -*-
"""
/***************************************************************************
    name             :  LRS-Editor
    description      :  QGIS plugin for editing linear reference systems
    begin            :  2020-09-01
    copyright        :  (C) 2020 by Reto Meier (Holenstein Ingenieure AG)
    email            :  reto.meier@h-ing.ch
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""
import os
from qgis.PyQt.uic import loadUiType
from qgis.PyQt.QtWidgets import QDialog, QMessageBox

FORM_CLASS, _ = loadUiType(os.path.join(
    os.path.dirname(__file__), os.pardir, 'ui', 'newevent.ui'))


class NewEvent(QDialog, FORM_CLASS):
    def __init__(self):
        # call superclass constructor
        QDialog.__init__(self, parent=None)
        # After self.setupUi() you can access any designer object by doing
        # self.<objectname>, and you can use autoconnect slots
        self.setupUi(self)

        self.return_values = None
        self.event_class_type = "p"

        # clear combo box
        self.cbx_event_class_type.clear()
        self.cbx_event_class_type.addItem("Continuous Event Class", "c")
        self.cbx_event_class_type.addItem("Point Event Class", "p")
        self.cbx_event_class_type.addItem("Tour Event Class", "t")
        # redirect buttonbox
        self.buttonBox.rejected.disconnect()
        self.buttonBox.rejected.connect(self.rejected)
        self.buttonBox.accepted.disconnect()
        self.buttonBox.accepted.connect(self.accepted)

    def rejected(self):
        self.reject()

    def accepted(self):
        if self.le_event_class_name.text() == "":
            return
        # check for spaces in class name
        if ' ' in self.le_event_class_name.text():
            msg = QMessageBox(QMessageBox.Critical, "New Event Class", "No spaces in class names allowed.",
                              QMessageBox.Ok)
            msg.exec_()
            return

        # option is not in use, set it 0
        option = 0
        self.event_class_type = self.cbx_event_class_type.currentData()
        self.return_values = (self.le_event_class_name.text().lower(), self.event_class_type, option)
        self.accept()

    def data_get(self):
        return self.return_values
