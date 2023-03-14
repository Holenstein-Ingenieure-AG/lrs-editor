# -*- coding: utf-8 -*-
"""
/***************************************************************************
    name             :  LRS-Editor
    description      :  QGIS plugin for editing linear reference systems
    begin            :  2021-07-06
    copyright        :  (C) 2021 by Reto Meier (Holenstein Ingenieure AG)
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
from qgis.gui import QgsVertexMarker
from ..utils import qgis_utils


class Tourmarker:
    def __init__(self, iface):
        self.canvas = iface.mapCanvas()
        self.datalist = None
        self.startpoint = False
        self.tourmarker = None

        vertex_items = [i for i in self.canvas.scene().items() if issubclass(type(i), QgsVertexMarker)]
        tourmarker_items = []
        for vertex_item in vertex_items:
            if vertex_item.data(1) == "Tourmarker":
                tourmarker_items.append(vertex_item)
        if len(tourmarker_items) == 1:
            self.tourmarker = tourmarker_items[0]
            self.datalist = self.tourmarker.data(3)

            if self.tourmarker.data(2) == "Startpoint":
                self.startpoint = True
            else:
                self.startpoint = False

    def startpoint_set(self, point, datalist):
        self.startpoint = True
        self.tourmarker = qgis_utils.digimarker_get(self.canvas, point)
        self.tourmarker.setData(1, "Tourmarker")
        self.tourmarker.setData(2, "Startpoint")
        self.tourmarker.setData(3, datalist)
        self.tourmarker.setVisible(True)

    def endpoint_set(self, point, datalist):
        self.startpoint = False
        self.tourmarker = qgis_utils.digimarker_get(self.canvas, point)
        self.tourmarker.setData(1, "Tourmarker")
        self.tourmarker.setData(2, "Endpoint")
        self.tourmarker.setData(3, datalist)
        self.tourmarker.setVisible(False)

    def point_get(self):
        return self.tourmarker.center()

    def remove(self):
        self.canvas.scene().removeItem(self.tourmarker)

    def startpoint(self):
        return self.startpoint

    def datalist_get(self):
        return self.datalist
