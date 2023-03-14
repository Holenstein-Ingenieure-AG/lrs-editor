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
from qgis.PyQt.QtWidgets import QApplication, QDialog, QDialogButtonBox, QMessageBox, QFileDialog, QInputDialog
from qgis.core import QgsProject

from ..utils.pg_conn import PGConn
from ..utils import qgis_utils
from ..gui.database import DBSettings
from ..cls.lrsproject import LRSProject

FORM_CLASS, _ = loadUiType(os.path.join(
    os.path.dirname(__file__), os.pardir, 'ui', 'project.ui'))


class ProjectSettings(QDialog, FORM_CLASS):
    def __init__(self, iface):
        # call superclass constructor
        QDialog.__init__(self, parent=None)
        self.iface = iface
        self.canvas = iface.mapCanvas()
        # After self.setupUi() you can access any designer object by doing
        # self.<objectname>, and you can use autoconnect slots
        self.setupUi(self)

        self.entries = None
        self.schema = None
        self.credentials = None
        self.pg_conn = None
        self.lrs_project = None

        # configure buttons
        self.pb_add.setEnabled(False)
        self.pb_remove.setEnabled(False)
        self.pb_add.clicked.connect(self.route_class_layer_add)
        self.pb_remove.clicked.connect(self.route_class_layer_remove)
        self.buttonBox.rejected.disconnect()
        self.buttonBox.rejected.connect(self.rejected)
        self.button_apply = self.buttonBox.button(QDialogButtonBox.Apply)
        self.button_apply.clicked.connect(self.apply)
        self.button_apply.setEnabled(False)
        self.pb_logfile.clicked.connect(self.filename_get)
        self.pb_conn.clicked.connect(self.conn_choose)
        self.cbx_crs.textActivated.connect(self.crs_dialog_show)

        # redirect changes in widgets
        self.le_project_name.textEdited.connect(self.editing_changed)
        self.le_route_class_name.textEdited.connect(self.editing_changed)
        self.dsb_tolerance.valueChanged.connect(self.editing_changed)
        self.le_logfile.textEdited.connect(self.editing_changed)

        self.form_update()

    def form_update(self):
        if self.lrs_project is None:
            self.cbx_crs.clear()
            self.cbx_crs.addItem(QgsProject.instance().crs().authid())

        self.entries = qgis_utils.qgis_entries_get("project")
        if self.entries is None:
            return
        conn_name = self.entries[0]

        self.cbx_conn_name.clear()
        self.cbx_conn_name.addItem(conn_name)

        self.schema = self.entries[3]

        self.credentials = qgis_utils.credentials_get(conn_name)
        if self.credentials is None:
            self.iface.messageBar().pushWarning("No Connection", "Missing credentials.")
            return

        self.pg_conn = PGConn(self.entries[1], self.entries[2], self.entries[4],
                              self.credentials[0], self.credentials[1])
        return_message = self.pg_conn.db_connect()
        if return_message:
            self.iface.messageBar().pushWarning("No Connection", "No connection established.")
            return

        self.lrs_project = LRSProject(self.pg_conn, self.schema)
        if self.lrs_project:
            self.le_project_name.setText(self.lrs_project.name)
            self.le_route_class_name.setText(self.lrs_project.route_class_name)
            # self.le_route_class_name.setEnabled(False)
            self.dsb_tolerance.setValue(self.lrs_project.tolerance)
            self.le_logfile.setText(self.lrs_project.logfile_path)
            srid_auth = self.pg_conn.srid_auth_get(self.lrs_project.srid)
            self.cbx_crs.clear()
            if srid_auth is not None:
                self.cbx_crs.addItem("{}: {}".format(srid_auth[0], srid_auth[1]))
                # compare with crs in qgis
                qgis_srid = QgsProject.instance().crs().authid().split(":")[1]
                srid_bool = True
                try:
                    qgis_srid = int(qgis_srid)
                    if qgis_srid != self.lrs_project.srid:
                        srid_bool = False
                except ValueError:
                    srid_bool = False
                if not srid_bool:
                    msg = QMessageBox(QMessageBox.Critical, "CRS", "CRS in QGIS does not match CRS of LRS-Project.",
                                      QMessageBox.Ok)
                    msg.exec_()
            else:
                msg = QMessageBox(QMessageBox.Critical, "No valid CRS", "CRS is not valid. Check LRS-Project settings "
                                                                        "in database.",
                                  QMessageBox.Ok)
                msg.exec_()
            self.pb_add.setEnabled(True)
            self.pb_remove.setEnabled(True)
            self.txt_routeupdatetstz.setText(self.lrs_project.routeupdatetstz)

    def conn_choose(self):
        dlg = DBSettings(self.iface, "project")
        dlg.setWindowTitle("Project Database Settings")
        dlg.gbox_settings.setTitle("Project Database Settings")
        dlg.exec_()
        self.form_update()

    def route_class_layer_add(self):
        name = self.le_route_class_name.text()
        if not name:
            return
        layer = qgis_utils.layer_create(self.entries, self.credentials, name, "geom", True, self.lrs_project.srid)
        if not layer.isValid():
            msg = QMessageBox(QMessageBox.Critical, "Route Class", "Route Class " + name + " failed to load!",
                              QMessageBox.Ok)
            msg.exec_()
            return
        else:
            # set fields readonly, though layer is already readonly
            qgis_utils.fields_readonly_set(layer, ["id", "sortnr", "route_id", "name", "basesystem_id", "createtstz",
                                                   "changetstz", "geomtstz", "length"])
            QgsProject.instance().addMapLayer(layer)
            self.canvas.redrawAllLayers()

    def route_class_layer_remove(self):
        name = self.le_route_class_name.text()
        if not name:
            return
        maplayer = qgis_utils.layer_by_tablename_get(self.entries[3], name)
        if maplayer is not None:
            QgsProject.instance().removeMapLayers([maplayer.id()])
            self.canvas.redrawAllLayers()

    def editing_changed(self):
        self.button_apply.setEnabled(False)
        if not self.pg_conn:
            return
        if not self.le_project_name.text():
            return
        if not self.le_route_class_name.text():
            return
        if self.dsb_tolerance.value() == 0:
            return
        if not self.le_logfile.text():
            return

        # check for changes of existing values
        if self.lrs_project:
            if self.le_project_name.text() == self.lrs_project.name:
                if self.le_route_class_name.text() == self.lrs_project.route_class_name:
                    if self.dsb_tolerance.value() == self.lrs_project.tolerance:
                        if self.le_logfile.text() == self.lrs_project.logfile_path:
                            return

        self.button_apply.setEnabled(True)

    def filename_get(self):
        oldfn = self.le_logfile.text()
        fnlist = QFileDialog.getSaveFileName(self, "Open Log File", oldfn, "Log File (*.log);;All Files (*.*)")
        fn = fnlist[0]
        # isfile = os.path.isfile(fn)
        if len(fn) != 0:
            if self.le_logfile.setText != fn:
                self.le_logfile.setText(fn)
                self.editing_changed()

    def crs_dialog_show(self):
        if not self.lrs_project:
            msg = QMessageBox(QMessageBox.Information, "CRS", "Choose CRS in QGIS before saving LRS-Project settings.",
                              QMessageBox.Ok)
            msg.exec_()

    def conn_close(self):
        if self.pg_conn:
            self.pg_conn.db_close()
            self.pg_conn = None

    def apply(self):
        valuelist = [self.le_project_name.text(), self.le_route_class_name.text().lower(),
                     self.dsb_tolerance.value(), self.le_logfile.text()]

        if not self.lrs_project:
            if ' ' in self.le_route_class_name.text():
                msg = QMessageBox(QMessageBox.Critical, "New Route Class", "No spaces in class names allowed.",
                                  QMessageBox.Ok)
                msg.exec_()
                return
            if self.pg_conn.table_exists(self.schema, self.le_route_class_name.text().lower()):
                msg = QMessageBox(QMessageBox.Critical, "New Route Class", "Route Class Name already exists.",
                                  QMessageBox.Ok)
                msg.exec_()
                return
            if self.pg_conn.system_table_exists(self.le_route_class_name.text().lower()):
                msg = QMessageBox(QMessageBox.Critical, "New Route Class", "Route Class Name is identical to system "
                                                                           "table name.", QMessageBox.Ok)
                msg.exec_()
                return

            srid = self.cbx_crs.currentText().split(":")[1]
            srid_bool = True
            # check crs with postgis
            try:
                srid = int(srid)
                # get crs from postgis
                if self.pg_conn.srid_auth_get(srid) is None:
                    srid_bool = False
            except ValueError:
                srid_bool = False

            if not srid_bool:
                msg = QMessageBox(QMessageBox.Critical, "No valid CRS", "CRS is not valid. "
                                                                        "Choose an other CRS in QGIS.", QMessageBox.Ok)
                msg.exec_()
                return

            self.lrs_project.create(valuelist, srid)
            self.iface.messageBar().pushMessage("Success", "New LRS-Project created.")
            self.pb_add.setEnabled(True)
            self.pb_remove.setEnabled(True)
            self.rejected()
        else:
            if valuelist[1] != self.lrs_project.route_class_name:
                msg = QMessageBox(QMessageBox.Critical, "Change Route Class Name",
                                  "Changing the route class name may affect your LRS-Project and will not "
                                  "be executed.", QMessageBox.Ok)
                msg.exec_()
                # reset values
                self.le_route_class_name.setText(self.lrs_project.route_class_name)
                valuelist[1] = self.lrs_project.route_class_name
            self.lrs_project.update(valuelist)
            self.button_apply.setEnabled(False)

    def rejected(self):
        self.conn_close()
        self.reject()

    def closeEvent(self, event):
        # dialog closed with X-button
        # overrides method in QDialog
        self.rejected()
