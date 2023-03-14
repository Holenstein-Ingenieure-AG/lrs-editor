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
from qgis.PyQt.QtWidgets import QDialog, QDialogButtonBox

from qgis.core import QgsProject

from ..utils.pg_conn import PGConn
from ..utils import qgis_utils

FORM_CLASS, _ = loadUiType(os.path.join(
    os.path.dirname(__file__), os.pardir, 'ui', 'database.ui'))


class DBSettings(QDialog, FORM_CLASS):
    def __init__(self, iface, conn_type):
        # call superclass constructor
        QDialog.__init__(self, parent=None)
        self.iface = iface
        self.conn_type = conn_type
        # After self.setupUi() you can access any designer object by doing
        # self.<objectname>, and you can use autoconnect slots
        self.setupUi(self)

        self.conn_name = None
        self.dbname = None
        self.schema = None
        self.host = None
        self.port = None
        self.user = None
        self.passwd = None
        self.pg_conn = None
        self.proj = QgsProject.instance()
        self.return_values = None

        # clear combo boxes
        self.cbx_type.clear()
        self.cbx_type.addItem('PostgreSQL/PostGIS', 'pg')
        self.cbx_schema.clear()

        # configure buttonBox
        self.buttonBox.rejected.disconnect()
        self.buttonBox.rejected.connect(self.rejected)
        self.button_apply = self.buttonBox.button(QDialogButtonBox.Apply)
        self.button_apply.clicked.connect(self.apply)

        self.button_apply.setEnabled(False)

        # get connections
        self.cbx_conn_name.clear()
        conn_name_list = qgis_utils.connection_names_get()
        if not conn_name_list:
            self.iface.messageBar().pushWarning("No Connection", "Create a connection in QGIS.")
            self.pb_connect.setEnabled(False)
            return
        else:
            for conn_name in conn_name_list:
                self.cbx_conn_name.addItem(conn_name)
                self.pb_connect.setEnabled(True)

        if self.conn_type is not None:
            entries = qgis_utils.qgis_entries_get(self.conn_type)
            if entries is not None:
                self.conn_name = entries[0]
                self.dbname = entries[1]
                self.host = entries[2]
                self.schema = entries[3]
                self.port = entries[4]
                self.cbx_conn_name.setCurrentText(self.conn_name)

        self.txt_lrs_conn_name.setText(self.conn_name)
        self.txt_lrs_database.setText(self.dbname)
        self.txt_lrs_schema.setText(self.schema)

        # redirect changes in widgets after all combo boxes are filled
        self.cbx_conn_name.currentTextChanged.connect(self.conn_name_changed)
        self.cbx_schema.currentTextChanged.connect(self.schema_changed)
        self.pb_connect.clicked.connect(self.conn_connect)

    def conn_connect(self):
        self.cbx_schema.clear()
        if self.conn_name is None:
            self.conn_name = self.cbx_conn_name.currentText()

        credentials = qgis_utils.credentials_get(self.conn_name)

        if credentials is None:
            self.iface.messageBar().pushWarning("No Connection", "Missing credentials.")
            return

        self.host, self.port, self.dbname = qgis_utils.connection_params_get(self.conn_name)
        self.pg_conn = PGConn(self.dbname, self.host, self.port, credentials[0], credentials[1])
        return_message = self.pg_conn.db_connect()
        if return_message:
            self.iface.messageBar().pushWarning("No Connection", "No connection established.")
            return

        if not self.pg_conn.postgis_exists():
            self.iface.messageBar().pushWarning("No Connection", "PostGIS Extension not available.")
            self.button_apply.setEnabled(False)
            return

        schemes_list = self.pg_conn.schemes_get()
        for schema_name in schemes_list:
            self.cbx_schema.addItem(schema_name)

        self.schema = self.cbx_schema.currentText()
        self.button_apply.setEnabled(True)

    def conn_name_changed(self):
        self.conn_name = self.cbx_conn_name.currentText()
        self.cbx_schema.clear()
        self.button_apply.setEnabled(False)

    def schema_changed(self):
        self.schema = self.cbx_schema.currentText()

    def conn_close(self):
        if self.pg_conn:
            self.pg_conn.db_close()
            self.pg_conn = None

    def apply(self):
        if self.pg_conn:
            self.txt_lrs_conn_name.setText(self.conn_name)
            self.txt_lrs_database.setText(self.dbname)
            self.txt_lrs_schema.setText(self.schema)

            if self.conn_type is not None:
                # write project/basesystem entries
                qgis_utils.qgis_entries_set(self.conn_type, self.conn_name, self.dbname, self.host,
                                            self.schema, self.port)
                self.iface.messageBar().pushMessage("Connection established",
                                                    "Save your QGIS project to store the settings.")
            self.return_values = [self.conn_name, self.dbname, self.host, self.schema, self.port]
        else:
            self.iface.messageBar().pushMessage("No Connection", "Click Connect to check connection.")

    def data_get(self):
        return self.return_values

    def rejected(self):
        self.conn_close()
        self.reject()

    def closeEvent(self, event):
        # dialog closed with X-button
        # overrides method in QDialog
        self.rejected()
