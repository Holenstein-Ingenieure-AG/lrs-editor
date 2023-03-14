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
from qgis.PyQt.QtWidgets import QInputDialog, QWidget
from qgis.core import QgsFeatureRequest

from ..utils import misc_utils, qgis_utils


class LRSLayerClass:

    def __init__(self, layer):
        self.__layer = layer

    def select_by_id(self, feat_id):
        self.__layer.removeSelection()
        self.__layer.select(feat_id)

    def select_by_rect(self, rect, selection_behavior):
        qgis_utils.layer_select_by_rect(self.__layer, rect, selection_behavior)

        return self.__layer.selectedFeatureCount()

    def feature_id_get(self, fieldname, value):
        request = QgsFeatureRequest().setFlags(QgsFeatureRequest.NoGeometry)
        request.setSubsetOfAttributes([fieldname], self.__layer.fields())
        if isinstance(value, str):
            expression = fieldname + " = \'" + value + "'"
        else:
            expression = fieldname + ' = ' + str(value)
        request.setFilterExpression(expression)
        selection = self.__layer.getFeatures(request)
        return [s.id() for s in selection]

    def select_by_attribute_value(self, fieldname, value):
        request = QgsFeatureRequest().setFlags(QgsFeatureRequest.NoGeometry)
        request.setSubsetOfAttributes([fieldname], self.__layer.fields())
        if isinstance(value, str):
            expression = fieldname + " = \'" + value + "'"
        else:
            expression = fieldname + ' = ' + str(value)
        request.setFilterExpression(expression)
        selection = self.__layer.getFeatures(request)
        self.__layer.selectByIds([s.id() for s in selection])
        return self.__layer.selectedFeatureCount()

    def selection_count_get(self):
        return self.__layer.selectedFeatureCount()

    def selection_remove(self):
        self.__layer.removeSelection()

    def selection_values_get(self, fieldnames):
        return qgis_utils.layer_selection_values_get(self.__layer, fieldnames)

    def selection_reselect(self, feat_id_list, items, title, text):
        # returns index, order in items and the id-list must be the same
        qwidget = QWidget()
        item_chosen, okpressed = QInputDialog.getItem(qwidget, title, text, items, 0, False)
        feat_id = None
        if okpressed:
            ind = items.index(item_chosen)
            feat_id = feat_id_list[ind]
            self.__layer.selectByIds([feat_id])
        else:
            self.selection_remove()
        return feat_id

    def feature_get_by_id(self, feat_id):
        return self.__layer.getFeature(feat_id)

    def attribute_values_change(self, feat_id, values_dict):
        map_dict = {}
        for key, val in values_dict.items():
            ind = self.__layer.fields().indexFromName(key)
            map_dict[ind] = val
        return self.__layer.changeAttributeValues(feat_id, map_dict)

    def attribute_value_change(self, feat_id, fieldname, value):
        ind = self.__layer.fields().indexFromName(fieldname)
        return self.__layer.changeAttributeValue(feat_id, ind, value)

    def editing_start(self):
        if not self.__layer.isEditable():
            self.__layer.startEditing()

    def changes_commit(self, editing_stop=True):
        if self.__layer.isEditable():
            self.__layer.commitChanges(editing_stop)

    def rollback(self, delete_buffer=True):
        if self.__layer.isEditable():
            self.__layer.rollBack(delete_buffer)

    def modified(self):
        return self.__layer.isModified()

    # get properties
    @property
    def datetime(self):
        return misc_utils.datetime_utc_get()

    @property
    def uuid(self):
        return str(misc_utils.uuid_get())

    @property
    def qgslayer(self):
        return self.__layer
