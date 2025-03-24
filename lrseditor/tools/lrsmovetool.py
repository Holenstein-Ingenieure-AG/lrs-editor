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
from qgis.PyQt.QtWidgets import QApplication

from ..utils import qgis_utils
from ..utils.tourmarker import Tourmarker
from ..tools.lrsmaptool import LRSMapTool
from ..cls.lrsconteventclass import LRSContEventClass
from ..cls.lrseventnamesclass import LRSEventNamesClass
from ..cls.lrspointeventclass import LRSPointEventClass
from ..cls.lrsbasepointeventclass import LRSBasePointEventClass
from ..cls.lrstoureventclass import LRSTourEventClass


class LRSMoveTool(LRSMapTool):
    def __init__(self, iface, eventnamesdockwidget):
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

        self.iface.activeLayer().selectionChanged.connect(self.selection_changed)

        self.eventnamesdockwidget = eventnamesdockwidget
        self.eventnamesdockwidget.listwidget_clicked.connect(self.event_name_changed)

        self.tourmarker = None
        self.feat_id = None
        self.feat_uuid = None

    def canvas_clicked_connect(self, point, rect, event_class_name, event_class_type):
        self.point = point
        self.rect = rect
        self.event_class_name = event_class_name
        self.event_class_type = event_class_type
        if event_class_type == "p":
            self.point_event_move()
        elif event_class_type == "c":
            self.cont_event_move()
        elif event_class_type == "t":
            self.tour_event_move()

    def tour_event_move(self):
        layer_mt = qgis_utils.layer_by_tablename_get(self.schema, self.event_class_name + "_mt")
        if not layer_mt:
            self.message_show("An Event Layer is missing.", 2)
            return

        self.lrs_layer = LRSTourEventClass(self.pg_conn, self.schema, self.iface.activeLayer())
        self.tourmarker = Tourmarker(self.iface)
        datalist = self.tourmarker.datalist_get()
        if self.lrs_layer.selection_count_get() == 0:
            # select new event point

            # must be before any other dialog
            modifiers = QApplication.keyboardModifiers()
            if modifiers == Qt.ShiftModifier:
                # append tour part, prepare and append
                if not self.route_select():
                    self.tool_reset()
                    return
                valuelist = self.route_class.selection_values_get(['route_id', 'sortnr'])
                self.route_class.selection_remove()
                self.tourmarker.remove()
                if datalist is not None:
                    route_id_fi, sortnr_fi = datalist[1], datalist[2]
                    route_id_se, sortnr_se = valuelist[0][0], valuelist[0][1]
                    # check for same route
                    if (route_id_se + "-" + str(sortnr_se)) != (route_id_fi + "-" + str(sortnr_fi)):
                        self.message_show("The endpoint of the part is not along the same route.", 3)
                        self.tool_reset()
                        return

                    qgis_point_fi = self.tourmarker.point_get()
                    result_fi = self.route_class.point_meas_get(route_id_fi, qgis_point_fi, self.lrs_project.srid,
                                                                sortnr_fi)
                    result_se = self.route_class.point_meas_get(route_id_se, self.point, self.lrs_project.srid,
                                                                sortnr_se)
                    meas_fi, meas_se = result_fi[1], result_se[1]
                    direction = True
                    if meas_fi < meas_se:
                        frommeas = meas_fi
                        tomeas = meas_se
                    elif meas_fi > meas_se:
                        frommeas = meas_se
                        tomeas = meas_fi
                        direction = False
                    else:
                        # same start- and endpoint of part
                        self.message_show("Invalid Tour Part", 4)
                        self.tool_reset()
                        return
                    # get tour events along route with selected event point
                    events_list = self.lrs_layer.tour_meas_get(datalist[3], route_id_fi)
                    if events_list is None:
                        self.message_show("Inconsistent data.", 4)
                        self.tool_reset()
                        return
                    if len(events_list) > 0:
                        # check for same direction on same route_id
                        for events in events_list:
                            routedir_old = events[8]
                            if direction != routedir_old:
                                self.message_show("New Tour Part in reversed direction.", 2)
                                self.tool_reset()
                                return
                        # check for overlapping parts on same route_id
                        for events in events_list:
                            frommeas_old = events[4]
                            tomeas_old = events[6]

                            tol = self.lrs_project.tolerance
                            if self.lrs_layer.overlaps_check(frommeas, frommeas_old, tomeas, tomeas_old, tol):
                                self.message_show("Overlapping Tour Parts.", 2)
                                self.tool_reset()
                                return
                    if not self.lrs_layer.event_append(datalist[3], result_fi, result_se, route_id_fi, direction):
                        self.message_show("Inconsistent data.", 4)
                    else:
                        # save to get new feat_id for reselect
                        self.layer_changes_saved()
                self.tool_reset()
            else:
                self.feat_id = None
                self.feat_uuid = None
                # select Event Point
                events_count = self.lrs_layer.select_by_rect(self.rect, "set")
                values = self.lrs_layer.selection_values_get(["id", "uuid"])
                if events_count > 1:
                    uuiddict = {}
                    event_names_multiple = []
                    id_list = []
                    for value in values:
                        event_name_list = self.lrs_layer.event_name_get(value[1])
                        if event_name_list is None:
                            self.message_show("Inconsistent data.", 4)
                            self.tool_reset()
                            return
                        event_names_multiple.append(event_name_list[0] + " - Part " + str(event_name_list[1]))
                        uuiddict[value[0]] = value[1]
                        id_list.append(value[0])

                    self.feat_id = self.lrs_layer.selection_reselect(id_list, event_names_multiple, "Move Event",
                                                                     "Choose an Event to move:")
                    if self.feat_id is None:
                        self.lrs_layer.selection_remove()
                        return
                    self.feat_uuid = uuiddict[self.feat_id]
                elif events_count == 1:
                    self.feat_id = values[0][0]
                    self.feat_uuid = values[0][1]
                else:
                    return
        else:
            # an event point is already selected

            # must be before any other dialog
            modifiers = QApplication.keyboardModifiers()

            if self.feat_uuid is None:
                return
            # check for selected route
            if not self.route_select():
                self.tool_reset()
                return
            valuelist = self.route_class.selection_values_get(['route_id', 'sortnr'])
            route_id = valuelist[0][0]
            sortnr = valuelist[0][1]
            result = self.route_class.point_meas_get(route_id, self.point, self.lrs_project.srid, sortnr)
            meas = result[1]
            if modifiers == Qt.ShiftModifier:
                # append tour part, set tourmarker startpoint
                if datalist is None:
                    self.tourmarker.startpoint_set(self.point,[result, route_id, sortnr, self.feat_uuid])
                    # remove selection of event point
                    # selection of route is also removed (triggered by selection_changed)
                    self.lrs_layer.selection_remove()
            else:
                # move event point of existing tour part
                event_list = self.lrs_layer.event_meas_get(self.feat_uuid, route_id)
                if event_list is None:
                    self.message_show("Inconsistent data.", 4)
                    self.tool_reset()
                    return
                if len(event_list) == 0:
                    self.message_show("Move the point along the same route.", 2)
                    self.tool_reset()
                    return
                if event_list[2] == -99:
                    # maxmeas at route end
                    maxmeas = self.route_class.point_routeend_get(route_id)[1]
                else:
                    maxmeas = event_list[2]
                minmeas = event_list[1]
                # it must be allowed to overlap points of tour parts, without gap and without overlapping lines
                tol = self.lrs_project.tolerance
                diff_min = minmeas - meas
                diff_max = meas - maxmeas
                # it is not allowed to move on the other point of the same tour part
                samemeas = event_list[4]
                diff = abs(meas - samemeas)
                if diff_min >= tol or diff_max >= tol:
                    self.message_show("An Event must be moved between existing Events.", 2)
                    self.tool_reset()
                    return
                elif diff <= tol:
                    self.message_show("An Event of the same Tour Part already exists at this position.", 2)
                    self.tool_reset()
                    return
                else:
                    self.lrs_layer.event_move(self.feat_id, result[0], result[2], event_list[0], event_list[3], meas)
                self.tool_reset()
        self.canvas.redrawAllLayers()

    def point_event_move(self):
        layer_bp = qgis_utils.layer_by_tablename_get(self.schema, self.event_class_name + "_bp")
        if not layer_bp:
            self.message_show("An Event Layer is missing.", 2)
            return
        self.lrs_layer = LRSPointEventClass(self.pg_conn, self.schema, self.iface.activeLayer())
        self.lrs_layer_bp = LRSBasePointEventClass(self.pg_conn, self.schema, layer_bp)

        if self.lrs_layer.selection_count_get() == 0:
            # select Event Point
            events_count = self.lrs_layer.select_by_rect(self.rect, "set")
            if events_count > 0:
                self.feat_id = None
                # get feat_id of selected event(s)
                values = self.lrs_layer.selection_values_get(["id", "name"])
                if events_count > 1:
                    event_names_multiple = []
                    id_list = []
                    for value in values:
                        event_names_multiple.append(value[1])
                        id_list.append(value[0])
                    self.feat_id = self.lrs_layer.selection_reselect(id_list, event_names_multiple,
                                                                     "Move Event", "Choose an Event to move:")
                else:
                    self.feat_id = values[0][0]
                if self.feat_id is None:
                    return
                event_uuid = self.lrs_layer.event_uuid_get(self.feat_id)
                self.lrs_layer_bp.select_by_attribute_value("event_id", event_uuid)
        else:
            if self.feat_id is None:
                return
            # must be before any other dialog
            modifiers = QApplication.keyboardModifiers()
            if modifiers == Qt.ShiftModifier:
                # insert additional Base Point
                # check if a route is selected
                self.route_class.select_by_rect(self.rect, "set")
                lines_count = self.route_class.selection_count_get()
                if lines_count == 1:
                    route_id_add = self.route_class.selection_values_get(['route_id'])[0][0]
                    valuelist = self.lrs_layer_bp.selection_values_get(['route_id'])
                    if route_id_add in (item for sublist in valuelist for item in sublist):
                        # check for existing Base Point
                        self.message_show("Base Point already exists for this route.", 2)
                    else:
                        feature = self.lrs_layer.feature_get_by_id(self.feat_id)
                        event_point = feature.geometry().asPoint()
                        result = self.route_class.point_meas_get(route_id_add, event_point, self.lrs_project.srid)
                        event_uuid = self.lrs_layer.event_uuid_get(self.feat_id)
                        self.lrs_layer_bp.basepoint_insert(result[0], route_id_add, event_uuid, result[1], result[2])
                        # following sets point event layer in modified state, without changing an attribute value
                        # when edits will be stopped -> changes in basepoint layer will be committed, when point event
                        # layer will be saved
                        self.lrs_layer.attribute_value_change(feature.id(), "changetstz", feature["changetstz"])
                else:
                    self.message_show("Select one route.", 2)
            else:
                # move Event Point and Base Point(s)
                valuelist = self.lrs_layer_bp.selection_values_get(['id', 'route_id'])
                # check for basepoints with feat_id = None (just added basepoints)
                if any(None in item for item in valuelist):
                    self.message_show("Save changes first.", 2)
                else:
                    self.lrs_layer.event_move(self.feat_id, self.point)
                    self.lrs_layer_bp.basepoints_move(self.point, self.route_class, valuelist, self.lrs_project.srid)

            self.tool_reset()
        self.canvas.redrawAllLayers()

    def cont_event_move(self):
        self.lrs_layer = LRSContEventClass(self.pg_conn, self.schema, self.iface.activeLayer())
        cont_event_names = LRSEventNamesClass(self.pg_conn, self.schema, self.event_class_name, "c")



        if self.lrs_layer.selection_count_get() == 0:
            # select Event Point
            events_count = self.lrs_layer.select_by_rect(self.rect, "set")

            if events_count > 0:
                self.feat_id = None
                event_name = ""
                values = self.lrs_layer.selection_values_get(["route_id", "id", "event_id", "tomeas"])
                if events_count > 1:
                    event_names_multiple = []
                    id_list = []
                    event_namedict = {}
                    for value in values:
                        route_id, f_id, event_uuid, tomeas = value[0], value[1], value[2], value[3]
                        route_name = self.route_class.route_name_get(route_id, 1)
                        event_id = cont_event_names.event_id_get(None, event_uuid)
                        event_name = cont_event_names.event_name_get(event_id)
                        event_names_multiple.append(event_name + " - " + str(round(tomeas, 3)) + " - " + route_name)
                        id_list.append(f_id)
                        event_namedict[f_id] = event_name
                    self.feat_id = self.lrs_layer.selection_reselect(id_list, event_names_multiple,
                                                                     "Move Event", "Choose an Event to move:")
                    if self.feat_id is not None:
                        event_name = event_namedict.get(self.feat_id)
                else:
                    self.feat_id = values[0][1]
                    event_id = cont_event_names.event_id_get(None, values[0][2])
                    event_name = cont_event_names.event_name_get(event_id)
                if self.feat_id is None:
                    return
                self.eventnamesdockwidget.event_name_select(event_name)
        else:
            if self.feat_id is None:
                return
            # check for selected route
            if not self.route_select():
                self.tool_reset()
                return
            valuelist = self.route_class.selection_values_get(['route_id', 'sortnr'])
            route_id = valuelist[0][0]
            sortnr = valuelist[0][1]
            # check, if selected route is the same
            if route_id != self.lrs_layer.selection_values_get(["route_id"])[0][0]:
                text = "Move the point along the same route."
                self.message_show(text, 2)
                self.tool_reset()
                return
            event_list = self.lrs_layer.events_get(route_id, True)
            result = self.route_class.point_meas_get(route_id, self.point, self.lrs_project.srid, sortnr)
            meas = result[1]
            if meas <= self.lrs_project.tolerance:
                # event at the beginning not allowed
                self.message_show("No Event at the beginning of the route allowed.", 2)
            else:
                feat_id_old = None
                tomeas = 0
                for event in event_list:
                    if event[0] == self.feat_id:
                        if feat_id_old is None:
                            self.message_show("An Event at the end of the route can not be moved.", 2)
                        else:
                            frommeas = event[2]
                            minmeas = frommeas + self.lrs_project.tolerance
                            maxmeas = tomeas - self.lrs_project.tolerance
                            if meas <= minmeas or meas >= maxmeas:
                                self.message_show("An Event must be moved between existing Events.", 2)
                            else:
                                self.lrs_layer.event_move(self.feat_id, result[0], frommeas, meas, result[2],
                                                          feat_id_old)
                        break
                    tomeas = event[3]
                    feat_id_old = event[0]

            self.tool_reset()
        self.canvas.redrawAllLayers()

    def event_name_changed(self, event_uuid):
        if self.lrs_layer is not None:
            if self.lrs_layer.selection_count_get() == 1:
                values = self.lrs_layer.selection_values_get(["id", "event_id", "route_id"])
                if event_uuid != values[0][1]:
                    feat_id = values[0][0]
                    self.lrs_layer.event_attribute_update(feat_id, "event_id", event_uuid)
                    # info same event name
                    # get all events along the route, tomeas descending
                    event_list = self.lrs_layer.events_get(values[0][2], True)
                    # get position of event
                    ind = [i for i, event in enumerate(event_list) if feat_id == event[0]][0]
                    text = ""
                    if ind == 0:
                        # last event of the route
                        # check only if route has more than one event
                        if len(event_list) > 1:
                            if event_uuid == event_list[ind + 1][1]:
                                text = "The previous Event Point has the same Event Name."
                    elif ind == len(event_list) - 1:
                        # first event of the route
                        if event_uuid == event_list[ind - 1][1]:
                            text = "The following Event Point has the same Event Name."
                    else:
                        event_uuid_prev = event_list[ind - 1][1]
                        event_uuid_next = event_list[ind + 1][1]
                        if event_uuid == event_uuid_prev and event_uuid == event_uuid_next:
                            text = "Previous and following Event Points have the same Event Name."
                        elif event_uuid == event_uuid_prev:
                            text = "The following Event Point has the same Event Name."
                        elif event_uuid == event_uuid_next:
                            text = "The previous Event Point has the same Event Name."
                    if text:
                        self.iface.messageBar().pushInfo("Same Event Name", text)
                    self.tool_reset()

    def selection_changed(self):
        if self.lrs_layer is not None:
            if self.lrs_layer.selection_count_get() == 0:
                self.tool_reset()
                return

    def tool_reset(self):
        self.feat_id = None
        self.feat_uuid = None
        self.route_class.selection_remove()
        if self.lrs_layer is not None:
            self.lrs_layer.selection_remove()
        if self.event_class_type == "p":
            self.lrs_layer_bp.selection_remove()
        elif self.event_class_type == "c":
            self.eventnamesdockwidget.event_name_deselect()

    def keyPressEvent(self, key_event):
        if key_event.key() == Qt.Key_Escape:
            self.snapmarker_remove()
            self.tool_reset()

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
        self.tool_reset()
        if self.tourmarker is not None:
            self.tourmarker.remove()
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
        try:
            self.iface.activeLayer().selectionChanged.disconnect(self.selection_changed)
        except TypeError:
            pass
        try:
            self.eventnamesdockwidget.listwidget_clicked.disconnect(self.event_name_changed)
        except TypeError:
            pass
        self.conn_close()
