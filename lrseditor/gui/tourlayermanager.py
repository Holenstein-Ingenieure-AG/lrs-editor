# -*- coding: utf-8 -*-
"""
/***************************************************************************
    name             :  LRS-Editor
    description      :  QGIS plugin for editing linear reference systems
    begin            :  2024-09-05
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
from qgis.PyQt.QtWidgets import QDialog, QHeaderView, QAbstractItemView, QTableWidgetItem, QMessageBox
from qgis.core import QgsMapLayer, QgsProject

from ..utils import qgis_utils

FORM_CLASS, _ = loadUiType(os.path.join(
    os.path.dirname(__file__), os.pardir, 'ui', 'tourlayermanager.ui'))

class TourLayerManager(QDialog, FORM_CLASS):
    def __init__(self, iface, pg_conn, schema, lrs_project, event_names_class, entries, credentials):
        # call superclass constructor
        QDialog.__init__(self, parent=None)
        self.iface = iface
        self.canvas = iface.mapCanvas()
        # After self.setupUi() you can access any designer object by doing
        # self.<objectname>, and you can use autoconnect slots
        self.setupUi(self)
        self.pg_conn = pg_conn
        self.schema = schema
        self.lrs_project = lrs_project
        self.event_names_class = event_names_class
        self.event_class_name = event_names_class.event_class_name
        self.entries = entries
        self.credentials = credentials

        # config table
        self.tableWidget.itemSelectionChanged.connect(self.selection_changed)
        self.tableWidget.setColumnCount(2)
        self.tableWidget.setHorizontalHeaderLabels(['Id', 'Name'])
        self.header = self.tableWidget.horizontalHeader()
        # stretch columns
        self.header.setSectionResizeMode(1, QHeaderView.Stretch)
        # select multiple rows
        self.tableWidget.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tableWidget.setSelectionMode(QAbstractItemView.MultiSelection)
        # no editing
        self.tableWidget.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.event_names_get()

        # config buttons
        self.pb_create.setEnabled(False)
        self.pb_delete.setEnabled(False)
        self.pb_close.clicked.connect(self.dialog_close)
        self.pb_create.clicked.connect(self.tour_layer_create)
        self.pb_delete.clicked.connect(self.tour_layer_delete)

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
            self.tableWidget.setItem(row_position, 1, QTableWidgetItem(val))
            self.header.setSectionResizeMode(1, QHeaderView.ResizeToContents)

        self.header.setSectionResizeMode(0, QHeaderView.Interactive)
        # enable sorting
        self.tableWidget.setSortingEnabled(True)

        # following sorting is slower:
        # self.tableWidget.sortItems(2, Qt.AscendingOrder)

    def selection_changed(self):
        if len(self.tableWidget.selectionModel().selectedRows()) > 0:
            self.pb_create.setEnabled(True)
            self.pb_delete.setEnabled(True)
        else:
            self.pb_create.setEnabled(False)
            self.pb_delete.setEnabled(False)

    def tour_layer_create(self):
        indexes = self.tableWidget.selectionModel().selectedRows()
        for index in indexes:
            event_name = self.tableWidget.item(index.row(), 1).text()
            event_id = self.tableWidget.item(index.row(), 0).text()
            self.pg_conn.tour_view_create(self.schema, self.event_class_name, self.lrs_project.route_class_name,
                                          event_id, self.lrs_project.srid)
            layername = "v_" + self.event_class_name + "_" + event_id
            layer = qgis_utils.layer_create(self.entries, self.credentials, layername, "geom", True,
                                            self.lrs_project.srid)
            layer.setName(event_name)
            if layer is not None:
                if not layer.isValid():
                    msg = QMessageBox(QMessageBox.Critical, "Create Layer", "Layer " + event_name + " failed to load!",
                                      QMessageBox.Ok)
                    msg.exec_()
                    return
                else:
                    QgsProject.instance().addMapLayer(layer)
                    self.canvas.redrawAllLayers()
            else:
                msg = QMessageBox(QMessageBox.Critical, "Create Layer", "Layer " + event_name + " failed to create!",
                                  QMessageBox.Ok)
                msg.exec_()

    def tour_layer_delete(self):
        indexes = self.tableWidget.selectionModel().selectedRows()
        # unique view names in a set
        view_set = set()
        for index in indexes:
            event_name = self.tableWidget.item(index.row(), 1).text()
            event_id = self.tableWidget.item(index.row(), 0).text()
            layername = "v_" + self.event_class_name + "_" + event_id
            layers = QgsProject.instance().mapLayers().values()
            for layer in layers:
                if layer.type() == QgsMapLayer.VectorLayer:
                    if layer.name() == event_name:
                        QgsProject.instance().removeMapLayers([layer.id()])
                        self.canvas.redrawAllLayers()
                        view_set.add(layername)

        # drop tour view
        if len(view_set) > 0:
            for view in view_set:
                self.pg_conn.view_drop(self.schema, view)

    def dialog_close(self):
        # do not close self.pg_conn, was imported from eventclassmanager
        self.reject()

    def closeEvent(self, event):
        self.dialog_close()