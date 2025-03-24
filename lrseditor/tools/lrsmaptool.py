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
from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.gui import QgsMapTool
from qgis.core import QgsPointXY, QgsRectangle

from ..tools.lrstool import LRSTool
from ..utils import qgis_utils


class LRSMapTool(LRSTool, QgsMapTool):
    # configure signal, when canvas is clicked
    canvas_clicked = pyqtSignal(QgsPointXY, QgsRectangle, str, str)

    def __init__(self, iface):
        # call superclass constructor (both ways possible)
        LRSTool.__init__(self, iface)
        QgsMapTool.__init__(self, iface.mapCanvas())
        # super().__init__(iface.mapCanvas())

        self.snapmarker = None
        self.snappoint = None

    def canvasReleaseEvent(self, mouse_event):
        if self.iface.activeLayer() is None:
            return
        event_class_name = qgis_utils.tablename_by_layername_get(self.schema, self.iface.activeLayer().name)
        event_class_type = self.lrs_event_classes.event_class_type_get(event_class_name)
        snapped = self.snapped(mouse_event)
        if snapped:
            point = self.snappoint
            x = self.toCanvasCoordinates(point).x()
            y = self.toCanvasCoordinates(point).y()
        else:
            point = qgis_utils.qgis_point_get(self.canvas, mouse_event)
            x = mouse_event.pos().x()
            y = mouse_event.pos().y()

        # origin of map canvas is upper left corner
        point_min = self.canvas.getCoordinateTransform().toMapCoordinates(x - 2, y + 2)
        point_max = self.canvas.getCoordinateTransform().toMapCoordinates(x + 2, y - 2)

        rect = QgsRectangle(point_min.x(), point_min.y(), point_max.x(), point_max.y())

        self.canvas_clicked.emit(point, rect, event_class_name, event_class_type)

    def canvasMoveEvent(self, mouse_event):
        self.snapped(mouse_event)

    def snapped(self, mouse_event):
        self.snapmarker_remove()
        self.snappoint = None
        # try to snap
        point = qgis_utils.qgis_point_get(self.canvas, mouse_event)
        snapper = self.canvas.snappingUtils()
        # snap to any layer within snap tolerance
        snapmatch = snapper.snapToMap(point)
        if not snapmatch.isValid():
            return False
        else:
            self.snappoint = snapmatch.point()
            self.snapmarker = qgis_utils.snapmarker_get(self.canvas, self.snappoint)
            return True

    def snapmarker_remove(self):
        if self.snapmarker is not None:
            self.canvas.scene().removeItem(self.snapmarker)
            self.snapmarker = None

    def route_select(self):
        selected = False
        self.route_class.select_by_rect(self.rect, "set")
        lines_count = self.route_class.selection_count_get()
        if lines_count != 1:
            if lines_count > 1:
                if self.route_class.route_reselect():
                    selected = True
            else:
                self.message_show("Set a point along a route.", 2)
        else:
            selected = True
        return selected

    def activate(self):
        self.canvas.setCursor(Qt.CrossCursor)
        self.snappoint = None
