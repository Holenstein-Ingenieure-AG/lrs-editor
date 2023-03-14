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
from qgis.PyQt.QtWidgets import QMessageBox

from ..utils import qgis_utils
from ..utils.pg_conn import PGConn
from ..cls.lrsproject import LRSProject
from ..cls.lrseventclasses import LRSEventClasses
from ..cls.lrsrouteclass import LRSRouteClass
from ..cls.lrsbasepointeventclass import LRSBasePointEventClass
from ..cls.lrsconteventclass import LRSContEventClass
from ..cls.lrstoureventclass import LRSTourEventClass


class LRSTool:
    def __init__(self, iface):
        self.iface = iface
        self.canvas = iface.mapCanvas()
        self.lrs_project = None

        # project connection
        entries = qgis_utils.qgis_entries_get("project")
        if entries is None:
            return
        conn_name = entries[0]
        self.schema = entries[3]
        credentials = qgis_utils.credentials_get(conn_name)
        if credentials is None:
            self.iface.messageBar().pushWarning("No Connection", "Missing credentials.")
            return
        self.pg_conn = PGConn(entries[1], entries[2], entries[4], credentials[0], credentials[1])
        return_message = self.pg_conn.db_connect()
        if return_message:
            self.iface.messageBar().pushWarning("No Connection", "No connection established.")
            return

        self.lrs_project = LRSProject(self.pg_conn, self.schema)
        if not self.lrs_project:
            self.iface.messageBar().pushWarning("No LRS Project", "No LRS Project created.")
            return

        self.lrs_event_classes = LRSEventClasses(self.pg_conn, self.schema, self.lrs_project.id)
        self.route_class = LRSRouteClass(self.pg_conn, self.schema, self.lrs_project.route_class_name)

    def message_show(self, text, msg_type):
        if msg_type == 1:
            t = QMessageBox.Question
        elif msg_type == 2:
            t = QMessageBox.Information
        elif msg_type == 3:
            t = QMessageBox.Warning
        elif msg_type == 4:
            t = QMessageBox.Critical
        else:
            t = QMessageBox.NoIcon

        msg = QMessageBox(t, "LRS-Editor", text)
        msg.exec_()

    def approvable_check(self, showmsg=True):
        if not self.lrs_project:
            return

        result = False
        # check event classes to approve
        event_classes = []
        route_class_name = self.lrs_project.route_class_name
        for clid in self.lrs_event_classes.event_class_idlist:
            event_class_name = self.lrs_event_classes.event_class_names[clid]
            lrs_layer = None
            if self.lrs_event_classes.event_class_types[clid] == "p":
                layer = qgis_utils.layer_by_tablename_get(self.schema, event_class_name + "_bp")
                if layer is None:
                    break
                lrs_layer = LRSBasePointEventClass(self.pg_conn, self.schema, layer)
            elif self.lrs_event_classes.event_class_types[clid] == "c":
                layer = qgis_utils.layer_by_tablename_get(self.schema, event_class_name)
                if layer is None:
                    break
                lrs_layer = LRSContEventClass(self.pg_conn, self.schema, layer)
            elif self.lrs_event_classes.event_class_types[clid] == "t":
                layer = qgis_utils.layer_by_tablename_get(self.schema, event_class_name)
                if layer is None:
                    break
                lrs_layer = LRSTourEventClass(self.pg_conn, self.schema, layer)

            if lrs_layer.events_approvable_get(route_class_name, self.lrs_project.tolerance, True):
                event_classes.append(event_class_name)

        if len(event_classes) > 0:
            result = True
            if showmsg:
                msg = QMessageBox()
                msg.setIcon(QMessageBox.Information)
                msg.setText("There are changed Event Points to approve first. See details for Event Classes.")
                msg.setWindowTitle("Approve Event Classes")
                txt = "\n".join(event_classes)
                msg.setDetailedText(txt)
                msg.setStandardButtons(QMessageBox.Ok)
                msg.exec_()

        return result

    def lrs_layer_check(self):
        # check layer before using tools
        if not self.lrs_project:
            return False
        result = 0
        event_class_name = ""
        for clid in self.lrs_event_classes.event_class_idlist:
            event_class_name = self.lrs_event_classes.event_class_names[clid]
            if self.lrs_event_classes.event_class_types[clid] == "p":
                layer = qgis_utils.layer_by_tablename_get(self.schema, event_class_name)
                layer_bp = qgis_utils.layer_by_tablename_get(self.schema, event_class_name + "_bp")
                if layer is None or layer_bp is None:
                    result = 1
                    break
                if layer_bp.isEditable() or layer.isEditable():
                    result = 2
                    break
            elif self.lrs_event_classes.event_class_types[clid] == "c":
                layer = qgis_utils.layer_by_tablename_get(self.schema, event_class_name)
                if layer is None:
                    result = 1
                    break
                if layer.isEditable():
                    result = 2
                    break
            elif self.lrs_event_classes.event_class_types[clid] == "t":
                layer = qgis_utils.layer_by_tablename_get(self.schema, event_class_name)
                layer_mt = qgis_utils.layer_by_tablename_get(self.schema, event_class_name + "_mt")
                if layer is None or layer_mt is None:
                    result = 1
                    break
                if layer.isEditable() or layer_mt.isEditable():
                    result = 2
                    break

        if result == 1:
            self.iface.messageBar().pushWarning("Update Event Classes", "Missing layer of Event Class '"
                                                + event_class_name + "'. Update failed.")
        if result == 2:
            self.iface.messageBar().pushWarning("Update Event Classes", "Stop editing of of Event Class '"
                                                + event_class_name + "'. Update failed.")

        if result == 0:
            return True
        else:
            return False

    def conn_close(self):
        if self.pg_conn:
            self.pg_conn.db_close()
            self.pg_conn = None
