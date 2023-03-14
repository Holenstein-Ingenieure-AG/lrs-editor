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

from ..tools.lrstool import LRSTool

from ..utils import qgis_utils
from ..cls.lrseventnamesclass import LRSEventNamesClass
from ..cls.lrspointeventclass import LRSPointEventClass
from ..gui.eventnamesmanager import EventNamesManager


class LRSEventNamesAdmin(LRSTool):
    def __init__(self, iface):
        # call superclass constructor (both ways possible)
        LRSTool.__init__(self, iface)

    def dialog_show(self):
        if not self.lrs_project:
            return
        event_class_name = qgis_utils.tablename_by_layername_get(self.schema, self.iface.activeLayer().name)

        event_class_type = self.lrs_event_classes.event_class_type_get(event_class_name)
        if event_class_type is None:
            return

        event_names_class = None
        if event_class_type == "c":
            event_names_class = LRSEventNamesClass(self.pg_conn, self.schema, event_class_name, "c")
        elif event_class_type == "p":
            event_names_class = LRSPointEventClass(self.pg_conn, self.schema, self.iface.activeLayer())
        elif event_class_type == "t":
            event_names_class = LRSEventNamesClass(self.pg_conn, self.schema, event_class_name, "t")

        if event_names_class is None:
            return
        dlg = EventNamesManager(self.iface, event_names_class)
        dlg.exec_()
