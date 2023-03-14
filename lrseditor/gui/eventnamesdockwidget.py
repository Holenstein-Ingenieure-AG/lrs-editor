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
import locale

from qgis.PyQt.uic import loadUiType
from qgis.PyQt.QtWidgets import QDockWidget, QAbstractItemView
from qgis.PyQt.QtCore import Qt, pyqtSignal

from ..utils import qgis_utils
from ..utils.pg_conn import PGConn
from ..cls.lrseventnamesclass import LRSEventNamesClass

FORM_CLASS, _ = loadUiType(os.path.join(
    os.path.dirname(__file__), os.pardir, 'ui', 'eventnamesdockwidget.ui'))


class EventNamesDockWidget(QDockWidget, FORM_CLASS):
    # configure signal, when list is clicked
    listwidget_clicked = pyqtSignal(str)

    def __init__(self, parent, iface):
        # call superclass constructor
        super(EventNamesDockWidget, self).__init__(parent)
        self.iface = iface
        self.setupUi(self)
        self.pg_conn = None
        self.cont_event_names = None
        self.event_names = None

    def form_update(self):
        # Initialize routine is already passed when loading the plugin
        # -> own function to update contents
        entries = qgis_utils.qgis_entries_get("project")
        if entries is None:
            return
        schema = entries[3]
        credentials = qgis_utils.credentials_get(entries[0])

        if credentials is None:
            self.iface.messageBar().pushWarning("No Connection", "Missing credentials.")
            return
        self.pg_conn = PGConn(entries[1], entries[2], entries[4], credentials[0], credentials[1])
        return_message = self.pg_conn.db_connect()
        if return_message:
            self.iface.messageBar().pushWarning("No Connection", "No connection established.")
            return

        event_class_name = qgis_utils.tablename_by_layername_get(schema, self.iface.activeLayer().name)
        self.txt_event_class_name.setText(event_class_name)
        self.cont_event_names = LRSEventNamesClass(self.pg_conn, schema, event_class_name, "c")

        # connect search
        self.le_event_name.setText("")
        self.le_event_name.textChanged.connect(self.text_changed)
        self.listWidget.currentItemChanged.connect(self.currentitem_changed)

        self.listWidget.clear()
        # convert into sorted list (case insensitive)
        self.event_names = list(self.cont_event_names.event_names.values())
        # this does not consider german umlauts...
        # self.event_names.sort(key=lambda y: y.lower())
        self.event_names.sort(key=locale.strxfrm)
        self.listWidget.addItems(self.event_names)

    def text_changed(self):
        # call search function
        self.item_search(self.le_event_name.text())

    def item_search(self, value):
        # search function
        self.listWidget.clear()
        self.listWidget.addItems(self.event_names)
        items = self.listWidget.findItems(value, Qt.MatchContains)
        if items is not None:
            foundlist = [item.text() for item in items]
            self.listWidget.clear()
            self.listWidget.addItems(foundlist)

    def event_uuid_selected_get(self):
        itemslist = self.listWidget.selectedItems()
        if len(itemslist) == 1:
            event_id = self.cont_event_names.event_id_get(itemslist[0].text())
            return self.cont_event_names.event_uuid_get(event_id)
        else:
            return None

    def event_name_deselect(self):
        for i in range(self.listWidget.count()):
            item = self.listWidget.item(i)
            item.setSelected(False)

    def event_name_select(self, event_name):
        # catch IndexError, if in the map an event point is selected, which
        # event_name in listWidget does not exist
        try:
            item = self.listWidget.findItems(event_name, Qt.MatchRegExp)[0]
        except IndexError:
            self.le_event_name.setText("")
            item = self.listWidget.findItems(event_name, Qt.MatchRegExp)[0]

        # releases currentitem_changed:
        self.listWidget.setCurrentItem(item)
        # item.setSelected(True)
        self.listWidget.scrollToItem(item, QAbstractItemView.PositionAtTop)
        self.listWidget.setFocus()

        # for x in range(self.listWidget.count()):
        #     if self.listWidget.item(x).text() == event_name:
        #         self.listWidget.item(x).setSelected(True)
        #         break

    def currentitem_changed(self, current):
        if current is not None:
            event_name = current.text()
            event_id = self.cont_event_names.event_id_get(event_name)
            event_uuid = self.cont_event_names.event_uuid_get(event_id)
            self.listwidget_clicked.emit(event_uuid)

    def conn_close(self):
        if self.pg_conn:
            self.pg_conn.db_close()
            self.pg_conn = None

    def closeEvent(self, event):
        # dialog closed with X-button
        # overrides method in QDialog
        self.conn_close()
