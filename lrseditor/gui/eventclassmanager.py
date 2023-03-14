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
from qgis.PyQt.QtWidgets import QApplication, QDialog, QHeaderView, QTableWidgetItem, QAbstractItemView, QMessageBox
from qgis.core import QgsProject

from ..utils.pg_conn import PGConn
from ..utils import qgis_utils
from ..gui.importevents import ImportEvents
from ..cls.lrsproject import LRSProject
from ..cls.lrseventclasses import LRSEventClasses

from ..gui.newevent import NewEvent

FORM_CLASS, _ = loadUiType(os.path.join(
    os.path.dirname(__file__), os.pardir, 'ui', 'eventclassmanager.ui'))


class EventClassManager(QDialog, FORM_CLASS):
    def __init__(self, iface):
        # call superclass constructor
        QDialog.__init__(self, parent=None)
        self.iface = iface
        self.canvas = iface.mapCanvas()
        # After self.setupUi() you can access any designer object by doing
        # self.<objectname>, and you can use autoconnect slots
        self.setupUi(self)
        self.pg_conn = None
        self.lrs_project = None
        self.lrs_event_classes = None

        # config table
        self.tableWidget.itemSelectionChanged.connect(self.selection_changed)
        self.tableWidget.setColumnCount(3)
        self.tableWidget.setHorizontalHeaderLabels(['Id', 'Type', 'Class Name'])
        self.header = self.tableWidget.horizontalHeader()
        # stretch columns
        self.header.setSectionResizeMode(2, QHeaderView.Stretch)
        # select only one row
        self.tableWidget.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tableWidget.setSelectionMode(QAbstractItemView.SingleSelection)
        # no editing
        self.tableWidget.setEditTriggers(QAbstractItemView.NoEditTriggers)

        # config buttons
        self.pb_delete.setEnabled(False)
        self.pb_add.setEnabled(False)
        self.pb_remove.setEnabled(False)
        self.pb_import.setEnabled(False)
        self.pb_delete.clicked.connect(self.event_class_delete)
        self.pb_new.clicked.connect(self.event_class_create)
        self.pb_add.clicked.connect(self.event_class_layers_add)
        self.pb_remove.clicked.connect(self.event_class_layers_remove)
        self.pb_import.clicked.connect(self.event_class_import)
        self.pb_close.clicked.connect(self.dialog_close)

        self.entries = qgis_utils.qgis_entries_get("project")
        if self.entries is None:
            self.pb_new.setEnabled(False)
            return

        conn_name = self.entries[0]
        self.schema = self.entries[3]

        self.credentials = qgis_utils.credentials_get(conn_name)
        if self.credentials is None:
            self.iface.messageBar().pushWarning("No Connection", "Missing credentials.")
            return

        self.pg_conn = PGConn(self.entries[1], self.entries[2], self.entries[4], self.credentials[0],
                              self.credentials[1])
        return_message = self.pg_conn.db_connect()
        if return_message:
            self.iface.messageBar().pushWarning("No Connection", "No connection established.")
            return

        self.lrs_project = LRSProject(self.pg_conn, self.schema)
        if not self.lrs_project:
            return

        self.lrs_event_classes = LRSEventClasses(self.pg_conn, self.schema, self.lrs_project.id)

        self.event_classes_get()

    def event_classes_get(self):
        # clear table, disable sorting temporarily
        self.tableWidget.setRowCount(0)
        self.tableWidget.setSortingEnabled(False)

        for clid in self.lrs_event_classes.event_class_idlist:
            row_position = self.tableWidget.rowCount()
            self.tableWidget.insertRow(row_position)
            iditem = QTableWidgetItem()
            # set numeric data for correct sorting
            iditem.setData(Qt.DisplayRole, clid)
            self.tableWidget.setItem(row_position, 0, iditem)
            if self.lrs_event_classes.event_class_types[clid] == "p":
                self.tableWidget.setItem(row_position, 1, QTableWidgetItem("Point Event Class"))
            elif self.lrs_event_classes.event_class_types[clid] == "c":
                self.tableWidget.setItem(row_position, 1, QTableWidgetItem("Continuous Event Class"))
            elif self.lrs_event_classes.event_class_types[clid] == "t":
                self.tableWidget.setItem(row_position, 1, QTableWidgetItem("Tour Event Class"))
            self.tableWidget.setItem(row_position, 2, QTableWidgetItem(self.lrs_event_classes.event_class_names[clid]))
        self.header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.header.setSectionResizeMode(1, QHeaderView.ResizeToContents)

        # enable sorting
        self.tableWidget.setSortingEnabled(True)

    def conn_close(self):
        if self.pg_conn:
            self.pg_conn.db_close()
            self.pg_conn = None

    def selection_changed(self):
        if len(self.tableWidget.selectionModel().selectedRows()) > 0:
            self.pb_delete.setEnabled(True)
            self.pb_add.setEnabled(True)
            self.pb_remove.setEnabled(True)
            self.pb_import.setEnabled(True)
        else:
            self.pb_delete.setEnabled(False)
            self.pb_add.setEnabled(False)
            self.pb_remove.setEnabled(False)
            self.pb_import.setEnabled(False)

    def selection_get(self):
        row_index = self.tableWidget.selectionModel().currentIndex().row()
        if row_index == -1:
            return None
        event_class_id = self.tableWidget.item(row_index, 0).text()
        event_class_type = self.tableWidget.item(row_index, 1).text()
        event_class_name = self.tableWidget.item(row_index, 2).text()
        return [event_class_id, event_class_type, event_class_name]

    def event_class_delete(self):
        row_values = self.selection_get()
        if row_values is None:
            return
        event_class_type = row_values[1][0].lower()
        event_class_name = row_values[2]
        event_class_id = int(row_values[0])

        layers_list = []
        if event_class_type == "c":
            v_layer = qgis_utils.layer_by_tablename_get(self.schema, "v_" + event_class_name)
            layer = qgis_utils.layer_by_tablename_get(self.schema, event_class_name)
            layers_list.extend([v_layer, layer])
        elif event_class_type == "p":
            layer = qgis_utils.layer_by_tablename_get(self.schema, event_class_name)
            layer_bp = qgis_utils.layer_by_tablename_get(self.schema, event_class_name + "_bp")
            layers_list.extend([layer, layer_bp])
        elif event_class_type == "t":
            layer = qgis_utils.layer_by_tablename_get(self.schema, event_class_name)
            layer_mt = qgis_utils.layer_by_tablename_get(self.schema, event_class_name + "_mt")
            v_layer = qgis_utils.layer_by_tablename_get(self.schema, "v_" + event_class_name)
            layers_list.extend([v_layer, layer, layer_mt])

        modifiers = QApplication.keyboardModifiers()
        if modifiers == Qt.ShiftModifier:
            # view must be in first position in layers_list
            if event_class_type != "p":
                if layers_list[0] is None:
                    self.pg_conn.view_drop(self.schema, "v_" + event_class_name)
                    msg = QMessageBox(QMessageBox.Information, "Drop View", "View 'v_" + event_class_name +
                                      "' deleted.", QMessageBox.Ok)
                    msg.exec_()
                else:
                    msg = QMessageBox(QMessageBox.Information, "Drop View", "Remove 'v_" + event_class_name +
                                      "' first.", QMessageBox.Ok)
                    msg.exec_()
        else:
            msg = QMessageBox()
            if all(layer is None for layer in layers_list):
                msg.setIcon(QMessageBox.Question)
                msg.setWindowTitle("Delete Event Class")
                msg.setText("Do you want to delete the Event Class '" + event_class_name + "'?")
                msg.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
                ret = msg.exec_()
                if ret == QMessageBox.Ok:
                    self.lrs_event_classes.event_class_delete(event_class_id)
                    self.event_classes_get()
            else:
                msg.setIcon(QMessageBox.Information)
                msg.setWindowTitle("Delete Event Class")
                msg.setText("Remove all layers of Event Class '" + event_class_name + "' first.")
                msg.setStandardButtons(QMessageBox.Ok)
                msg.exec_()

    def event_class_create(self):
        modifiers = QApplication.keyboardModifiers()
        if modifiers == Qt.ShiftModifier:
            row_values = self.selection_get()
            if row_values is not None:
                event_class_type = row_values[1][0].lower()
                event_class_name = row_values[2]
                if event_class_type != "p":
                    if event_class_type == "c":
                        self.pg_conn.cont_event_view_create(self.schema, event_class_name,
                                                            self.lrs_project.route_class_name, self.lrs_project.srid)
                    else:
                        self.pg_conn.tour_event_view_create(self.schema, event_class_name,
                                                            self.lrs_project.route_class_name, self.lrs_project.srid)
                    msg = QMessageBox(QMessageBox.Information, "Create View", "View 'v_" + event_class_name +
                                      "' created.", QMessageBox.Ok)
                    msg.exec_()
        else:
            dlg = NewEvent()
            dlg.exec_()
            if not dlg.data_get():
                return
            event_class_name, event_class_type, event_class_option = dlg.data_get()
            for key, val in self.lrs_event_classes.event_class_names.items():
                if val.lower() == event_class_name.lower():
                    msg = QMessageBox(QMessageBox.Critical, "New Event Class", "Event Class Name already exists.",
                                      QMessageBox.Ok)
                    msg.exec_()
                    return

            self.lrs_event_classes.event_class_create(event_class_name, event_class_type, event_class_option,
                                                      self.lrs_project.route_class_name)
            self.event_classes_get()

    def event_class_import(self):
        row_values = self.selection_get()
        if row_values is not None:
            event_class_type = row_values[1][0].lower()
            event_class_name = row_values[2]
            dlg = ImportEvents(self.iface, self.pg_conn, self.schema, event_class_name, event_class_type)
            dlg.setWindowTitle("Import Events into '" + event_class_name + "'")
            dlg.exec_()

    def event_class_layers_add(self):
        row_values = self.selection_get()
        if row_values is not None:
            event_class_type = row_values[1][0].lower()
            event_class_name = row_values[2]
            if event_class_type == "p":
                self.layer_add(event_class_name, "geom", ["id", "uuid", "name", "createtstz", "changetstz", "geomtstz"],
                               False)
                self.layer_add(event_class_name + "_bp", "geom", ["id", "uuid", "event_id", "azi", "route_id", "meas",
                               "apprtstz", "createtstz", "changetstz", "geomtstz"], False)
            if event_class_type == "c" or event_class_type == "t":
                modifiers = QApplication.keyboardModifiers()
                if modifiers == Qt.ShiftModifier:
                    # view is readonly, no need to set fields readonly
                    self.layer_add("v_" + event_class_name, "geom", [], True)
                else:
                    # view is readonly, no need to set fields readonly
                    self.layer_add("v_" + event_class_name, "geom", [], True)
                    self.layer_add(event_class_name, "geom", ["id", "uuid", "event_id", "azi", "route_id", "frommeas",
                                   "tomeas", "apprtstz", "createtstz", "changetstz", "geomtstz"], False)
                    if event_class_type == "t":
                        self.layer_add(event_class_name + "_mt", None, ["id", "uuid", "event_id", "route_id", "sortnr",
                                       "frommeas", "tomeas", "frompoint_id", "topoint_id", "routedir"], False)

    def event_class_layers_remove(self):
        row_values = self.selection_get()
        if row_values is not None:
            event_class_type = row_values[1][0].lower()
            event_class_name = row_values[2]
            if event_class_type == "p":
                self.layer_remove(event_class_name)
                self.layer_remove(event_class_name + "_bp")
            if event_class_type == "c" or event_class_type == "t":
                modifiers = QApplication.keyboardModifiers()
                if modifiers == Qt.ShiftModifier:
                    self.layer_remove("v_" + event_class_name)
                else:
                    self.layer_remove(event_class_name)
                    self.layer_remove("v_" + event_class_name)
                    if event_class_type == "t":
                        self.layer_remove(event_class_name + "_mt")

    def layer_remove(self, name):
        layer = qgis_utils.layer_by_tablename_get(self.schema, name)
        if layer is not None:
            QgsProject.instance().removeMapLayers([layer.id()])
            self.canvas.redrawAllLayers()

    def layer_add(self, name, geomfield, fields_readonly, layer_readonly):
        layer = qgis_utils.layer_create(self.entries, self.credentials, name, geomfield, layer_readonly,
                                        self.lrs_project.srid)
        if layer is not None:
            if not layer.isValid():
                msg = QMessageBox(QMessageBox.Critical, "Add Layer", "Layer " + name + " failed to load!",
                                  QMessageBox.Ok)
                msg.exec_()
                return
            else:
                qgis_utils.fields_readonly_set(layer, fields_readonly)
                QgsProject.instance().addMapLayer(layer)
                self.canvas.redrawAllLayers()
        else:
            msg = QMessageBox(QMessageBox.Critical, "Add Layer", "Layer " + name + " failed to add!",
                              QMessageBox.Ok)
            msg.exec_()

    def dialog_close(self):
        self.conn_close()
        self.reject()

    def closeEvent(self, event):
        # dialog closed with X-button
        # overrides method in QDialog
        self.dialog_close()
