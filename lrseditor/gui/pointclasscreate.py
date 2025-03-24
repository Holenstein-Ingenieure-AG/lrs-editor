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
import operator

from qgis.PyQt.uic import loadUiType
from qgis.PyQt.QtWidgets import QDialog, QDialogButtonBox, QMessageBox

from qgis.core import QgsProject

from ..utils.pg_conn import PGConn
from ..utils import qgis_utils
from ..utils import misc_utils
from ..gui.database import DBSettings

FORM_CLASS, _ = loadUiType(os.path.join(
    os.path.dirname(__file__), os.pardir, 'ui', 'pointclasscreate.ui'))


class PointClassCreate(QDialog, FORM_CLASS):
    def __init__(self, iface):
        # call superclass constructor
        QDialog.__init__(self, parent=None)
        self.iface = iface
        self.canvas = iface.mapCanvas()
        # After self.setupUi() you can access any designer object by doing
        # self.<objectname>, and you can use autoconnect slots
        self.setupUi(self)
        self.schema_pt = None
        self.pg_conn_pt = None
        self.entries = None
        self.credentials = None

        # redirect buttonbox
        self.pb_conn.clicked.connect(self.conn_choose)
        self.buttonBox.rejected.disconnect()
        self.buttonBox.rejected.connect(self.rejected)
        self.buttonBox.accepted.disconnect()
        self.buttonBox.accepted.connect(self.accepted)
        self.pb_ok = self.buttonBox.button(QDialogButtonBox.Ok)
        self.pb_ok.setEnabled(False)

    def form_update(self):
        # fill combo boxes with table names
        # get only 2D-geom
        tablelist = self.pg_conn_pt.tablenames_geom_get(self.schema_pt, 2)
        self.cbx_class_name.clear()
        for table in tablelist:
            if table[1].upper() == "LINESTRING":
                self.cbx_class_name.addItem(table[0])
                self.class_fields_add()

        if self.cbx_class_name.count() > 0:
            self.pb_ok.setEnabled(True)
            # redirect changes
            self.cbx_class_name.currentTextChanged.connect(self.class_name_changed)

    def class_name_changed(self):
        self.class_fields_add()

    def class_fields_add(self):
        fields_geom = self.pg_conn_pt.fieldnames_geom_get(self.schema_pt, self.cbx_class_name.currentText())
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
            conn_name, dbname, host, self.schema_pt, port = dlg.data_get()
            self.entries = [conn_name, dbname, host, self.schema_pt, port]
            self.credentials = qgis_utils.credentials_get(conn_name)
            if self.credentials is None:
                self.iface.messageBar().pushWarning("No Connection", "Missing credentials.")
                return None
            self.pg_conn_pt = PGConn(dbname, host, port, self.credentials[0], self.credentials[1])
            return_message = self.pg_conn_pt.db_connect()
            if return_message:
                self.iface.messageBar().pushWarning("No Connection", "No connection established.")
                return None
            self.cbx_conn_name.clear()
            self.cbx_conn_name.addItem(conn_name)
            self.form_update()

    def conn_close(self):
        if self.pg_conn_pt:
            self.pg_conn_pt.db_close()
            self.pg_conn_pt = None

    def rejected(self):
        self.conn_close()
        self.reject()

    def accepted(self):
        point_class_name = self.le_point_class_name.text()
        if point_class_name == "":
            return
        linestring_class_name = self.cbx_class_name.currentText()
        if linestring_class_name == "":
            return

        # check for spaces in class name
        if ' ' in point_class_name:
            msg = QMessageBox(QMessageBox.Critical, "Create Point Class", "No spaces in class names allowed.",
                              QMessageBox.Ok)
            msg.exec_()
            return

        if self.pg_conn_pt.table_exists(self.schema_pt, point_class_name.lower()):
            msg = QMessageBox(QMessageBox.Critical, "Create Point Class", "Point Class Name already exists.",
                              QMessageBox.Ok)
            msg.exec_()
            return
        if self.pg_conn_pt.system_table_exists(point_class_name.lower()):
            msg = QMessageBox(QMessageBox.Critical, "Create Point Class", "Point Class Name is identical to system "
                                                                          "table name.", QMessageBox.Ok)
            msg.exec_()
            return

        # --------------------------------
        # generate node class

        geom_field = self.cbx_geom.currentText()
        nodelist = self.pg_conn_pt.linestrings_nodes_get(self.schema_pt, linestring_class_name, geom_field)
        if len(nodelist) == 0:
            msg = QMessageBox(QMessageBox.Information, "Create Point Class", "Empty Line Class.",
                              QMessageBox.Ok)
            msg.exec_()
            return

        # sort by x-coord, itemgetter ist faster
        nodelist.sort(key=operator.itemgetter(1))
        # newlist = sorted(nodelist, key=lambda x: x[1])

        # re-sort nodelist
        tol = self.dsb_tolerance.value()
        oldx = nodelist[0][1]
        sortednodelist = []
        tmplist1 = []
        for row in nodelist:
            newx = row[1]
            # get all nodes tolerated in x-direction
            if (newx - oldx) <= tol:
                tmplist1.append(row)
            else:
                # sort temp list by y-coord
                if len(tmplist1) > 1:
                    tmplist1.sort(key=operator.itemgetter(2))
                for tmprow in tmplist1:
                    sortednodelist.append(tmprow)
                tmplist1[:] = []
                tmplist1.append(row)
            oldx = newx
        # get the last ones
        if len(tmplist1) > 1:
            tmplist1.sort(key=operator.itemgetter(2))
        for tmprow in tmplist1:
            sortednodelist.append(tmprow)

        # generate topology nodelist
        oldnode = sortednodelist[0]
        tmplist2 = []
        finallist = []
        for node in sortednodelist:
            point1 = [node[1], node[2]]
            point2 = [oldnode[1], oldnode[2]]
            dist = misc_utils.points_dist_get(point1, point2)
            # get all nodes inside tolerance
            if dist <= tol:
                tmplist2.append(node)
            else:
                centrnode = self.centroid_node_get(tmplist2)
                finallist.append(centrnode)
                tmplist2[:] = []
                tmplist2.append(node)
            oldnode = node
        # get the last ones
        finallist.append(self.centroid_node_get(tmplist2))

        srid = self.pg_conn_pt.srid_find(self.schema_pt, linestring_class_name, geom_field)
        self.pg_conn_pt.point_class_create(self.schema_pt, point_class_name, finallist, srid)

        self.conn_close()

        msg = QMessageBox(QMessageBox.Information, "Create Point Class", "Point Class created. "
                                                                         "Do you want to add it to the project?")
        msg.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
        ret = msg.exec_()
        if ret == QMessageBox.Ok:
            layer = qgis_utils.layer_create(self.entries, self.credentials, point_class_name, "geom", False,
                                            srid, False)
            if not layer.isValid():
                msg = QMessageBox(QMessageBox.Critical, "Create Point Class", "Point Class failed to load!",
                                  QMessageBox.Ok)
                msg.exec_()
                return
            else:
                QgsProject.instance().addMapLayer(layer)
                self.canvas.redrawAllLayers()

        self.accept()

    def centroid_node_get(self, nodelist):
        countlist = len(nodelist)
        if countlist > 1:
            xlist = [n[1] for n in nodelist]
            ylist = [n[2] for n in nodelist]
            centr_x = sum(xlist) / countlist
            centr_y = sum(ylist) / countlist
            if countlist == 2:
                kind = 'P'
            else:
                kind = 'T'
            return [kind, centr_x, centr_y]
        else:
            return nodelist[0]

    def closeEvent(self, event):
        # dialog closed with X-button
        # overrides method in QDialog
        self.rejected()
