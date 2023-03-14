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
from qgis.PyQt.QtWidgets import QDialog, QDialogButtonBox, QMessageBox

from ..utils.pg_conn import PGConn
from ..utils import qgis_utils
from ..gui.database import DBSettings
from ..cls.lrsproject import LRSProject
from ..cls.lrsbasesystem import LRSBasesystem

FORM_CLASS, _ = loadUiType(os.path.join(
    os.path.dirname(__file__), os.pardir, 'ui', 'basesystem.ui'))


class BaseSystemSettings(QDialog, FORM_CLASS):
    def __init__(self, iface):
        # call superclass constructor
        QDialog.__init__(self, parent=None)
        self.iface = iface
        # After self.setupUi() you can access any designer object by doing
        # self.<objectname>, and you can use autoconnect slots
        self.setupUi(self)

        self.pg_conn = None
        self.lrs_project = None
        self.schema_bs = None
        self.pg_conn_bs = None
        self.lrs_basesystem = None

        # clear combo boxes
        self.cbx_project_name.clear()
        self.cbx_base_class_name.clear()
        self.cbx_point_class_name.clear()

        # configure buttonBox
        self.buttonBox.rejected.disconnect()
        self.buttonBox.rejected.connect(self.rejected)
        self.button_apply = self.buttonBox.button(QDialogButtonBox.Apply)
        self.button_apply.clicked.connect(self.apply)
        self.button_apply.setEnabled(False)
        self.pb_conn.clicked.connect(self.conn_choose)

        self.form_update()

    def form_update(self):
        # project connection
        result = self.conn_get("project")
        if result is None:
            return
        _, schema, self.pg_conn = result[0], result[1], result[2]
        self.lrs_project = LRSProject(self.pg_conn, schema)
        if not self.lrs_project:
            return

        self.cbx_project_name.clear()
        self.cbx_project_name.addItem(self.lrs_project.name)

        # basesystem connection
        result = self.conn_get("basesystem")
        if result is None:
            return
        conn_name, self.schema_bs, self.pg_conn_bs = result[0], result[1], result[2]

        self.cbx_conn_name.clear()
        self.cbx_conn_name.addItem(conn_name)

        # fill combo boxes with table names
        # get only 2D-geom
        tablelist = self.pg_conn_bs.tablenames_geom_get(self.schema_bs, 2)
        self.cbx_base_class_name.clear()
        self.cbx_point_class_name.clear()
        for table in tablelist:
            if table[1].upper() == "LINESTRING":
                self.cbx_base_class_name.addItem(table[0])
            elif table[1].upper() == "POINT":
                self.cbx_point_class_name.addItem(table[0])

        self.base_class_fields_add()
        self.point_class_fields_add()

        self.lrs_basesystem = LRSBasesystem(self.pg_conn, schema, self.lrs_project.id, self.pg_conn_bs, self.schema_bs)
        if self.lrs_basesystem:
            self.le_basesystem_name.setText(self.lrs_basesystem.name)
            self.dsb_tolerance.setValue(self.lrs_basesystem.tolerance)

            self.cbx_base_class_name.setCurrentText(self.lrs_basesystem.base_class)
            self.base_class_fields_add()
            # add matching field names in combo box
            self.cbx_base_geom.setCurrentText(self.lrs_basesystem.base_geom_field)
            self.cbx_base_route_id.setCurrentText(self.lrs_basesystem.base_route_id_field)

            self.cbx_point_class_name.setCurrentText(self.lrs_basesystem.point_class)
            self.point_class_fields_add()
            # add matching field names in combo box
            self.cbx_point_geom.setCurrentText(self.lrs_basesystem.point_geom_field)
            self.cbx_point_route_id.setCurrentText(self.lrs_basesystem.point_route_id_field)
            self.cbx_point_sortnr.setCurrentText(self.lrs_basesystem.point_sortnr_field)
            self.cbx_point_type.setCurrentText(self.lrs_basesystem.point_type_field)

        # redirect changes in widgets after all combo boxes are filled
        self.cbx_base_class_name.currentTextChanged.connect(self.base_class_name_changed)
        self.cbx_point_class_name.currentTextChanged.connect(self.point_class_name_changed)

        self.button_apply.setEnabled(True)

    def conn_get(self, conn_type):
        entries = qgis_utils.qgis_entries_get(conn_type)
        if entries is None:
            return None
        conn_name = entries[0]
        schema = entries[3]
        credentials = qgis_utils.credentials_get(conn_name)
        if credentials is None:
            self.iface.messageBar().pushWarning("No Connection", "Missing credentials.")
            return None
        pg_conn = PGConn(entries[1], entries[2], entries[4], credentials[0], credentials[1])
        return_message = pg_conn.db_connect()
        if return_message:
            self.iface.messageBar().pushWarning("No Connection", "No connection established.")
            return None
        return conn_name, schema, pg_conn

    def conn_choose(self):
        dlg = DBSettings(self.iface, "basesystem")
        dlg.setWindowTitle("Base System Database Settings")
        dlg.gbox_settings.setTitle("Base System Database Settings")
        dlg.exec_()
        self.form_update()

    def base_class_name_changed(self):
        self.base_class_fields_add()

    def point_class_name_changed(self):
        self.point_class_fields_add()

    def base_class_fields_add(self):
        fields = self.pg_conn_bs.fieldnames_get(self.schema_bs, self.cbx_base_class_name.currentText())
        self.cbx_base_route_id.clear()
        for field in fields:
            if field[1] == 'string':
                self.cbx_base_route_id.addItem(field[0])

        fields_geom = self.pg_conn_bs.fieldnames_geom_get(self.schema_bs, self.cbx_base_class_name.currentText())
        self.cbx_base_geom.clear()
        for field_geom in fields_geom:
            self.cbx_base_geom.addItem(field_geom)

    def point_class_fields_add(self):
        self.cbx_point_route_id.clear()
        self.cbx_point_sortnr.clear()
        self.cbx_point_type.clear()
        fields = self.pg_conn_bs.fieldnames_get(self.schema_bs, self.cbx_point_class_name.currentText())
        for field in fields:
            if (field[1] == 'float') or (field[1] == 'integer'):
                self.cbx_point_sortnr.addItem(field[0])
                self.cbx_point_type.addItem(field[0])
            elif field[1] == 'string':
                self.cbx_point_route_id.addItem(field[0])

        fields_geom = self.pg_conn_bs.fieldnames_geom_get(self.schema_bs, self.cbx_point_class_name.currentText())
        self.cbx_point_geom.clear()
        for field_geom in fields_geom:
            self.cbx_point_geom.addItem(field_geom)

    def conn_close(self):
        if self.pg_conn_bs:
            self.pg_conn_bs.db_close()
            self.pg_conn_bs = None
        if self.pg_conn:
            self.pg_conn.db_close()
            self.pg_conn = None

    def apply(self):
        if self.dsb_tolerance.value() == 0.0:
            self.iface.messageBar().pushWarning("Missing Values", "Tolerance should not be 0.")
            return

        srid_bool = True
        if self.pg_conn_bs.srid_find(self.schema_bs, self.cbx_base_class_name.currentText(),
                                     self.cbx_base_geom.currentText()) != self.lrs_project.srid:
            srid_bool = False
        if self.pg_conn_bs.srid_find(self.schema_bs, self.cbx_point_class_name.currentText(),
                                     self.cbx_point_geom.currentText()) != self.lrs_project.srid:
            srid_bool = False

        if not srid_bool:
            msg = QMessageBox(QMessageBox.Critical, "CRS", "CRS of Base System does not match CRS of LRS-Project.",
                              QMessageBox.Ok)
            msg.exec_()
            return

        valuelist = [self.le_basesystem_name.text(), self.dsb_tolerance.value(),
                     self.cbx_base_class_name.currentText(), self.cbx_base_geom.currentText(),
                     self.cbx_base_route_id.currentText(),
                     self.cbx_point_class_name.currentText(), self.cbx_point_geom.currentText(),
                     self.cbx_point_route_id.currentText(),
                     self.cbx_point_sortnr.currentText(), self.cbx_point_type.currentText()]

        for val in valuelist:
            if val == '':
                self.iface.messageBar().pushWarning("Missing Values", "Missing values for LRS Base System.")
                return

        if not self.lrs_basesystem:
            self.lrs_basesystem.create(valuelist)
            self.iface.messageBar().pushMessage("Success", "New LRS Base System established.")
            self.rejected()
        else:
            self.lrs_basesystem.update(valuelist)

    def rejected(self):
        self.conn_close()
        self.reject()

    def closeEvent(self, event):
        # dialog closed with X-button
        # overrides method in QDialog
        self.rejected()
