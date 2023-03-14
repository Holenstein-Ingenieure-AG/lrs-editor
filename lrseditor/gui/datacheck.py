# -*- coding: utf-8 -*-
"""
/***************************************************************************
    name             :  LRS-Editor
    description      :  QGIS plugin for editing linear reference systems
    begin            :  2021-12-14
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
import operator
import datetime

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.uic import loadUiType
from qgis.PyQt.QtWidgets import QDialog, QTreeWidgetItem, QDialogButtonBox, QMessageBox, QApplication
from qgis.core import QgsProject

from ..utils.pg_conn import PGConn
from ..utils import qgis_utils
from ..cls.lrsproject import LRSProject
from ..cls.lrseventclasses import LRSEventClasses
from ..cls.lrseventnamesclass import LRSEventNamesClass
from ..cls.lrspointeventclass import LRSPointEventClass
from ..cls.lrsconteventclass import LRSContEventClass
from ..cls.lrstoureventclass import LRSTourEventClass
from ..cls.lrscheckclass import LRSCheckClass

FORM_CLASS, _ = loadUiType(os.path.join(
    os.path.dirname(__file__), os.pardir, 'ui', 'datacheck.ui'))


class DataCheck(QDialog, FORM_CLASS):
    def __init__(self, iface):
        # call superclass constructor
        QDialog.__init__(self, parent=None)
        self.iface = iface
        self.canvas = iface.mapCanvas()
        # After self.setupUi() you can access any designer object by doing
        # self.<objectname>, and you can use autoconnect slots
        self.setupUi(self)

        # configure buttonBox
        self.buttonBox.rejected.disconnect()
        self.buttonBox.rejected.connect(self.rejected)
        self.button_apply = self.buttonBox.button(QDialogButtonBox.Apply)
        self.button_apply.clicked.connect(self.apply)
        self.button_apply.setEnabled(False)
        self.pb_add.clicked.connect(self.layer_add)
        self.pb_add.setEnabled(False)

        # textEdit/progressBar
        self.textEdit.setReadOnly(True)
        self.progressBar.setValue(0)
        self.progress_step = 0

        self.entries = qgis_utils.qgis_entries_get("project")
        if self.entries is None:
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

        self.lrs_project = LRSProject(self.pg_conn, self.entries[3])
        if not self.lrs_project:
            return

        # redirect changes in widgets after combo box is filled
        self.cbx_event_class_name.currentTextChanged.connect(self.event_class_changed)
        self.treeWidget.itemChanged.connect(self.selection_changed)

        self.items_c = ["Routes without Events", "Event Measures", "Unused Event Names",
                        "Event Name References", "Event Point not on Route"]
        self.items_p = ["Events without Base Points", "Unused Event Names",
                        "Base Points without Event", "Base Point not on Route"]
        self.items_t = ["Event Measures", "Unused Event Names",
                        "Event Name References",
                        "Missing Event Point", "Event Point not on Route"]
        self.checkdict = {}
        self.checks_add()

        self.lrs_event_classes = LRSEventClasses(self.pg_conn, self.entries[3], self.lrs_project.id)
        # no event classes to check
        if len(self.lrs_event_classes.event_class_types) == 0:
            return
        self.event_classes_get()

        self.button_apply.setEnabled(True)
        self.lrs_check_class = LRSCheckClass(self.pg_conn, self.schema, self.lrs_project.srid)
        if self.lrs_check_class.exists:
            self.pb_add.setEnabled(True)
        else:
            self.pb_add.setEnabled(False)

    def event_classes_get(self):
        # clear table
        self.cbx_event_class_name.clear()
        event_classes = []

        for clid in self.lrs_event_classes.event_class_idlist:
            if self.lrs_event_classes.event_class_types[clid] == "p":
                event_classes.append([self.lrs_event_classes.event_class_names[clid], "p"])
            elif self.lrs_event_classes.event_class_types[clid] == "c":
                event_classes.append([self.lrs_event_classes.event_class_names[clid], "c"])
            elif self.lrs_event_classes.event_class_types[clid] == "t":
                event_classes.append([self.lrs_event_classes.event_class_names[clid], "t"])

        event_classes.sort(key=operator.itemgetter(0))
        event_classes.insert(0, ["<All Event Classes>", "a"])

        for event_class in event_classes:
            self.cbx_event_class_name.addItem(event_class[0], event_class[1])

    def event_class_changed(self):
        self.checks_add()

    def checks_add(self):
        # emit no signal as long as treewidget is reorganised
        self.treeWidget.blockSignals(True)
        event_class_type = self.cbx_event_class_name.currentData()
        if event_class_type == "c":
            itemsdict = {"Continuous Event Class": self.items_c}
            self.checkdict = {event_class_type: self.items_c.copy()}
        elif event_class_type == "p":
            itemsdict = {"Point Event Class": self.items_p}
            self.checkdict = {event_class_type: self.items_p.copy()}
        elif event_class_type == "t":
            itemsdict = {"Tour Event Class": self.items_t}
            self.checkdict = {event_class_type: self.items_t.copy()}
        else:
            itemsdict = {"Continuous Event Class": self.items_c,
                         "Point Event Class": self.items_p,
                         "Tour Event Class": self.items_t}
            self.checkdict = {"c": self.items_c.copy(),
                              "p": self.items_p.copy(),
                              "t": self.items_t.copy()}

        self.treeWidget.setColumnCount(1)
        self.treeWidget.setHeaderLabels(["Choose Data Checks:"])
        self.treeWidget.clear()

        for key, val in itemsdict.items():
            parent = QTreeWidgetItem(self.treeWidget)
            parent.setText(0, str(key))
            parent.setFlags(parent.flags() | Qt.ItemIsAutoTristate | Qt.ItemIsUserCheckable)
            for check in val:
                child = QTreeWidgetItem(parent)
                child.setText(0, str(check))
                child.setFlags(child.flags() | Qt.ItemIsUserCheckable)
                child.setCheckState(0, Qt.Checked)

        self.treeWidget.expandAll()
        # allow signals, when item is changed
        self.treeWidget.blockSignals(False)

    def selection_changed(self, item, column):
        # get only child items
        if not item.parent() is None:
            # event type
            parent_type = item.parent().text(column)[:1].lower()
            # remove unchecked
            if item.checkState(column) == 0:
                try:
                    tmplist = self.checkdict.get(parent_type)
                    tmplist.remove(item.text(column))
                except ValueError:
                    pass
            # append checked
            if item.checkState(column) == 2:
                try:
                    tmplist = self.checkdict.get(parent_type)
                    tmplist.append(item.text(column))
                except ValueError:
                    pass

            isempty = 0
            for key, val in self.checkdict.items():
                isempty = isempty + len(val)
            if isempty == 0:
                self.button_apply.setEnabled(False)
            else:
                self.button_apply.setEnabled(True)

    def apply(self):
        self.progressBar.setValue(0)
        self.progressBar.setMaximum(100)
        self.textEdit.clear()
        now = datetime.datetime.now()
        self.textEdit.append("Check Start: " + now.strftime("%Y-%m-%d %H:%M:%S"))

        self.textEdit.append("...Get all Routes...")
        QApplication.processEvents()
        group = "route_id, name"
        routelist = self.pg_conn.table_select_group(self.schema, self.lrs_project.route_class_name,
                                                    "route_id, name", group, None, "name")
        tolerance = self.lrs_project.tolerance
        event_class_type = self.cbx_event_class_name.currentData()
        route_class_name = self.lrs_project.route_class_name

        self.lrs_check_class.truncate()
        if event_class_type == "a":
            # calculate the steps of the progressbar
            count_c = len(self.checkdict.get("c"))
            progress_max = count_c * self.lrs_event_classes.event_classes_stat()[0]
            count_p = len(self.checkdict.get("p"))
            progress_max = progress_max + count_p * self.lrs_event_classes.event_classes_stat()[1]
            count_t = len(self.checkdict.get("t"))
            progress_max = progress_max + count_t * self.lrs_event_classes.event_classes_stat()[2]
            self.progress_step = int((1*100)/progress_max)
            for clid in self.lrs_event_classes.event_class_idlist:
                event_class_name = self.lrs_event_classes.event_class_names[clid]
                layer = qgis_utils.layer_by_tablename_get(self.schema, event_class_name)
                if layer is None:
                    self.textEdit.append("Layer " + event_class_name + " not found.")
                    QApplication.processEvents()
                    break
                if self.lrs_event_classes.event_class_types[clid] == "c":
                    self.cont_event_class_check(layer, event_class_name, routelist, tolerance, route_class_name)
                elif self.lrs_event_classes.event_class_types[clid] == "p":
                    self.point_event_class_check(layer, event_class_name, tolerance, route_class_name)
                elif self.lrs_event_classes.event_class_types[clid] == "t":
                    self.tour_event_class_check(layer, event_class_name, routelist, tolerance, route_class_name)
        else:
            event_class_name = self.cbx_event_class_name.currentText()
            layer = qgis_utils.layer_by_tablename_get(self.schema, event_class_name)
            if layer is None:
                self.textEdit.append("Layer " + event_class_name + " not found.")
                QApplication.processEvents()
                QApplication.restoreOverrideCursor()
                return
            if event_class_type == "c":
                count_c = len(self.checkdict.get("c"))
                self.progress_step = int((1*100)/count_c)
                self.cont_event_class_check(layer, event_class_name, routelist, tolerance, route_class_name)
            elif event_class_type == "p":
                count_p = len(self.checkdict.get("p"))
                self.progress_step = int((1*100)/count_p)
                self.point_event_class_check(layer, event_class_name, tolerance, route_class_name)
            elif event_class_type == "t":
                count_t = len(self.checkdict.get("t"))
                self.progress_step = int((1*100)/count_t)
                self.tour_event_class_check(layer, event_class_name, routelist, tolerance, route_class_name)

        self.progressBar.setValue(100)
        self.textEdit.append("Check Errors: " + str(self.lrs_check_class.err_count))
        self.textEdit.append("Check Infos: " + str(self.lrs_check_class.info_count))
        now = datetime.datetime.now()
        self.textEdit.append("Check End: " + now.strftime("%Y-%m-%d %H:%M:%S"))
        self.pb_add.setEnabled(True)
        self.canvas.redrawAllLayers()
        # restore after multiple overrides
        while QApplication.overrideCursor() is not None:
            QApplication.restoreOverrideCursor()

    def cont_event_class_check(self, layer, event_class_name, routelist, tolerance, route_class_name):
        lrs_layer = LRSContEventClass(self.pg_conn, self.schema, layer)
        tmplist = self.checkdict.get("c")
        QApplication.setOverrideCursor(Qt.WaitCursor)
        self.textEdit.append("Check " + event_class_name + ":")
        QApplication.processEvents()
        for check in tmplist:
            if check == "Routes without Events":
                self.textEdit.append("..." + check + "...")
                QApplication.processEvents()
                for route in routelist:
                    result = lrs_layer.events_meas_check(route[0], tolerance, route_class_name)
                    if result is None:
                        self.lrs_check_class.insert(event_class_name, "INFO", "Route without Events.",
                                                    None, None, route[1])
                self.progressBar.setValue(self.progressBar.value() + self.progress_step)
            if check == "Event Measures":
                self.textEdit.append("..." + check + "...")
                QApplication.processEvents()
                for route in routelist:
                    result = lrs_layer.events_meas_check(route[0], tolerance, route_class_name)
                    if result is not None:
                        for val in result[0]:
                            self.lrs_check_class.insert(event_class_name, "ERROR", "Measures are not continuous.",
                                                        val[4], val[1], route[1])
                        if not result[1]:
                            self.lrs_check_class.insert(event_class_name, "ERROR", "First measure is not 0.",
                                                        None, None, route[1])
                        if not result[2]:
                            self.lrs_check_class.insert(event_class_name, "ERROR",
                                                        "Last measure does not match route length.",
                                                        None, None, route[1])
                self.progressBar.setValue(self.progressBar.value() + self.progress_step)
            if check == "Unused Event Names":
                self.textEdit.append("..." + check + "...")
                QApplication.processEvents()
                event_names_class = LRSEventNamesClass(self.pg_conn, self.schema, event_class_name, "c")
                for key, val in event_names_class.event_names_used.items():
                    if val == 0:
                        event_name = event_names_class.event_name_get(key)
                        self.lrs_check_class.insert(event_class_name, "INFO",
                                                    "Event Name " + event_name + " not in use.", None, None, None)
                self.progressBar.setValue(self.progressBar.value() + self.progress_step)
            if check == "Event Name References":
                self.textEdit.append("..." + check + "...")
                QApplication.processEvents()
                event_names_class = LRSEventNamesClass(self.pg_conn, self.schema, event_class_name, "c")
                result = event_names_class.event_names_unreferenced()
                if len(result) > 0:
                    for val in result:
                        self.lrs_check_class.insert(event_class_name, "ERROR", "Event " + val[0] +
                                                    " can not be found in Event Name Table.", val[1], None, None)
                self.progressBar.setValue(self.progressBar.value() + self.progress_step)
            if check == "Event Point not on Route":
                self.textEdit.append("..." + check + "...")
                QApplication.processEvents()
                fields = "a.uuid, a.geom, b.name"
                group = "a.uuid, a.geom, b.name"
                result = self.pg_conn.point_within1(self.schema, event_class_name, route_class_name, fields,
                                                    "geom", "geom", tolerance, "route_id", "route_id", group)
                for event in result:
                    if not event[3]:
                        self.lrs_check_class.insert(event_class_name, "ERROR", "Event Point not on Route.",
                                                    event[1], event[0], event[2])
                self.progressBar.setValue(self.progressBar.value() + self.progress_step)

    def point_event_class_check(self, layer, event_class_name, tolerance, route_class_name):
        lrs_layer = LRSPointEventClass(self.pg_conn, self.schema, layer)
        tmplist = self.checkdict.get("p")
        QApplication.setOverrideCursor(Qt.WaitCursor)
        self.textEdit.append("Check " + event_class_name + ":")
        QApplication.processEvents()
        for check in tmplist:
            if check == "Events without Base Points":
                self.textEdit.append("..." + check + "...")
                QApplication.processEvents()
                for key, val in lrs_layer.event_bp_count.items():
                    if val == 0:
                        event_name = lrs_layer.event_names[key]
                        event_uuid = lrs_layer.event_uuid_get(key)
                        self.lrs_check_class.insert(event_class_name, "INFO", "Event " + event_name +
                                                    " without Basepoints.", None, event_uuid, None)
                self.progressBar.setValue(self.progressBar.value() + self.progress_step)
            if check == "Unused Event Names":
                self.textEdit.append("..." + check + "...")
                QApplication.processEvents()
                for key, val in lrs_layer.event_names_used.items():
                    if val == 0:
                        event_name = lrs_layer.event_names[key]
                        event_uuid = lrs_layer.event_uuid_get(key)
                        self.lrs_check_class.insert(event_class_name, "INFO", "Event " + event_name +
                                                    " not in use.", None, event_uuid, None)
                self.progressBar.setValue(self.progressBar.value() + self.progress_step)
            if check == "Base Points without Event":
                self.textEdit.append("..." + check + "...")
                QApplication.processEvents()
                result = lrs_layer.event_names_unreferenced()
                for basepoint in result:
                    self.lrs_check_class.insert(event_class_name, "ERROR", "Base Point without Event.",
                                                basepoint[1], basepoint[0], None)
                self.progressBar.setValue(self.progressBar.value() + self.progress_step)
            if check == "Base Point not on Route":
                self.textEdit.append("..." + check + "...")
                QApplication.processEvents()
                fields = "a.uuid, a.geom, b.name"
                group = "a.uuid, a.geom, b.name"
                result = self.pg_conn.point_within1(self.schema, event_class_name + "_bp", route_class_name, fields,
                                                    "geom", "geom", tolerance, "route_id", "route_id", group)
                for event in result:
                    if not event[3]:
                        self.lrs_check_class.insert(event_class_name, "ERROR", "Base Point not on Route.",
                                                    event[1], event[0], event[2])
                self.progressBar.setValue(self.progressBar.value() + self.progress_step)

    def tour_event_class_check(self, layer, event_class_name, routelist, tolerance, route_class_name):
        lrs_layer = LRSTourEventClass(self.pg_conn, self.schema, layer)
        tmplist = self.checkdict.get("t")
        QApplication.setOverrideCursor(Qt.WaitCursor)
        self.textEdit.append("Check " + event_class_name + ":")
        QApplication.processEvents()
        for check in tmplist:
            if check == "Event Measures":
                self.textEdit.append("..." + check + "...")
                QApplication.processEvents()
                for route in routelist:
                    result = lrs_layer.events_meas_check(route[0], tolerance)
                    if result is not None:
                        for val in result:
                            self.lrs_check_class.insert(event_class_name, "ERROR", "Event measures are not correct.",
                                                        val[4], val[3], route[1])
                self.progressBar.setValue(self.progressBar.value() + self.progress_step)
            if check == "Unused Event Names":
                self.textEdit.append("..." + check + "...")
                QApplication.processEvents()
                event_names_class = LRSEventNamesClass(self.pg_conn, self.schema, event_class_name, "t")
                for key, val in event_names_class.event_names_used.items():
                    if val == 0:
                        event_name = event_names_class.event_name_get(key)
                        self.lrs_check_class.insert(event_class_name, "INFO",
                                                    "Event Name " + event_name + " not in use.", None, None, None)
                self.progressBar.setValue(self.progressBar.value() + self.progress_step)
            if check == "Event Name References":
                self.textEdit.append("..." + check + "...")
                QApplication.processEvents()
                event_names_class = LRSEventNamesClass(self.pg_conn, self.schema, event_class_name, "t")
                result = event_names_class.event_names_unreferenced()
                if len(result) > 0:
                    for val in result:
                        self.lrs_check_class.insert(event_class_name, "ERROR", "Event " + val[0] +
                                                    " can not be found in Event Name Table.", None, val[1], None)
                self.progressBar.setValue(self.progressBar.value() + self.progress_step)
            if check == "Missing Event Point":
                self.textEdit.append("..." + check + "...")
                QApplication.processEvents()
                result = lrs_layer.event_point_check()
                if len(result) > 0:
                    for val in result:
                        self.lrs_check_class.insert(event_class_name, "ERROR", val[0] + " Event Point " + val[2] +
                                                    " can not be found in Tour Event Table.", None, val[1], None)
                self.progressBar.setValue(self.progressBar.value() + self.progress_step)
            if check == "Event Point not on Route":
                self.textEdit.append("..." + check + "...")
                QApplication.processEvents()
                fields = "b.uuid, b.geom, c.name"
                group = "b.uuid, b.geom, c.name"
                where = "(a.frompoint_id = b.uuid or a.topoint_id = b.uuid) and a.route_id = c.route_id"
                result = self.pg_conn.point_within2(self.schema, event_class_name + "_mt", event_class_name,
                                                    route_class_name, fields, "geom", "geom", tolerance,
                                                    where, group)
                for event in result:
                    if not event[3]:
                        self.lrs_check_class.insert(event_class_name, "ERROR", "Event Point not on Route.",
                                                    event[1], event[0], event[2])
                self.progressBar.setValue(self.progressBar.value() + self.progress_step)

    def layer_add(self):
        layer = qgis_utils.layer_create(self.entries, self.credentials, "lrs_check_class", "geom", False,
                                        self.lrs_project.srid, False)
        if not layer.isValid():
            msg = QMessageBox(QMessageBox.Critical, "Data Check", "Layer lrs_check_class failed to load!",
                              QMessageBox.Ok)
            msg.exec_()
            return
        else:
            qgis_utils.fields_readonly_set(layer, ["id", "class_name", "uuid", "name", "category", "route_name",
                                                   "description"])
            QgsProject.instance().addMapLayer(layer)
            self.canvas.redrawAllLayers()

    def conn_close(self):
        if self.pg_conn:
            self.pg_conn.db_close()
            self.pg_conn = None

    def rejected(self):
        self.conn_close()
        self.reject()
