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
from qgis.PyQt.QtWidgets import QDockWidget

from ..utils import qgis_utils
from ..utils.pg_conn import PGConn
from ..cls.lrsproject import LRSProject
from ..cls.lrseventclasses import LRSEventClasses
from ..cls.lrsbasepointeventclass import LRSBasePointEventClass
from ..cls.lrsconteventclass import LRSContEventClass
from ..cls.lrstoureventclass import LRSTourEventClass

FORM_CLASS, _ = loadUiType(os.path.join(
    os.path.dirname(__file__), os.pardir, 'ui', 'eventapprovaldockwidget.ui'))


class EventApprovalDockWidget(QDockWidget, FORM_CLASS):
    def __init__(self, parent, iface):
        # call superclass constructor
        super(EventApprovalDockWidget, self).__init__(parent)
        self.iface = iface
        self.canvas = iface.mapCanvas()
        self.setupUi(self)
        self.pg_conn = None
        self.schema = None
        self.lrs_project = None
        self.lrs_event_classes = None

        self.lrs_layer_old = None
        self.lrs_layer = None

        self.eventclassdict = None
        self.eventclasserrdict = None

        # config buttons
        self.pb_ok.setEnabled(True)
        self.pb_ok.clicked.connect(self.event_approve)
        self.pb_skip.setEnabled(True)
        self.pb_skip.clicked.connect(self.event_skip)

        # clear combo boxes
        self.cbx_event_class_name.clear()
        self.cbx_route_name.clear()
        self.cbx_event.clear()

        self.textEdit.clear()
        self.textEdit.hide()

        # redirect combo boxes
        self.cbx_event_class_name.currentTextChanged.connect(self.event_name_changed)
        self.cbx_route_name.currentTextChanged.connect(self.route_name_changed)
        self.cbx_event.currentTextChanged.connect(self.event_changed)

    def form_update(self):
        # Initialize routine is already passed when loading the plugin
        # -> own function to update contents
        entries = qgis_utils.qgis_entries_get("project")
        if entries is None:
            return
        self.schema = entries[3]
        credentials = qgis_utils.credentials_get(entries[0])

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

        route_class_name = self.lrs_project.route_class_name
        self.eventclassdict = {}
        self.eventclasserrdict = {}
        for clid in self.lrs_event_classes.event_class_idlist:
            event_class_name = self.lrs_event_classes.event_class_names[clid]
            lrs_l = None
            if self.lrs_event_classes.event_class_types[clid] == "p":
                layer = qgis_utils.layer_by_tablename_get(self.schema, event_class_name + "_bp")
                lrs_l = LRSBasePointEventClass(self.pg_conn, self.schema, layer)
            elif self.lrs_event_classes.event_class_types[clid] == "c":
                layer = qgis_utils.layer_by_tablename_get(self.schema, event_class_name)
                lrs_l = LRSContEventClass(self.pg_conn, self.schema, layer)
            elif self.lrs_event_classes.event_class_types[clid] == "t":
                layer = qgis_utils.layer_by_tablename_get(self.schema, event_class_name)
                lrs_l = LRSTourEventClass(self.pg_conn, self.schema, layer)
            tolerance = self.lrs_project.tolerance
            routedict, routeerrdict = lrs_l.events_approvable_get(route_class_name, tolerance, False)

            # add only, if not empty
            if bool(routedict):
                self.eventclassdict[event_class_name] = routedict
            if bool(routeerrdict):
                self.eventclasserrdict[event_class_name] = routeerrdict

        event_class_names = []
        for key, val in self.eventclassdict.items():
            event_class_names.append(key)

        self.cbx_event_class_name.clear()
        self.cbx_route_name.clear()
        self.cbx_event.clear()
        for event_class_name in sorted(event_class_names):
            self.cbx_event_class_name.addItem(event_class_name)

    def event_name_changed(self):
        # ignore signal, when combo box with event class name is cleared
        if len(self.cbx_event_class_name.currentText()) == 0:
            return

        routedict = self.eventclassdict[self.cbx_event_class_name.currentText()]
        self.cbx_route_name.clear()
        for key, val in sorted(routedict.items()):
            self.cbx_route_name.addItem(key)

    def route_name_changed(self):
        # ignore signal, when combo box with route name is cleared
        if len(self.cbx_route_name.currentText()) == 0:
            return

        routedict = self.eventclassdict[self.cbx_event_class_name.currentText()]
        events = routedict[self.cbx_route_name.currentText()]
        self.cbx_event.clear()

        # events are already sorted
        for val in events:
            self.cbx_event.addItem(val)

        # check for routes with error
        self.textEdit.clear()
        self.textEdit.hide()
        routeerrdict = self.eventclasserrdict.get(self.cbx_event_class_name.currentText(), None)
        if bool(routeerrdict):
            routeerrlist = routeerrdict.get(self.cbx_route_name.currentText(), None)
            if routeerrlist is not None:
                self.textEdit.append("ERROR: Measures along route " + self.cbx_route_name.currentText() + " are "
                                     "not correct.")
                self.textEdit.append("")
                self.textEdit.append("Check the order of following Event Points:")
                for val in routeerrlist:
                    self.textEdit.append(val)
                self.textEdit.show()

    def event_changed(self):
        # ignore signal, when combo box with events is cleared
        if len(self.cbx_event.currentText()) == 0:
            return

        self.event_select()

    def event_select(self):
        event_class_name = self.cbx_event_class_name.currentText()
        feat_id = int(self.cbx_event.currentText().split(":")[0])
        event_class_type = self.lrs_event_classes.event_class_type_get(event_class_name)

        if self.lrs_layer_old is not None:
            try:
                self.lrs_layer_old.selection_remove()
            except RuntimeError:
                pass

        self.lrs_layer = None
        if event_class_type == "p":
            layer = qgis_utils.layer_by_tablename_get(self.schema, event_class_name + "_bp")
            self.lrs_layer = LRSBasePointEventClass(self.pg_conn, self.schema, layer)
        elif event_class_type == "c":
            layer = qgis_utils.layer_by_tablename_get(self.schema, event_class_name)
            self.lrs_layer = LRSContEventClass(self.pg_conn, self.schema, layer)
        elif event_class_type == "t":
            layer = qgis_utils.layer_by_tablename_get(self.schema, event_class_name)
            self.lrs_layer = LRSTourEventClass(self.pg_conn, self.schema, layer)

        self.lrs_layer.select_by_id(feat_id)
        self.canvas.zoomToSelected(self.lrs_layer.qgslayer)
        self.lrs_layer_old = self.lrs_layer

    def event_approve(self):
        event = self.cbx_event.currentText()
        index = self.cbx_event.findText(event)
        routedict = self.eventclassdict[self.cbx_event_class_name.currentText()]
        events = routedict[self.cbx_route_name.currentText()]

        try:
            # can cause error, when list is empty
            events.remove(event)
            # causes no error when box is empty
            self.cbx_event.removeItem(index)
            feat_id = int(event.split(":")[0])
            self.lrs_layer.event_approve(feat_id)
            if len(events) == 0:
                self.lrs_layer.selection_remove()
        except ValueError:
            self.lrs_layer.selection_remove()
            pass

    def event_skip(self):
        event = self.cbx_event.currentText()
        index = self.cbx_event.findText(event)
        if index == self.cbx_event.count() - 1:
            self.cbx_event.setCurrentIndex(0)
        else:
            self.cbx_event.setCurrentIndex(index + 1)

    def conn_close(self):
        if self.pg_conn:
            self.pg_conn.db_close()
            self.pg_conn = None

    def closeEvent(self, event):
        # dialog closed with X-button
        # overrides method in QDialog
        self.conn_close()
