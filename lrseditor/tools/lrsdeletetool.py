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

from ..utils import qgis_utils
from ..tools.lrsmaptool import LRSMapTool
from ..cls.lrsconteventclass import LRSContEventClass
from ..cls.lrseventnamesclass import LRSEventNamesClass
from ..cls.lrspointeventclass import LRSPointEventClass
from ..cls.lrsbasepointeventclass import LRSBasePointEventClass
from ..cls.lrstoureventclass import LRSTourEventClass


class LRSDeleteTool(LRSMapTool):
    def __init__(self, iface):
        LRSMapTool.__init__(self, iface)

        self.canvas_clicked.connect(self.canvas_clicked_connect)
        self.iface.activeLayer().afterCommitChanges.connect(self.layer_changes_saved)
        self.iface.activeLayer().afterRollBack.connect(self.layer_changes_unsaved)
        self.point = None
        self.rect = None
        self.event_class_name = None
        self.event_class_type = None
        self.lrs_layer = None
        self.lrs_layer_bp = None

    def canvas_clicked_connect(self, point, rect, event_class_name, event_class_type):
        self.point = point
        self.rect = rect
        self.event_class_name = event_class_name
        self.event_class_type = event_class_type
        if event_class_type == "p":
            self.point_event_delete()
        elif event_class_type == "c":
            self.cont_event_delete()
        elif event_class_type == "t":
            self.tour_event_delete()

    def tour_event_delete(self):
        layer_mt = qgis_utils.layer_by_tablename_get(self.schema, self.event_class_name + "_mt")
        if not layer_mt:
            self.message_show("An Event Layer is missing.", 2)
            return

        self.lrs_layer = LRSTourEventClass(self.pg_conn, self.schema, self.iface.activeLayer())
        events_count = self.lrs_layer.select_by_rect(self.rect, "set")
        values = self.lrs_layer.selection_values_get(["id", "uuid"])

        # must be before any other dialog
        modifiers = QApplication.keyboardModifiers()

        if events_count > 1:
            uuiddict = {}
            event_names_multiple = []
            id_list = []
            for value in values:
                event_name_list = self.lrs_layer.event_name_get(value[1])
                if event_name_list is None:
                    self.message_show("Inconsistent data.", 4)
                    self.lrs_layer.selection_remove()
                    return
                event_names_multiple.append(event_name_list[0] + " - Part " + str(event_name_list[1]))
                uuiddict[value[0]] = value[1]
                id_list.append(value[0])

            feat_id = self.lrs_layer.selection_reselect(id_list, event_names_multiple, "Delete Event",
                                                        "Choose an Event to delete:")
            if feat_id is None:
                self.lrs_layer.selection_remove()
                return
            uuid = uuiddict[feat_id]
        elif events_count == 1:
            uuid = values[0][1]
        else:
            return

        if modifiers == Qt.ControlModifier:
            # delete whole Tour
            msg = QMessageBox(QMessageBox.Question, "LRS-Editor", "Do you want to delete the whole Tour? "
                                                                  "This can not be undone.",
                              QMessageBox.Ok | QMessageBox.Cancel)
            ret = msg.exec_()
            if ret == QMessageBox.Ok:
                if not self.lrs_layer.tour_delete(uuid):
                    self.lrs_layer.selection_remove()
                    self.message_show("Inconsistent data.", 4)
            else:
                self.lrs_layer.selection_remove()
        else:
            # delete Tour Part
            if not self.lrs_layer.event_delete(uuid):
                self.lrs_layer.selection_remove()
                self.message_show("Inconsistent data.", 4)

        self.canvas.redrawAllLayers()

    def point_event_delete(self):
        layer_bp = qgis_utils.layer_by_tablename_get(self.schema, self.event_class_name + "_bp")
        if not layer_bp:
            self.message_show("An Event Layer is missing.", 2)
            return
        self.lrs_layer = LRSPointEventClass(self.pg_conn, self.schema, self.iface.activeLayer())
        self.lrs_layer_bp = LRSBasePointEventClass(self.pg_conn, self.schema, layer_bp)

        events_count = self.lrs_layer.select_by_rect(self.rect, "set")

        if events_count > 0:
            # get feat_id of selected event(s)
            values = self.lrs_layer.selection_values_get(["id", "name"])
            if events_count > 1:
                event_names_multiple = []
                id_list = []
                for value in values:
                    event_names_multiple.append(value[1])
                    id_list.append(value[0])
                feat_id = self.lrs_layer.selection_reselect(id_list, event_names_multiple, "Delete Event",
                                                            "Choose an Event to delete:")
                if feat_id is None:
                    return
            else:
                feat_id = values[0][0]

            # delete referenced base points, set geom null
            self.lrs_layer.event_geom_reset(feat_id)
            event_uuid = self.lrs_layer.event_uuid_get(feat_id)
            self.lrs_layer_bp.basepoints_delete("event_id", event_uuid)
            self.lrs_layer.selection_remove()
        else:
            # get feat_id of selected base point(s)
            basepoints_count = self.lrs_layer_bp.select_by_rect(self.rect, "set")
            values = self.lrs_layer_bp.selection_values_get(["id", "event_id", "route_id"])
            if basepoints_count > 1:
                event_names_multiple = []
                id_list = []
                for value in values:
                    f_id, event_uuid, route_id = value[0], value[1], value[2]
                    route_name = self.route_class.route_name_get(route_id, 1)
                    event_id = self.lrs_layer.event_id_get(None, event_uuid)
                    event_name = self.lrs_layer.event_name_get(event_id)
                    event_names_multiple.append(event_name + " - " + route_name)
                    id_list.append(f_id)
                feat_id = self.lrs_layer_bp.selection_reselect(id_list, event_names_multiple,
                                                               "Delete Base Point", "Choose a Base Point to delete:")
                if feat_id is None:
                    return
            elif basepoints_count == 1:
                feat_id = values[0][0]
            else:
                return

            # following sets point event layer in modified state, without changing an attribute value
            # when edits will be stopped -> changes in basepoint layer will be committed, when point event
            # layer will be saved
            feature = self.lrs_layer_bp.feature_get_by_id(feat_id)
            event_uuid = feature["event_id"]
            event_feat_id = self.lrs_layer.feature_id_get("uuid", event_uuid)[0]
            event_feature = self.lrs_layer.feature_get_by_id(event_feat_id)
            self.lrs_layer.attribute_value_change(event_feat_id, "changetstz", event_feature["changetstz"])

            # delete base point
            self.lrs_layer_bp.basepoint_delete(feat_id)
            self.lrs_layer_bp.selection_remove()

        self.canvas.redrawAllLayers()

    def cont_event_delete(self):
        self.lrs_layer = LRSContEventClass(self.pg_conn, self.schema, self.iface.activeLayer())
        events_count = self.lrs_layer.select_by_rect(self.rect, "set")

        # get route_id and feat_id of selected event(s)
        values = self.lrs_layer.selection_values_get(["route_id", "id", "event_id", "tomeas"])
        if events_count > 1:
            cont_event_names = LRSEventNamesClass(self.pg_conn, self.schema, self.event_class_name, "c")
            event_names_multiple = []
            id_list = []
            routedict = {}
            for value in values:
                route_id, f_id, event_uuid, tomeas = value[0], value[1], value[2], value[3]
                route_name = self.route_class.route_name_get(route_id, 1)
                event_id = cont_event_names.event_id_get(None, event_uuid)
                event_name = cont_event_names.event_name_get(event_id)
                event_names_multiple.append(event_name + " - " + str(round(tomeas, 3)) + " - " + route_name)
                id_list.append(f_id)
                routedict[f_id] = route_id
            feat_id = self.lrs_layer.selection_reselect(id_list, event_names_multiple, "Delete Event",
                                                        "Choose an Event to delete:")
            if feat_id is None:
                return
            route_id = routedict.get(feat_id)
        elif events_count == 1:
            route_id, feat_id = values[0][0], values[0][1]
        else:
            return

        # get all events along the route, tomeas descending
        event_list = self.lrs_layer.events_get(route_id, True)
        feat_id_old = None
        event_uuid_old = None
        for ind, event in enumerate(event_list):
            if event[0] == feat_id:
                if feat_id_old is None:
                    # this is the first event in the list (highest meas)
                    if len(event_list) > 1:
                        # do not delete the event at the end of the route
                        self.message_show("An Event at the end of the route can not be deleted, "
                                          "if other Events exist along the same route.", 2)
                        self.lrs_layer.selection_remove()
                    else:
                        # delete the last event at this route
                        # no update of other meas necessary
                        self.lrs_layer.event_delete(feat_id)
                else:
                    frommeas = event[2]
                    self.lrs_layer.event_delete(feat_id, feat_id_old, frommeas)
                    self.lrs_layer.selection_remove()
                    # info same event name
                    # except the first along the route
                    if not len(event_list) - 1 == ind:
                        if event_uuid_old == event_list[ind + 1][1]:
                            self.iface.messageBar().pushInfo("Same Event Name",
                                                             "Previous and following Event Points have "
                                                             "the same Event Name.")
                break
            event_uuid_old = event[1]
            feat_id_old = event[0]

        self.canvas.redrawAllLayers()

    def layer_changes_saved(self):
        self.layer_changes_accomplish(True)
        self.canvas.redrawAllLayers()

    def layer_changes_unsaved(self):
        self.layer_changes_accomplish(False)
        self.canvas.redrawAllLayers()

    def layer_changes_accomplish(self, commit):
        if self.lrs_layer is not None:
            if self.lrs_layer.modified():
                if commit:
                    self.lrs_layer.changes_commit(False)
                else:
                    self.lrs_layer.rollback()
            if self.event_class_type == "p":
                if self.lrs_layer_bp.modified():
                    if commit:
                        self.lrs_layer_bp.changes_commit()
                    else:
                        self.lrs_layer_bp.rollback()
            if self.event_class_type == "t":
                if self.lrs_layer.layer_mt_modified():
                    if commit:
                        self.lrs_layer.layer_mt_changes_commit()
                    else:
                        self.lrs_layer.layer_mt_rollback()

    def deactivate(self):
        # save all changes
        self.layer_changes_accomplish(True)
        self.canvas.redrawAllLayers()
        try:
            self.iface.activeLayer().afterCommitChanges.disconnect(self.layer_changes_saved)
        except TypeError:
            pass
        try:
            self.iface.activeLayer().afterRollBack.disconnect(self.layer_changes_unsaved)
        except TypeError:
            pass
        try:
            self.canvas_clicked.disconnect(self.canvas_clicked_connect)
        except TypeError:
            pass
        self.conn_close()
