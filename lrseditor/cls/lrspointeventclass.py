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
import locale

from qgis.core import QgsGeometry, QgsPointXY, QgsFeatureRequest

from ..cls.lrslayerclass import LRSLayerClass
from ..utils import qgis_utils


class LRSPointEventClass(LRSLayerClass):

    def __init__(self, pg_conn, schema, layer):
        LRSLayerClass.__init__(self, layer)
        self.__schema = schema
        self.__layer = layer
        self.__pg_conn = pg_conn
        self.__event_class_name = qgis_utils.tablename_by_layername_get(self.__schema, self.__layer.name)
        self.__table_bp_name = self.__event_class_name + "_bp"
        self.__uuiddict = None
        self.__namedict = None
        self.__bp_countdict = None
        self.__useddict = None

        self.__data_get()

    def __data_get(self):
        self.__uuiddict = {}
        self.__namedict = {}
        self.__bp_countdict = {}
        self.__useddict = {}

        fields = "val.id, val.name, val.geom, val.uuid"
        countfield = "bp.id"
        tablename_a = self.__event_class_name + " val"
        tablename_b = self.__table_bp_name + " bp"
        a_id_field = "val.uuid"
        b_id_field = "bp.event_id"
        group = "val.id"
        event_names = self.__pg_conn.table_select_count_leftjoin(self.__schema, tablename_a, tablename_b, fields,
                                                                 countfield, a_id_field, b_id_field, group)
        for event_name in event_names:
            self.__uuiddict[event_name[0]] = event_name[3]
            self.__namedict[event_name[0]] = event_name[1]
            self.__bp_countdict[event_name[0]] = event_name[4]
            # null geometry
            if not event_name[2]:
                self.__useddict[event_name[0]] = 0
            else:
                self.__useddict[event_name[0]] = 1

    def event_names_unreferenced(self):
        # get basepoints where the point event not exists
        fields = "bp.uuid, bp.geom, bp.event_id"
        group = "bp.uuid, bp.geom, bp.event_id"
        a_id_field = "bp.event_id"
        b_id_field = "val.uuid"
        tablename_a = self.__table_bp_name + " bp"
        tablename_b = self.__event_class_name + " val"
        countfield = "bp.event_id"
        where = "val.uuid IS NULL"

        return self.__pg_conn.table_select_count_leftjoin(self.__schema, tablename_a, tablename_b, fields,
                                                          countfield, a_id_field, b_id_field, group, where)

    def event_name_add(self, event_name):
        now_utc = self.datetime
        uuid = self.uuid
        fields = "uuid, geom, name, createtstz, changetstz"
        # replace single quotes
        value = event_name.replace("'", "''")
        values = "'{}', {}, '{}', '{}', '{}'".format(uuid, 'NULL', value, now_utc, now_utc)

        try:
            # must be inserted with SQL, not by QGIS attribute: to get new id
            event_name_id = self.__pg_conn.table_insert(self.__schema, self.__event_class_name, fields, values, "id")
        except Exception as error:
            # insertion error, e.g. user-defined not-null-fields
            self.__pg_conn.rollback()
            raise Exception(error)

        self.__uuiddict[event_name_id] = uuid
        self.__namedict[event_name_id] = event_name
        self.__bp_countdict[event_name_id] = "0"
        self.__useddict[event_name_id] = "0"
        return event_name_id

    def event_name_delete(self, event_name_id):
        where = "id = " + str(event_name_id)
        self.__pg_conn.table_delete_row(self.__schema, self.__event_class_name, where)
        # no idea why here int() must be used...
        self.__uuiddict.pop(int(event_name_id))
        self.__namedict.pop(int(event_name_id))
        self.__bp_countdict.pop(int(event_name_id))
        self.__useddict.pop(int(event_name_id))

    def event_name_change(self, event_name, event_name_id):
        where = "id = " + str(event_name_id)
        now_utc = self.datetime
        # replace single quotes
        value = event_name.replace("'", "''")
        expression = "name = '" + value + "', changetstz = '" + now_utc + "'"
        self.__pg_conn.table_update1(self.__schema, self.__event_class_name, expression, where)
        # no idea why here int() must be used...
        self.__namedict[int(event_name_id)] = event_name

    def event_id_get(self, event_name=None, event_uuid=None):
        if event_name is not None:
            for key, val in self.__namedict.items():
                if val == event_name:
                    return key
        elif event_uuid is not None:
            for key, val in self.__uuiddict.items():
                if val == event_uuid:
                    return key
        else:
            return None

    def event_name_get(self, event_id):
        for key, val in self.__namedict.items():
            if key == event_id:
                return val

    def event_uuid_get(self, event_id):
        for key, val in self.__uuiddict.items():
            if key == event_id:
                return val

    def event_sql_insert(self, event_name, qgis_point, srid, fields_list, fields_values):
        now_utc = self.datetime
        uuid = self.uuid
        fields = "uuid, geom, name, createtstz, changetstz, geomtstz"
        values = "'{uuid}', ST_SetSRID(ST_MakePoint({x}, {y}), {srid}), '{event_name}', '{now_utc}', '{now_utc}', " \
                 "'{now_utc}'" \
                 .format(uuid=uuid, x=qgis_point.x(), y=qgis_point.y(), srid=srid, event_name=event_name,
                         now_utc=now_utc)

        # additional values of fields to insert
        for i in range(len(fields_list)):
            value = fields_values[i]
            fieldname = fields_list[i]
            field_type = self.__pg_conn.field_type_get(self.__schema, self.__event_class_name, fieldname)[1]
            if value is not None:
                if field_type != 'other':
                    fields = ''.join((fields, ", ", fieldname))
                    if field_type == 'string':
                        # replace single quotes
                        value = value.replace("'", "''")
                    if field_type == 'number' or field_type == 'boolean':
                        values = ''.join((values, ", ", str(value)))
                    else:
                        values = ''.join((values, ", '", str(value), "'"))

        event_name_id = self.__pg_conn.table_insert(self.__schema, self.__event_class_name, fields, values, "id")

        self.__uuiddict[event_name_id] = uuid
        self.__namedict[event_name_id] = event_name
        self.__bp_countdict[event_name_id] = "0"
        self.__useddict[event_name_id] = "0"
        return event_name_id

    def event_insert(self, event_id, qgis_point):
        now_utc = self.datetime
        self.__layer.beginEditCommand("Insert Point Event")
        sumbool = self.__layer.changeGeometry(event_id, QgsGeometry.fromPointXY(QgsPointXY(qgis_point.x(),
                                                                                           qgis_point.y())))
        sumbool += self.attribute_value_change(event_id, 'geomtstz', now_utc)
        if sumbool != 2:
            self.__layer.destroyEditCommand()
        else:
            self.__layer.endEditCommand()
            self.__layer.updateExtents()

    def event_geom_reset(self, feat_id):
        now_utc = self.datetime
        self.__layer.beginEditCommand("Delete Point Event")
        # set geometry to NULL
        # QgsGeometry.fromWkt('Point()') does not set empty geometry (from QGIS 3.16)
        sumbool = self.__layer.changeGeometry(feat_id, QgsGeometry.fromWkt(''))
        sumbool += self.attribute_value_change(feat_id, 'geomtstz', now_utc)
        if sumbool != 2:
            self.__layer.destroyEditCommand()
        else:
            self.__layer.endEditCommand()
            self.__layer.updateExtents()

    def event_geom_sql_reset(self, event_id):
        now_utc = self.datetime
        where = "uuid = '" + event_id + "'"
        expression = """geom = NULL, geomtstz = '{utc}'""".format(utc=now_utc)
        self.__pg_conn.table_update1(self.__schema, self.__event_class_name, expression, where)

    def event_move(self, feat_id, qgis_point):
        now_utc = self.datetime
        self.__layer.beginEditCommand("Move Point Event")
        sumbool = self.__layer.changeGeometry(feat_id, QgsGeometry.fromPointXY(QgsPointXY(qgis_point.x(),
                                                                                          qgis_point.y())))
        sumbool += self.attribute_value_change(feat_id, 'geomtstz', now_utc)
        if sumbool != 2:
            self.__layer.destroyEditCommand()
        else:
            self.__layer.endEditCommand()
            self.__layer.updateExtents()

    def events_withoutgeom_get(self):
        request = QgsFeatureRequest().setFlags(QgsFeatureRequest.NoFlags)
        request.setSubsetOfAttributes(['name'], self.__layer.fields())
        selection = self.__layer.getFeatures(request)
        event_names_unused = [feat['name'] for feat in selection if not feat.hasGeometry()]
        # sort
        event_names_unused.sort(key=locale.strxfrm)
        return event_names_unused

    # get properties
    @property
    def event_class_name(self):
        return self.__event_class_name

    @property
    def event_names(self):
        return self.__namedict

    @property
    def event_names_used(self):
        return self.__useddict

    @property
    def event_bp_count(self):
        return self.__bp_countdict

    @property
    def event_class_type(self):
        return "p"
