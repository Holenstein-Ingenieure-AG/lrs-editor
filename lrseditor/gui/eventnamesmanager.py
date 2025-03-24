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

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.uic import loadUiType
from qgis.PyQt.QtWidgets import QDialog, QHeaderView, QTableWidgetItem, QAbstractItemView, QMessageBox, QInputDialog
from qgis.PyQt.QtWidgets import QLineEdit

FORM_CLASS, _ = loadUiType(os.path.join(
    os.path.dirname(__file__), os.pardir, 'ui', 'eventnamesmanager.ui'))


class EventNamesManager(QDialog, FORM_CLASS):
    def __init__(self, iface, event_names_class):
        # call superclass constructor
        QDialog.__init__(self, parent=None)
        self.iface = iface
        # After self.setupUi() you can access any designer object by doing
        # self.<objectname>, and you can use autoconnect slots
        self.setupUi(self)
        self.event_names_class = event_names_class
        self.event_class_name = event_names_class.event_class_name
        self.event_class_type = self.event_names_class.event_class_type
        self.selected_event_name = None
        self.selected_event_id = None

        # config buttons
        self.pb_add.setEnabled(True)
        self.pb_delete.setEnabled(False)
        self.pb_change.setEnabled(False)
        self.pb_close.setEnabled(True)
        self.pb_add.clicked.connect(self.event_name_add)
        self.pb_delete.clicked.connect(self.event_name_delete)
        self.pb_change.clicked.connect(self.event_name_change)
        self.pb_close.clicked.connect(self.dialog_close)

        # config table
        self.tableWidget.itemSelectionChanged.connect(self.selection_changed)
        self.header = self.tableWidget.horizontalHeader()
        if self.event_class_type == "c" or self.event_class_type == "t":
            self.tableWidget.setColumnCount(3)
            self.tableWidget.setHorizontalHeaderLabels(['Id', 'Used', 'Name'])
            self.header.setSectionResizeMode(2, QHeaderView.Stretch)
        elif self.event_class_type == "p":
            self.tableWidget.setColumnCount(4)
            self.tableWidget.setHorizontalHeaderLabels(['Id', 'Used', 'BP', 'Name'])
            # self.header.setSectionResizeMode(0, QHeaderView.Interactive)
            self.header.setSectionResizeMode(2, QHeaderView.Fixed)
            self.header.setSectionResizeMode(3, QHeaderView.Stretch)
        # select only one row
        self.tableWidget.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tableWidget.setSelectionMode(QAbstractItemView.SingleSelection)
        # no editing
        self.tableWidget.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.event_names_get()

    def event_names_get(self):
        # clear table, disable sorting temporarily
        self.tableWidget.setRowCount(0)
        self.tableWidget.setSortingEnabled(False)

        # sort dict by value case insensitive, but does not consider german umlauts...
        for key, val in sorted(self.event_names_class.event_names.items(), key=lambda x: x[1].lower()):
            row_position = self.tableWidget.rowCount()
            self.tableWidget.insertRow(row_position)
            iditem = QTableWidgetItem()
            # set numeric data for correct sorting
            iditem.setData(Qt.DisplayRole, int(key))
            self.tableWidget.setItem(row_position, 0, iditem)
            useditem = QTableWidgetItem()
            used_val = self.event_names_class.event_names_used[int(key)]
            # set numeric data for correct sorting
            useditem.setData(Qt.DisplayRole, int(used_val))
            self.tableWidget.setItem(row_position, 1, useditem)
            if self.event_class_type == "c" or self.event_class_type == "t":
                self.tableWidget.setItem(row_position, 2, QTableWidgetItem(val))
                # self.header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
                self.header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
            elif self.event_class_type == "p":
                # insert base point count
                bpitem = QTableWidgetItem()
                bp_count = self.event_names_class.event_bp_count[int(key)]
                # set numeric data for correct sorting
                bpitem.setData(Qt.DisplayRole, int(bp_count))
                self.tableWidget.setItem(row_position, 2, QTableWidgetItem(bpitem))
                self.tableWidget.setItem(row_position, 3, QTableWidgetItem(val))
                # self.header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
                self.header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
                self.header.setSectionResizeMode(2, QHeaderView.ResizeToContents)

        self.header.setSectionResizeMode(0, QHeaderView.Interactive)
        # enable sorting
        self.tableWidget.setSortingEnabled(True)

        # following sorting is slower:
        # self.tableWidget.sortItems(2, Qt.AscendingOrder)

    def selection_changed(self):
        if len(self.tableWidget.selectionModel().selectedRows()) > 0:
            self.pb_delete.setEnabled(True)
            self.pb_change.setEnabled(True)
            self.selection_get()
        else:
            self.pb_delete.setEnabled(False)
            self.pb_change.setEnabled(False)

    def selection_get(self):
        row_index = self.tableWidget.selectionModel().currentIndex().row()
        if row_index == -1:
            return None
        self.selected_event_id = self.tableWidget.item(row_index, 0).text()
        if self.event_class_type == "c" or self.event_class_type == "t":
            self.selected_event_name = self.tableWidget.item(row_index, 2).text()
        elif self.event_class_type == "p":
            self.selected_event_name = self.tableWidget.item(row_index, 3).text()

    def event_name_add(self):
        name_new, okpressed = QInputDialog.getText(self, "New Event Name", "Event Name:", QLineEdit.Normal, "")
        if not okpressed or name_new == '':
            return
        while self.name_exists(name_new):
            name_new, okpressed = QInputDialog.getText(self, "New Event Name", "Event Name:", QLineEdit.Normal,
                                                       name_new)
            if not okpressed or name_new == '':
                return
        try:
            self.event_names_class.event_name_add(name_new)
        except Exception as error:
            # insertion error, e.g. user-defined not-null-fields
            msg = QMessageBox(QMessageBox.Critical, "New Event Name", str(error), QMessageBox.Ok)
            msg.exec_()
        self.event_names_get()

    def event_name_delete(self):
        if int(self.event_names_class.event_names_used[int(self.selected_event_id)]) > 0:
            msg = QMessageBox(QMessageBox.Critical, "Delete Event Name",
                              "Event Name is in use and can not be deleted.", QMessageBox.Ok)
            msg.exec_()
            return
        # check first for existing tour layers
        if self.event_class_type == "t":
            viewname = "v_" + self.event_class_name + "_" + self.selected_event_id
            if self.event_names_class.event_view_exists(viewname):
                msg = QMessageBox(QMessageBox.Critical, "Delete Event Name",
                                  "Tour layer exists, Event Name can not be deleted.", QMessageBox.Ok)
                msg.exec_()
                return
        self.event_names_class.event_name_delete(self.selected_event_id)
        self.event_names_get()

    def event_name_change(self):
        name_new, okpressed = QInputDialog.getText(self, "Change Event Name", "Event Name:", QLineEdit.Normal,
                                                   self.selected_event_name)
        if not okpressed or name_new == '':
            return
        if self.name_exists(name_new):
            return
        self.event_names_class.event_name_change(name_new, self.selected_event_id)
        self.event_names_get()

    def name_exists(self, name_new):
        exists = False
        names_list = [val.lower() for val in self.event_names_class.event_names.values()]
        if name_new.lower() in names_list:
            msg = QMessageBox(QMessageBox.Critical, "New Event Name", "Event Name already exists.",
                              QMessageBox.Ok)
            msg.exec_()
            exists = True
        return exists

    def dialog_close(self):
        self.reject()

    def closeEvent(self, event):
        self.dialog_close()
