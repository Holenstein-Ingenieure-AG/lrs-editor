# -*- coding: utf-8 -*-
"""
/***************************************************************************
    name             :  LRS-Editor
    description      :  QGIS plugin for editing linear reference systems
    begin            :  2022-01-27
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
import datetime

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import QDialog, QHeaderView, QDialogButtonBox, QTableWidgetItem, QAbstractItemView
from qgis.PyQt.QtWidgets import QMessageBox, QApplication
from qgis.PyQt.uic import loadUiType
from qgis.core import QgsPointXY, QgsPoint

from ..utils import qgis_utils
from ..utils.pg_conn import PGConn
from ..gui.database import DBSettings
from ..cls.lrsproject import LRSProject
from ..cls.lrsrouteclass import LRSRouteClass
from ..cls.lrseventnamesclass import LRSEventNamesClass
from ..cls.lrspointeventclass import LRSPointEventClass
from ..cls.lrsbasepointeventclass import LRSBasePointEventClass
from ..cls.lrsconteventclass import LRSContEventClass
from ..cls.lrstoureventclass import LRSTourEventClass

FORM_CLASS, _ = loadUiType(os.path.join(
    os.path.dirname(__file__), os.pardir, 'ui', 'importevents.ui'))
# prevent inserting in wrong fields
EXCLUDE_FIELDNAME = ["id", "geom", "uuid", "name", "createtstz", "changetstz", "geomtstz", "event_id", "azi",
                     "route_id", "frommeas", "tomeas", "apprtstz", "sortnr", "frompoint_id", "topoint_id", "routedir"]


class ImportEvents(QDialog, FORM_CLASS):
    def __init__(self, iface, pg_conn, schema, event_class_name, event_class_type):
        # call superclass constructor
        QDialog.__init__(self, parent=None)
        self.iface = iface
        self.canvas = iface.mapCanvas()
        # After self.setupUi() you can access any designer object by doing
        # self.<objectname>, and you can use autoconnect slots
        self.setupUi(self)

        self.pg_conn = pg_conn
        self.schema = schema
        self.lrs_project = None
        self.route_class = None
        self.srid = None
        self.tol = None
        self.event_class_name = event_class_name
        self.event_class_type = event_class_type
        self.schema_ip = None
        self.pg_conn_ip = None
        self.fields = None
        self.class_name = None
        self.geom_field = None
        self.route_id_field = None
        self.event_names_field = None
        self.sortnr_field = None

        # configure buttonBox
        self.buttonBox.rejected.disconnect()
        self.buttonBox.rejected.connect(self.rejected)
        self.buttonBox.rejected.disconnect()
        self.buttonBox.rejected.connect(self.rejected)
        self.button_apply = self.buttonBox.button(QDialogButtonBox.Apply)
        self.button_apply.clicked.connect(self.apply)
        self.button_apply.setEnabled(False)

        if self.event_class_type == "t":
            self.cbx_sortnr.setEnabled(True)
            self.lbl_sortnr.setDisabled(False)
        else:
            self.cbx_sortnr.setEnabled(False)
            self.lbl_sortnr.setDisabled(True)

        # textEdit
        self.textEdit.setReadOnly(True)
        self.lbl_processing.setText("")
        self.pb_conn.clicked.connect(self.conn_choose)

        # config table
        self.tableWidget.setColumnCount(2)
        self.tableWidget.setHorizontalHeaderLabels(['Source Field', 'Target Field'])
        self.header = self.tableWidget.horizontalHeader()
        # stretch columns
        self.header.setSectionResizeMode(0, QHeaderView.Stretch)
        # no editing
        self.tableWidget.setEditTriggers(QAbstractItemView.NoEditTriggers)

    def form_update(self):
        # fill combo boxes with table names
        # get only 2D-geom
        tablelist = self.pg_conn_ip.tablenames_geom_get(self.schema_ip, 2)
        self.cbx_class_name.clear()
        for tablename in tablelist:
            if self.event_class_type == "p":
                if tablename[1].upper() == "POINT":
                    self.cbx_class_name.addItem(tablename[0])
            else:
                if tablename[1].upper() == "LINESTRING":
                    self.cbx_class_name.addItem(tablename[0])

        self.class_fields_add()
        self.cbx_class_name.currentTextChanged.connect(self.class_name_changed)
        self.button_apply.setEnabled(True)

    def class_name_changed(self):
        self.class_fields_add()

    def class_fields_add(self):
        class_name = self.cbx_class_name.currentText()
        fields = self.pg_conn_ip.fieldnames_get(self.schema_ip, class_name)
        self.cbx_route_id.clear()
        self.cbx_event_names.clear()
        self.cbx_sortnr.clear()
        if self.event_class_type == "t":
            self.cbx_sortnr.addItem("<None>")
        # clear table
        self.tableWidget.setRowCount(0)

        for count, field in enumerate(fields):
            fieldname = field[0]
            field_type = field[1]
            if field_type == 'string':
                self.cbx_route_id.addItem(fieldname)
                self.cbx_event_names.addItem(fieldname)
            if field_type != 'other':
                row_position = self.tableWidget.rowCount()
                self.tableWidget.insertRow(row_position)
                chkboxitem = QTableWidgetItem()
                chkboxitem.setText(fieldname)
                if self.event_class_type == "t":
                    result = self.pg_conn.field_exists(self.schema, self.event_class_name + "_mt", fieldname)
                else:
                    result = self.pg_conn.field_exists(self.schema, self.event_class_name, fieldname)
                if result and fieldname not in EXCLUDE_FIELDNAME:
                    textitem = QTableWidgetItem(fieldname)
                    self.tableWidget.setItem(row_position, 1, textitem)
                    chkboxitem.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
                elif result and fieldname in EXCLUDE_FIELDNAME:
                    textitem = QTableWidgetItem("-- Locked --")
                    self.tableWidget.setItem(row_position, 1, textitem)
                    chkboxitem.setFlags(Qt.NoItemFlags)
                else:
                    textitem = QTableWidgetItem("-- Not Available --")
                    self.tableWidget.setItem(row_position, 1, textitem)
                    chkboxitem.setFlags(Qt.NoItemFlags)
                chkboxitem.setCheckState(Qt.Unchecked)
                self.tableWidget.setItem(row_position, 0, chkboxitem)
            if self.event_class_type == "t":
                if (field_type == 'float') or (field_type == 'integer'):
                    self.cbx_sortnr.addItem(fieldname)

        self.header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.tableWidget.setSelectionMode(QAbstractItemView.NoSelection)

        fields_geom = self.pg_conn_ip.fieldnames_geom_get(self.schema_ip, class_name)
        self.cbx_geom.clear()
        for field_geom in fields_geom:
            self.cbx_geom.addItem(field_geom)

    def conn_choose(self):
        dlg = DBSettings(self.iface, None)
        dlg.setWindowTitle("Database Connections")
        dlg.gbox_settings.setTitle("Database Settings")
        dlg.exec_()
        if not dlg.data_get():
            return
        else:
            conn_name, dbname, host, self.schema_ip, port = dlg.data_get()
            credentials = qgis_utils.credentials_get(conn_name)
            if credentials is None:
                self.iface.messageBar().pushWarning("No Connection", "Missing credentials.")
                return None
            self.pg_conn_ip = PGConn(dbname, host, port, credentials[0], credentials[1])
            return_message = self.pg_conn_ip.db_connect()
            if return_message:
                self.iface.messageBar().pushWarning("No Connection", "No connection established.")
                return None
            self.cbx_conn_name.clear()
            self.cbx_conn_name.addItem(conn_name)
            self.form_update()

    def apply(self):
        valuelist = [self.cbx_class_name.currentText(), self.cbx_geom.currentText(),
                     self.cbx_route_id.currentText(), self.cbx_event_names.currentText()]

        for val in valuelist:
            if val == '':
                self.iface.messageBar().pushWarning("Missing Values", "Missing values for import.")
                return

        self.class_name = valuelist[0]
        self.geom_field = valuelist[1]
        self.route_id_field = valuelist[2]
        self.event_names_field = valuelist[3]
        self.sortnr_field = self.cbx_sortnr.currentText()

        self.lrs_project = LRSProject(self.pg_conn, self.schema)
        self.srid, self.tol = self.lrs_project.srid, self.lrs_project.tolerance
        self.route_class = LRSRouteClass(self.pg_conn, self.schema, self.lrs_project.route_class_name)

        if not self.pg_conn_ip.srid_find(self.schema_ip, self.class_name, self.geom_field) == self.srid:
            msg = QMessageBox(QMessageBox.Information, "LRS-Editor", "SRID of class '" + self.class_name + "' "
                              "does not match SRID of LRS-Project", QMessageBox.Ok)
            msg.exec_()
            self.textEdit.append("Import aborted.")
            return

        self.textEdit.clear()
        now = datetime.datetime.now()
        self.textEdit.append("Import into Event Class '" + self.event_class_name + "'")
        self.textEdit.append("Import Start: " + now.strftime("%Y-%m-%d %H:%M:%S"))

        self.fields = []
        for i in range(self.tableWidget.rowCount()):
            if self.tableWidget.item(i, 0).checkState() == Qt.Checked:
                fieldname = self.tableWidget.item(i, 0).text()
                if not self.field_type_check(fieldname):
                    msg = QMessageBox(QMessageBox.Information, "LRS-Editor", "Field Type of '" + fieldname + "' is "
                                      "different in source and target. Import failed.", QMessageBox.Ok)
                    msg.exec_()
                    self.textEdit.append("Import aborted.")
                    return
                else:
                    self.fields.append(fieldname)

        layer = qgis_utils.layer_by_tablename_get(self.schema, self.event_class_name)
        if not layer:
            self.textEdit.append("Missing layer of Event Class '" + self.event_class_name + "' in project. "
                                                                                            "Import failed.")
            return

        if self.event_class_type == "c":
            self.cont_event_import(layer)
        elif self.event_class_type == "p":
            self.point_event_import(layer)
        elif self.event_class_type == "t":
            self.tour_event_import(layer)

        QApplication.restoreOverrideCursor()
        self.canvas.redrawAllLayers()
        now = datetime.datetime.now()
        self.textEdit.append("Import End: " + now.strftime("%Y-%m-%d %H:%M:%S"))
        self.lbl_processing.setText("")

    def field_type_check(self, fieldname):
        if self.event_class_type == "t":
            target_field_type = self.pg_conn.field_type_get(self.schema, self.event_class_name + "_mt", fieldname)[0]
        else:
            target_field_type = self.pg_conn.field_type_get(self.schema, self.event_class_name, fieldname)[0]
        source_field_type = self.pg_conn_ip.field_type_get(self.schema_ip, self.class_name, fieldname)[0]
        if target_field_type != source_field_type:
            return False
        else:
            return True

    def field_null_check(self, tablename, fieldname):
        where = fieldname + " IS NULL"
        result = self.pg_conn_ip.table_select(self.schema_ip, tablename, fieldname, where)
        if len(result) > 0:
            return True
        else:
            return False

    def tables_truncate(self, tables_list):
        msg = QMessageBox(QMessageBox.Question, "LRS-Editor", "Event Class '" + self.event_class_name +
                          "' is not empty. Do you want to remove all data first?",
                          QMessageBox.Yes | QMessageBox.No)
        ret = msg.exec_()
        if ret == QMessageBox.Yes:
            self.textEdit.append("...Removing data of existing Event Class...")
            QApplication.processEvents()
            for tablename in tables_list:
                self.pg_conn.table_truncate(self.schema, tablename)
            return True
        else:
            self.textEdit.append("Import aborted.")
            return False

    def tour_event_import(self, layer):
        event_names_class = LRSEventNamesClass(self.pg_conn, self.schema, self.event_class_name, "t")
        lrs_layer = LRSTourEventClass(self.pg_conn, self.schema, layer)
        layer_mt = qgis_utils.layer_by_tablename_get(self.schema, self.event_class_name + "_mt")

        if not layer_mt:
            msg = QMessageBox(QMessageBox.Information, "LRS-Editor", "Layer '" + self.event_class_name + "_mt' is "
                              "missing. Import failed.", QMessageBox.Ok)
            msg.exec_()
            self.textEdit.append("Import aborted.")
            return

        # check for NULL-values
        self.textEdit.append("...Checking NULL values...")
        QApplication.processEvents()
        event_name_null = self.field_null_check(self.class_name, self.event_names_field)
        if event_name_null:
            self.textEdit.append("There are NULL values in field '" + self.event_names_field +"'. Import aborted.")
        route_id_null = self.field_null_check(self.class_name, self.route_id_field)
        if route_id_null:
            self.textEdit.append("There are NULL values in field '" + self.route_id_field +"'. Import aborted.")
        sortnr_null = False
        if self.sortnr_field != "<None>":
            sortnr_null = self.field_null_check(self.class_name, self.sortnr_field)
            if sortnr_null:
                self.textEdit.append("There are NULL values in field '" + self.sortnr_field +"'. Import aborted.")
        if event_name_null or route_id_null or sortnr_null:
            QApplication.processEvents()
            return

        # truncate tables
        table_et_name = self.event_class_name + "_et"
        table_mt_name = self.event_class_name + "_mt"
        cont_count = len(self.pg_conn.table_select_group(self.schema, self.event_class_name, "COUNT(id)", "id"))
        cont_et_count = len(self.pg_conn.table_select_group(self.schema, table_et_name, "COUNT(id)", "id"))
        if cont_count > 0 or cont_et_count > 0:
            if not self.tables_truncate([self.event_class_name, table_et_name, table_mt_name]):
                return

        QApplication.setOverrideCursor(Qt.WaitCursor)

        # insert event_names
        # get all unique event names
        event_names = self.pg_conn_ip.table_select_group(self.schema_ip, self.class_name, self.event_names_field,
                                                         self.event_names_field, None, self.event_names_field)
        self.textEdit.append("...Import Event Names...")
        QApplication.processEvents()
        for event_name in event_names:
            event_names_class.event_name_add(event_name[0])

        # get all unique routes
        self.textEdit.append("...Get all Routes to process...")
        QApplication.processEvents()
        routelist = self.pg_conn_ip.table_select_group(self.schema_ip, self.class_name, self.route_id_field,
                                                       self.route_id_field, None, self.route_id_field)
        total_routes = len(routelist)
        for count1, route in enumerate(routelist):
            self.lbl_processing.setText("Processing Route: " + str(count1 + 1) + " / " + str(total_routes))
            QApplication.processEvents()
            route_name = route[0]
            route_id = self.route_class.route_id_get(route_name)
            if route_id is None:
                # route does not exists in routeclass
                self.textEdit.append("...Route '" + route_name + "' not found...")
                QApplication.processEvents()
                continue
            where = self.route_id_field + " = '" + route_name + "'"
            if self.sortnr_field != "<None>":
                fields = ''.join((self.event_names_field, ", ", self.sortnr_field))
                order = ''.join((self.event_names_field, " ASC, ", self.sortnr_field, " ASC"))
            else:
                fields = self.event_names_field
                order = self.event_names_field + " ASC"
            # add fields for the additional values to import
            for field in self.fields:
                fields = fields + ", " + field

            nodelist = self.pg_conn_ip.linestring_nodes_get(self.schema_ip, self.class_name, self.geom_field,
                                                            fields, where, order)
            # iterate every linestring
            event_uuid_old = ""
            # toursortnr = 1
            for nodes in nodelist:
                tour_name = nodes[4]
                event_uuid = event_names_class.event_uuid_get(event_names_class.event_id_get(tour_name))
                qgis_point_fi = QgsPointXY(nodes[0], nodes[1])
                qgis_point_se = QgsPointXY(nodes[2], nodes[3])
                if self.sortnr_field != "<None>":
                    toursortnr = int(nodes[5])
                    # up to version 1.3.1:
                    # if event_uuid == event_uuid_old:
                    #     toursortnr = toursortnr + 1
                    # else:
                    #     toursortnr = 1
                else:
                    if event_uuid == event_uuid_old:
                        self.textEdit.append("...Tour '" + tour_name + "' has more than one part. "
                                                                       "Missing Sort Number...")
                        QApplication.processEvents()
                    toursortnr = 1
                # create list of additional values to import
                valuelist = []
                for i in range(len(self.fields)):
                    if self.sortnr_field != "<None>":
                        value = nodes[6 + i]
                    else:
                        value = nodes[5 + i]
                    if len(str(value)) > 0:
                        valuelist.append(value)
                    else:
                        valuelist.append(None)

                lrs_layer.event_sql_insert(qgis_point_fi, qgis_point_se, event_uuid, route_id, self.route_class,
                                           toursortnr, self.srid, self.fields, valuelist)
                event_uuid_old = event_uuid

    def point_event_import(self, layer):
        lrs_layer = LRSPointEventClass(self.pg_conn, self.schema, layer)
        layer_bp = qgis_utils.layer_by_tablename_get(self.schema, self.event_class_name + "_bp")
        lrs_layer_bp = LRSBasePointEventClass(self.pg_conn, self.schema, layer_bp)

        if not layer_bp:
            msg = QMessageBox(QMessageBox.Information, "LRS-Editor", "Layer '" + self.event_class_name + "_bp' is "
                                                       "missing. Import failed.", QMessageBox.Ok)
            msg.exec_()
            self.textEdit.append("Import aborted.")
            return

        # check for NULL-values
        self.textEdit.append("...Checking NULL values...")
        QApplication.processEvents()
        event_name_null = self.field_null_check(self.class_name, self.event_names_field)
        if event_name_null:
            self.textEdit.append("There are NULL values in field '" + self.event_names_field +"'. Import aborted.")
        route_id_null = self.field_null_check(self.class_name, self.route_id_field)
        if route_id_null:
            self.textEdit.append("There are NULL values in field '" + self.route_id_field +"'. Import aborted.")
        if event_name_null or route_id_null:
            QApplication.processEvents()
            return

        # truncate tables
        events_count = len(self.pg_conn.table_select_group(self.schema, self.event_class_name, "COUNT(id)", "id"))
        if events_count > 0:
            if not self.tables_truncate([self.event_class_name, lrs_layer_bp.event_class_name]):
                return

        QApplication.setOverrideCursor(Qt.WaitCursor)
        fields = ''.join((self.event_names_field, ", ", self.route_id_field, ", ",
                          "ST_AsText(" + self.geom_field + ")"))
        # add fields for the additional values to import
        for field in self.fields:
            fields = fields + ", " + field
        order = self.event_names_field + " ASC, " + self.route_id_field + " ASC"
        pointlist = self.pg_conn_ip.table_select(self.schema_ip, self.class_name, fields, None, order)

        total_points = len(pointlist)
        event_name_old = ""
        route_name_old = ""
        qgis_point_old = None
        event_uuid_old = ""
        event_uuid = ""
        for count1, event_point in enumerate(pointlist):
            self.lbl_processing.setText("Processing Event Point: " + str(count1 + 1) + " / " + str(total_points))
            QApplication.processEvents()
            route_name = event_point[1]
            route_id = self.route_class.route_id_get(route_name)
            if route_id is None:
                # route does not exists in routeclass
                self.textEdit.append("...Route '" + route_name + "' not found...")
                QApplication.processEvents()
                continue
            event_name = event_point[0]
            qgis_point = QgsPoint()
            qgis_point.fromWkt(event_point[2])
            if event_name == event_name_old:
                if route_name == route_name_old:
                    # event point with same event_name and route_name as last one
                    self.textEdit.append("...Event Name '" + event_name + "' skipped, already references '"
                                         + route_name + "'")
                    QApplication.processEvents()
                    continue
                else:
                    # insert additional basepoint, no insert of event point
                    # geometry taken from last event point (points with more than one basepoint must overlap)
                    if qgis_point_old is not None:
                        self.textEdit.append("...Event Name '" + event_name + "' already exists, reference added "
                                             "with '"+ route_name + "'.")
                        QApplication.processEvents()
                        result = self.route_class.point_meas_get(route_id, qgis_point_old, self.srid)
                        lrs_layer_bp.basepoint_sql_insert(result[0], route_id, event_uuid_old, result[1],
                                                          result[2], self.srid)
            else:
                # create list of additional values to import
                valuelist = []
                for i in range(len(self.fields)):
                    value = event_point[3 + i]
                    if len(str(value)) > 0:
                        valuelist.append(value)
                    else:
                        valuelist.append(None)
                event_id = lrs_layer.event_sql_insert(event_name, qgis_point, self.srid, self.fields, valuelist)
                event_uuid = lrs_layer.event_uuid_get(event_id)
                result = self.route_class.point_meas_get(route_id, qgis_point, self.srid)
                lrs_layer_bp.basepoint_sql_insert(result[0], route_id, event_uuid, result[1], result[2], self.srid)

            event_uuid_old = event_uuid
            qgis_point_old = qgis_point
            route_name_old = route_name
            event_name_old = event_name

    def cont_event_import(self, layer):
        # check for NULL-values
        self.textEdit.append("...Checking NULL values...")
        QApplication.processEvents()
        event_name_null = self.field_null_check(self.class_name, self.event_names_field)
        if event_name_null:
            self.textEdit.append("There are NULL values in field '" + self.event_names_field +"'. Import aborted.")
        route_id_null = self.field_null_check(self.class_name, self.route_id_field)
        if route_id_null:
            self.textEdit.append("There are NULL values in field '" + self.route_id_field +"'. Import aborted.")
        if event_name_null or route_id_null:
            QApplication.processEvents()
            return

        event_names_class = LRSEventNamesClass(self.pg_conn, self.schema, self.event_class_name, "c")
        lrs_layer = LRSContEventClass(self.pg_conn, self.schema, layer)

        # truncate tables
        table_et_name = self.event_class_name + "_et"
        cont_count = len(self.pg_conn.table_select_group(self.schema, self.event_class_name, "COUNT(id)", "id"))
        cont_et_count = len(self.pg_conn.table_select_group(self.schema, table_et_name, "COUNT(id)", "id"))
        if cont_count > 0 or cont_et_count > 0:
            if not self.tables_truncate([self.event_class_name, table_et_name]):
                return

        QApplication.setOverrideCursor(Qt.WaitCursor)

        # insert n/a and event_names
        # get all unique event names
        event_names = self.pg_conn_ip.table_select_group(self.schema_ip, self.class_name, self.event_names_field,
                                                         self.event_names_field, None, self.event_names_field)
        self.textEdit.append("...Import Event Names...")
        QApplication.processEvents()
        event_names_class.event_name_add("n/a")
        for event_name in event_names:
            event_names_class.event_name_add(event_name[0])

        # get all unique routes
        self.textEdit.append("...Get all Routes to process...")
        QApplication.processEvents()
        routelist = self.pg_conn_ip.table_select_group(self.schema_ip, self.class_name, self.route_id_field,
                                                       self.route_id_field, None, self.route_id_field)
        nodelist_sorted = []
        total_routes = len(routelist)
        for count1, route in enumerate(routelist):
            self.lbl_processing.setText("Processing Route: " + str(count1 + 1) + " / " + str(total_routes))
            QApplication.processEvents()
            route_name = route[0]
            route_id = self.route_class.route_id_get(route_name)
            if route_id is None:
                # route does not exists in routeclass
                self.textEdit.append("...Route '" + route_name + "' not found...")
                QApplication.processEvents()
                continue
            route_length = self.route_class.route_length_get(route_id)
            where = self.route_id_field + " = '" + route_name + "'"
            fields = self.event_names_field
            # add fields for the additional values to import
            for field in self.fields:
                fields = fields + ", " + field
            nodelist = self.pg_conn_ip.linestring_nodes_get(self.schema_ip, self.class_name, self.geom_field,
                                                            fields, where)
            nodelist_sorted[:] = []
            # iterate every linestring, sort nodes of linestrings (meas asc)
            for nodes in nodelist:
                event_uuid = event_names_class.event_uuid_get(event_names_class.event_id_get(nodes[4]))
                # create list of additional values to import
                valuelist = []
                for i in range(len(self.fields)):
                    value = nodes[5 + i]
                    if len(str(value)) > 0:
                        valuelist.append(value)
                    else:
                        valuelist.append(None)
                result_start = self.route_class.point_meas_get(route_id, QgsPointXY(nodes[0], nodes[1]), self.srid)
                result_start.append(event_uuid)
                result_start.extend(valuelist)
                result_end = self.route_class.point_meas_get(route_id, QgsPointXY(nodes[2], nodes[3]), self.srid)
                result_end.append(event_uuid)
                result_end.extend(valuelist)
                if result_start[1] < result_end[1]:
                    # linestring in route direction
                    meas_next = result_start[1]
                else:
                    # linestring in opposite direction
                    meas_next = result_end[1]
                ind = 0
                # get position to insert meas asc
                for value in nodelist_sorted:
                    meas = value[1]
                    if meas_next < meas:
                        break
                    ind = ind + 1
                # insert
                if result_start[1] < result_end[1]:
                    # linestring in route direction
                    nodelist_sorted.insert(ind, result_start)
                    nodelist_sorted.insert(ind + 1, result_end)
                else:
                    # linestring in opposite direction -> change
                    nodelist_sorted.insert(ind, result_end)
                    nodelist_sorted.insert(ind + 1, result_start)

            tomeas_old = 0.0
            # exceptional handling for closed, single linestrings
            if len(nodelist_sorted) == 2:
                node_fi, node_se = nodelist_sorted[0], nodelist_sorted[1]
                meas_start = node_fi[1]
                meas_end = node_se[1]
                if abs(meas_start - meas_end) <= self.tol:
                    # create list of additional values to import
                    values = []
                    for i in range(len(self.fields)):
                        values.append(nodelist_sorted[0][4 + i])
                    result = self.route_class.point_routeend_get(route_id)
                    lrs_layer.event_sql_insert(result[0], node_fi[3], result[2], route_id,
                                               0.0, result[1], self.srid, self.fields, values)
                    # prevent executing following for-loop
                    nodelist_sorted = []
                    tomeas_old = route_length

            # count = even -> start point of linestring
            # count = odd -> end point of linestring
            for count2, nodes_sorted in enumerate(nodelist_sorted):
                meas = nodes_sorted[1]
                # create list of additional values to import
                values = []
                for i in range(len(self.fields)):
                    values.append(nodes_sorted[4 + i])
                if count2 == 0 and meas > self.tol:
                    # start point is not at route start
                    event_uuid = event_names_class.event_uuid_get(event_names_class.event_id_get("n/a"))
                    lrs_layer.event_sql_insert(nodes_sorted[0], event_uuid, nodes_sorted[2], route_id, 0.0,
                                               meas, self.srid, [], [])
                else:
                    # ignore start point smaller than tol
                    if abs(meas - tomeas_old) > self.tol:
                        # check if point is at route end
                        if abs(route_length - meas) > self.tol:
                            if count2 % 2 == 0:
                                # even
                                event_uuid = event_names_class.event_uuid_get(event_names_class.event_id_get("n/a"))
                                lrs_layer.event_sql_insert(nodes_sorted[0], event_uuid, nodes_sorted[2], route_id,
                                                           tomeas_old, meas, self.srid, [], [])
                            else:
                                # odd
                                lrs_layer.event_sql_insert(nodes_sorted[0], nodes_sorted[3], nodes_sorted[2], route_id,
                                                           tomeas_old, meas, self.srid, self.fields, values)
                        else:
                            # move last point to route end
                            result = self.route_class.point_routeend_get(route_id)
                            lrs_layer.event_sql_insert(result[0], nodes_sorted[3], result[2], route_id,
                                                       tomeas_old, result[1], self.srid, self.fields, values)

                # move first meas to route start
                if meas <= self.tol:
                    tomeas_old = 0.0
                else:
                    tomeas_old = meas

            # insert point at route end, if missing
            if abs(route_length - tomeas_old) > self.tol:
                result = self.route_class.point_routeend_get(route_id)
                event_uuid = event_names_class.event_uuid_get(event_names_class.event_id_get("n/a"))
                lrs_layer.event_sql_insert(result[0], event_uuid, result[2], route_id, tomeas_old, result[1],
                                           self.srid, [], [])

        self.cont_event_no_routes_create()

    def cont_event_no_routes_create(self):
        # keep this in an own function to start it independently
        layer = qgis_utils.layer_by_tablename_get(self.schema, self.event_class_name)
        if not layer:
            self.textEdit.append("Missing layer of Event Class '" + self.event_class_name + "' in project. "
                                                                                            "Import failed.")
            return

        lrs_project = LRSProject(self.pg_conn, self.schema)
        group = "route_id, name"
        routelist_all = self.pg_conn.table_select_group(self.schema, lrs_project.route_class_name,
                                                        "route_id, name", group, None, "name")
        group = "route_id"
        routelist_event_class = self.pg_conn.table_select_group(self.schema, self.event_class_name,
                                                                "route_id", group, None, "route_id")
        # convert into set
        routeset_all = set(route[0] for route in routelist_all)
        routeset_event_class = set(route[0] for route in routelist_event_class)
        # compare, get differences -> routes without events
        routeset_na = routeset_all.difference(routeset_event_class)

        QApplication.restoreOverrideCursor()
        if len(routeset_na) > 0:
            msg = QMessageBox(QMessageBox.Question, "LRS-Editor", "There are Routes without Events. Do you want to set"
                              " 'n/a' for these Routes?", QMessageBox.Yes | QMessageBox.No)
            ret = msg.exec_()
            if ret != QMessageBox.Yes:
                return
        QApplication.setOverrideCursor(Qt.WaitCursor)

        lrs_layer = LRSContEventClass(self.pg_conn, self.schema, layer)
        route_class = LRSRouteClass(self.pg_conn, self.schema, lrs_project.route_class_name)
        event_names_class = LRSEventNamesClass(self.pg_conn, self.schema, self.event_class_name, "c")
        event_uuid = event_names_class.event_uuid_get(event_names_class.event_id_get("n/a"))
        for route_id in routeset_na:
            result = route_class.point_routeend_get(route_id)
            lrs_layer.event_sql_insert(result[0], event_uuid, result[2], route_id, 0.0, result[1],
                                       self.srid, [], [])

    def conn_close(self):
        # do not close self.pg_conn, was imported from eventclassmanager
        if self.pg_conn_ip:
            self.pg_conn_ip.db_close()
            self.pg_conn_ip = None

    def rejected(self):
        self.conn_close()
        self.reject()

    def closeEvent(self, event):
        # dialog closed with X-button
        # overrides method in QDialog
        self.rejected()
