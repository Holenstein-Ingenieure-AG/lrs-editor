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
from qgis.PyQt.QtWidgets import QApplication, QInputDialog, QLineEdit, QMessageBox

from ..utils import qgis_utils
from ..utils.tourmarker import Tourmarker
from ..tools.lrsmaptool import LRSMapTool
from ..cls.lrsconteventclass import LRSContEventClass
from ..cls.lrspointeventclass import LRSPointEventClass
from ..cls.lrsbasepointeventclass import LRSBasePointEventClass
from ..cls.lrstoureventclass import LRSTourEventClass
from ..cls.lrseventnamesclass import LRSEventNamesClass


class LRSDigiTool(LRSMapTool):
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

        self.eventnamesdockwidget = eventnamesdockwidget

        self.tourmarker = None
        self.route_class.selection_remove()

    def canvas_clicked_connect(self, point, rect, event_class_name, event_class_type):
        self.point = point
        self.rect = rect
        self.event_class_name = event_class_name
        self.event_class_type = event_class_type
        if event_class_type == "p":
            self.point_event_digitize()
        elif event_class_type == "c":
            self.cont_event_digitize()
        elif event_class_type == "t":
            self.tour_event_digitize()

    def tour_event_digitize(self):
        layer_mt = qgis_utils.layer_by_tablename_get(self.schema, self.event_class_name + "_mt")
        if not layer_mt:
            self.message_show("An Event Layer is missing.", 2)
            return

        self.lrs_layer = LRSTourEventClass(self.pg_conn, self.schema, self.iface.activeLayer())
        tour_event_names = LRSEventNamesClass(self.pg_conn, self.schema, self.event_class_name, "t")

        self.tourmarker = Tourmarker(self.iface)
        datalist = self.tourmarker.datalist_get()

        if datalist is None:
            if not self.route_select():
                self.route_class.selection_remove()
                return
            event_name = None
            event_names_unused = self.lrs_layer.events_withoutgeom_get()
            # choose event name without geom
            if len(event_names_unused) > 0:
                event_name, okpressed = QInputDialog.getItem(self.eventnamesdockwidget, "New Event Name",
                                                             "Choose an existing Event Name:", event_names_unused, 0,
                                                             False)
                if not okpressed:
                    event_name = None
            # set new event name
            if event_name is None:
                event_name, okpressed = QInputDialog.getText(self.eventnamesdockwidget, "New Event Name",
                                                             "Set a new Event Name:", QLineEdit.Normal, "")
                if not okpressed or event_name == '':
                    self.route_class.selection_remove()
                    return
                names_list = [val.lower() for val in tour_event_names.event_names.values()]
                while event_name.lower() in names_list:
                    self.message_show("Event Name already exists.", 2)
                    event_name, okpressed = QInputDialog.getText(self.eventnamesdockwidget, "New Event Name",
                                                                 "Set a new Event Name:", QLineEdit.Normal, "")
                    if not okpressed or event_name == '':
                        self.route_class.selection_remove()
                        return

                # add new event name
                tour_event_names.event_name_add(event_name)
            if event_name is None:
                self.route_class.selection_remove()
                return

            valuelist = self.route_class.selection_values_get(['route_id', 'sortnr'])
            route_id = valuelist[0][0]
            sortnr = valuelist[0][1]
            # set first tourmarker with toursortnr 1
            self.tourmarker.startpoint_set(self.point, [route_id, sortnr, event_name, 1])
        else:
            # must be before any other dialog
            modifiers = QApplication.keyboardModifiers()

            if not self.route_select():
                self.route_class.selection_remove()
                return
            valuelist = self.route_class.selection_values_get(['route_id', 'sortnr'])
            if self.tourmarker.startpoint:
                route_id_fi, sortnr_fi, event_name, toursortnr = datalist[0], datalist[1], datalist[2], datalist[3]
                route_id_se = valuelist[0][0]
                sortnr_se = valuelist[0][1]

                if route_id_fi != route_id_se:
                    self.message_show("The endpoint of the part is not along the same route.", 3)
                    # self.tourmarker_remove()
                    self.route_class.selection_remove()
                    return

                qgis_point_fi = self.tourmarker.point_get()

                meas_fi = self.route_class.point_meas_get(route_id_fi, qgis_point_fi, self.lrs_project.srid,
                                                          sortnr_fi)[1]
                meas_se = self.route_class.point_meas_get(route_id_se, self.point, self.lrs_project.srid,
                                                          sortnr_se)[1]

                if abs(meas_fi - meas_se) <= self.lrs_project.tolerance:
                    # event at an existing event position
                    self.message_show("An Event already exists at this position.", 2)
                    return

                event_id = tour_event_names.event_id_get(event_name)
                event_uuid = tour_event_names.event_uuid_get(event_id)

                self.lrs_layer.event_insert(qgis_point_fi, self.point, int(sortnr_fi), sortnr_se, event_uuid,
                                            route_id_fi, self.route_class, toursortnr, self.lrs_project.srid)
                self.tourmarker.remove()

                if modifiers == Qt.ShiftModifier:
                    # continue tour when Shift is pressed, increase toursortnr
                    self.tourmarker.endpoint_set(self.point, [route_id_se, sortnr_se, event_name, toursortnr + 1])
            else:
                # tour has continued, set new startpoint
                event_name = datalist[2]
                toursortnr = datalist[3]
                self.tourmarker.remove()
                self.tourmarker.startpoint_set(self.point, [valuelist[0][0], valuelist[0][1], event_name, toursortnr])

        self.route_class.selection_remove()
        self.canvas.redrawAllLayers()

    def point_event_digitize(self):
        layer_bp = qgis_utils.layer_by_tablename_get(self.schema, self.event_class_name + "_bp")
        if not layer_bp:
            self.message_show("An Event Layer is missing.", 2)
            return
        # must be before any other dialog
        modifiers = QApplication.keyboardModifiers()

        # select route(s)
        lines_count = self.route_class.selection_count_get()
        if lines_count == 0:
            self.route_class.select_by_rect(self.rect, "set")
            lines_count = self.route_class.selection_count_get()
            if lines_count == 0:
                self.message_show("Select at least one route.", 2)
            return
        elif lines_count > 0:
            if modifiers == Qt.ShiftModifier:
                self.route_class.select_by_rect(self.rect, "add")
                return
            elif modifiers == Qt.ControlModifier:
                self.route_class.select_by_rect(self.rect, "remove")
                return

        self.lrs_layer = LRSPointEventClass(self.pg_conn, self.schema, self.iface.activeLayer())
        self.lrs_layer_bp = LRSBasePointEventClass(self.pg_conn, self.schema, layer_bp)

        event_id = None
        event_names_unused = self.lrs_layer.events_withoutgeom_get()
        # choose event name without geom
        if len(event_names_unused) > 0:
            name_new, okpressed = QInputDialog.getItem(self.eventnamesdockwidget, "New Event Name",
                                                       "Choose an existing Event Name:", event_names_unused, 0, False)
            if okpressed:
                event_id = self.lrs_layer.event_id_get(name_new)
        # set new event name
        if event_id is None:
            name_new, okpressed = QInputDialog.getText(self.eventnamesdockwidget, "New Event Name",
                                                       "Set a new Event Name:", QLineEdit.Normal, "")
            if not okpressed or name_new == '':
                self.route_class.selection_remove()
                return
            names_list = [val.lower() for val in self.lrs_layer.event_names.values()]
            while name_new.lower() in names_list:
                self.message_show("Event Name already exists.", 2)
                name_new, okpressed = QInputDialog.getText(self.eventnamesdockwidget, "New Event Name",
                                                           "Set a new Event Name:", QLineEdit.Normal,
                                                           name_new)
                if not okpressed or name_new == '':
                    self.route_class.selection_remove()
                    return
            # add new event name
            try:
                event_id = self.lrs_layer.event_name_add(name_new)
            except Exception as error:
                # insertion error, e.g. user-defined not-null-fields
                msg = QMessageBox(QMessageBox.Critical, "New Event Name", str(error), QMessageBox.Ok)
                msg.exec_()

        if event_id is None:
            self.route_class.selection_remove()
            return

        self.lrs_layer.event_insert(event_id, self.point)

        # get routelist with unique route_id
        routelist = list(set([value[0] for value in self.route_class.selection_values_get(['route_id'])]))
        event_uuid = self.lrs_layer.event_uuid_get(event_id)
        self.lrs_layer_bp.basepoints_insert(self.point, self.route_class, event_uuid, routelist, self.lrs_project.srid)

        self.route_class.selection_remove()
        self.canvas.redrawAllLayers()

    def cont_event_digitize(self):
        # select event name and route
        selected = False
        event_uuid = self.eventnamesdockwidget.event_uuid_selected_get()
        if event_uuid:
            selected = self.route_select()
        else:
            self.message_show("Choose an Event Name.", 2)
        if not selected:
            self.route_class.selection_remove()
            return

        valuelist = self.route_class.selection_values_get(['route_id', 'sortnr'])
        route_id = valuelist[0][0]
        sortnr = valuelist[0][1]
        self.lrs_layer = LRSContEventClass(self.pg_conn, self.schema, self.iface.activeLayer())
        # get all events along the route, tomeas ascending
        event_list = self.lrs_layer.events_get(route_id)

        # insert the point and update measures along the route
        if len(event_list) == 0:
            # no event until now -> set at route end
            result = self.route_class.point_routeend_get(route_id)
            self.lrs_layer.event_insert(result[0], route_id, event_uuid, 0, result[1], result[2])
        else:
            result = self.route_class.point_meas_get(route_id, self.point, self.lrs_project.srid, sortnr)
            meas = result[1]
            if meas <= self.lrs_project.tolerance:
                # event at the beginning not allowed
                self.message_show("No Event at the beginning of the route allowed.", 2)
            else:
                # get new frommeas
                frommeas = 0
                event_uuid_old = None
                for event in event_list:
                    tomeas = event[3]
                    if abs(meas - tomeas) <= self.lrs_project.tolerance:
                        # event at an existing event position
                        self.message_show("An Event already exists at this position.", 2)
                        break
                    else:
                        if meas > tomeas:
                            # continue loop
                            frommeas = tomeas
                        elif meas < tomeas:
                            # insert point snapped to the route
                            self.lrs_layer.event_insert(result[0], route_id, event_uuid, frommeas,
                                                        meas, result[2], event[0])
                            # info same event name
                            text = ""
                            if event_uuid == event_uuid_old and event_uuid == event[1]:
                                text = "Previous and following Event Points have the same Event Name."
                            elif event_uuid == event_uuid_old:
                                text = "The previous Event Point has the same Event Name."
                            elif event_uuid == event[1]:
                                text = "The following Event Point has the same Event Name."
                            if text:
                                self.iface.messageBar().pushInfo("Same Event Name", text)
                            break
                    event_uuid_old = event[1]

        self.route_class.selection_remove()
        self.canvas.redrawAllLayers()

    def keyPressEvent(self, key_event):
        if key_event.key() == Qt.Key_Escape:
            self.snapmarker_remove()
            self.route_class.selection_remove()

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

        self.route_class.selection_remove()
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
        self.conn_close()
