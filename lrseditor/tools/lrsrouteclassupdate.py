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

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import QApplication, QMessageBox

from ..tools.lrstool import LRSTool
from ..utils import qgis_utils
from ..utils.pg_conn import PGConn
from ..utils.logfile import LogFile
from ..cls.lrsbasesystem import LRSBasesystem
from ..cls.lrspointeventclass import LRSPointEventClass
from ..cls.lrsbasepointeventclass import LRSBasePointEventClass
from ..cls.lrsconteventclass import LRSContEventClass
from ..cls.lrstoureventclass import LRSTourEventClass


class LRSRouteClassUpdate(LRSTool):
    def __init__(self, iface):
        # call superclass constructor (both ways possible)
        LRSTool.__init__(self, iface)

    def update(self):
        # basesystem connection
        entries = qgis_utils.qgis_entries_get("basesystem")

        if entries is None:
            self.iface.messageBar().pushWarning("No LRS Base System", "No LRS Base System defined.")
            return

        conn_name = entries[0]
        schema_bs = entries[3]
        credentials = qgis_utils.credentials_get(conn_name)
        if credentials is None:
            self.iface.messageBar().pushWarning("No Connection", "Missing credentials.")
            return
        pg_conn_bs = PGConn(entries[1], entries[2], entries[4], credentials[0], credentials[1])
        return_message = pg_conn_bs.db_connect()
        if return_message:
            self.iface.messageBar().pushWarning("No Connection", "No connection established.")
            return

        lrs_basesystem = LRSBasesystem(self.pg_conn, self.schema, self.lrs_project.id,
                                       pg_conn_bs, schema_bs)
        if not lrs_basesystem:
            self.iface.messageBar().pushWarning("No LRS Base System", "No LRS Base System defined.")
            return

        try:
            logfile = LogFile(self.lrs_project.logfile_path)
        except Exception as error:
            msg = QMessageBox(QMessageBox.Critical, "Open Log File", str(error), QMessageBox.Ok)
            msg.exec_()
            return

        QApplication.setOverrideCursor(Qt.WaitCursor)

        # check data of basesystem
        result = lrs_basesystem.data_check(logfile)
        if result:
            # continue
            # check topology of linestring with points
            lrs_basesystem.topology_check(logfile)

            # synchronize routes in route class and get changed routes to update events
            routelist_upd, route_del_list_tmp = self.lrs_project.routes_synchronize(lrs_basesystem.id, logfile)
            self.lrs_project.routeupdatetstz_set()

            # update event classes
            for clid in self.lrs_event_classes.event_class_idlist:
                event_class_name = self.lrs_event_classes.event_class_names[clid]
                if self.lrs_event_classes.event_class_types[clid] == "p":
                    layer = qgis_utils.layer_by_tablename_get(self.schema, event_class_name + "_bp")
                    lrs_layer = LRSBasePointEventClass(self.pg_conn, self.schema, layer)
                    lrs_layer.basepoints_update(routelist_upd, self.route_class, self.lrs_project.srid,
                                                self.lrs_project.tolerance)
                elif self.lrs_event_classes.event_class_types[clid] == "c":
                    layer = qgis_utils.layer_by_tablename_get(self.schema, event_class_name)
                    lrs_layer = LRSContEventClass(self.pg_conn, self.schema, layer)
                    lrs_layer.events_update(routelist_upd, self.route_class, self.lrs_project.srid,
                                            self.lrs_project.tolerance)
                elif self.lrs_event_classes.event_class_types[clid] == "t":
                    layer = qgis_utils.layer_by_tablename_get(self.schema, event_class_name)
                    lrs_layer = LRSTourEventClass(self.pg_conn, self.schema, layer)
                    lrs_layer.events_update(routelist_upd, self.route_class, self.lrs_project.srid,
                                            self.lrs_project.tolerance)

            if len(route_del_list_tmp) > 0:
                msg = QMessageBox()
                msg.setIcon(QMessageBox.Information)
                msg.setText("There are Routes to delete with existing Events. Do you want to delete Routes and "
                            "the referencing Events? "
                            "See details for Routes and Event Classes.")
                txt = ""
                for route in route_del_list_tmp:
                    txt = txt + route[0] + ": " + route[2] + "\n"
                msg.setDetailedText(txt)
                msg.setWindowTitle("Delete Routes")
                msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
                ret = msg.exec_()
                if ret == QMessageBox.Yes:
                    for route in route_del_list_tmp:
                        event_class_name = route[2]
                        event_class_type = self.lrs_event_classes.event_class_type_get(event_class_name)
                        if event_class_type == "p":
                            layer_bp = qgis_utils.layer_by_tablename_get(self.schema, event_class_name + "_bp")
                            lrs_layer_bp = LRSBasePointEventClass(self.pg_conn, self.schema, layer_bp)
                            point_events_reset = lrs_layer_bp.basepoints_sql_delete(route[1])
                            layer = qgis_utils.layer_by_tablename_get(self.schema, event_class_name)
                            lrs_layer = LRSPointEventClass(self.pg_conn, self.schema, layer)
                            # reset geom of event point with one basepoint
                            for point_event_reset in point_events_reset:
                                lrs_layer.event_geom_sql_reset(point_event_reset)
                        if event_class_type == "c":
                            layer = qgis_utils.layer_by_tablename_get(self.schema, event_class_name)
                            lrs_layer = LRSContEventClass(self.pg_conn, self.schema, layer)
                            lrs_layer.events_sql_delete(route[1])
                        if event_class_type == "t":
                            layer = qgis_utils.layer_by_tablename_get(self.schema, event_class_name)
                            lrs_layer = LRSTourEventClass(self.pg_conn, self.schema, layer)
                            lrs_layer.events_sql_delete(route[1])
                        self.route_class.route_delete(route[0])
                        logfile.write("Route " + route[0] + ": Route with events deleted", "INFORM")

        logfile.close()
        QApplication.restoreOverrideCursor()
        self.iface.messageBar().pushMessage("Route Class Update",
                                            "Update finished with " + str(logfile.warn_count) + " warnings and "
                                            + str(logfile.err_count) + " errors. "
                                            "<a href=file:///" + self.lrs_project.logfile_path + ">Log File</a>")

        self.canvas.redrawAllLayers()

        if pg_conn_bs:
            pg_conn_bs.db_close()
