# -*- coding: utf-8 -*-
"""
/***************************************************************************
    name             :  LRS-Editor
    description      :  QGIS plugin for editing linear reference systems
    begin            :  2021-06-28
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
from ..utils import misc_utils


class LRSEventNamesClass:

    def __init__(self, pg_conn, schema, event_class_name, event_class_type):
        self.__schema = schema
        self.__pg_conn = pg_conn
        self.__event_class_type = event_class_type
        self.__event_class_name = event_class_name

        self.__table_et_name = self.__event_class_name + "_et"
        self.__uuiddict = {}
        self.__namedict = {}
        self.__useddict = {}

        fields = "et.id, et.name, et.uuid"
        countfield = "val.id"
        tablename_a = self.__table_et_name + " et"
        if self.__event_class_type == "c":
            tablename_b = self.__event_class_name + " val"
        else:
            tablename_b = self.__event_class_name + "_mt" + " val"

        a_id_field = "et.uuid"
        b_id_field = "val.event_id"
        group = "et.id"
        event_names = self.__pg_conn.table_select_count_leftjoin(self.__schema, tablename_a, tablename_b, fields,
                                                                 countfield, a_id_field, b_id_field, group)

        for event_name in event_names:
            self.__uuiddict[event_name[0]] = event_name[2]
            self.__namedict[event_name[0]] = event_name[1]
            self.__useddict[event_name[0]] = event_name[3]

    def event_names_unreferenced(self):
        # get event points or event uuid where event names not exist
        a_id_field = "val.event_id"
        b_id_field = "et.uuid"
        if self.__event_class_type == "c":
            fields = "val.event_id, val.geom"
            group = "val.event_id, val.geom"
            tablename_a = self.__event_class_name + " val"
        else:
            fields = "val.event_id, val.uuid"
            group = "val.event_id, val.uuid"
            tablename_a = self.__event_class_name + "_mt" + " val"
        tablename_b = self.__table_et_name + " et"
        countfield = "val.event_id"
        where = "et.uuid IS NULL"

        return self.__pg_conn.table_select_count_leftjoin(self.__schema, tablename_a, tablename_b, fields,
                                                          countfield, a_id_field, b_id_field, group, where)

    def event_name_add(self, event_name):
        now_utc = misc_utils.datetime_utc_get()
        uuid = misc_utils.uuid_get()
        fields = "uuid, name, createtstz, changetstz"
        # replace single quotes
        value = event_name.replace("'", "''")
        values = "'{}', '{}', '{}', '{}'".format(uuid, value, now_utc, now_utc)
        # return new id
        event_name_id = self.__pg_conn.table_insert(self.__schema, self.__table_et_name, fields, values, "id")

        self.__uuiddict[event_name_id] = uuid
        self.__namedict[event_name_id] = event_name
        self.__useddict[event_name_id] = "0"
        return event_name_id

    def event_name_delete(self, event_name_id):
        where = "id = " + str(event_name_id)
        self.__pg_conn.table_delete_row(self.__schema, self.__table_et_name, where)
        # no idea why here int() must be used...
        self.__uuiddict.pop(int(event_name_id))
        self.__namedict.pop(int(event_name_id))
        self.__useddict.pop(int(event_name_id))

    def event_name_change(self, event_name, event_name_id):
        now_utc = misc_utils.datetime_utc_get()
        where = "id = " + str(event_name_id)
        # replace single quotes
        value = event_name.replace("'", "''")
        expression = "name = '" + value + "', changetstz = '" + now_utc + "'"
        self.__pg_conn.table_update1(self.__schema, self.__table_et_name, expression, where)
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

    def event_view_exists(self, viewname):
        return self.__pg_conn.view_exists(self.__schema, viewname)

    # get properties
    @property
    def event_names(self):
        return self.__namedict

    @property
    def event_names_used(self):
        return self.__useddict

    @property
    def event_class_type(self):
        return self.__event_class_type

    @property
    def event_class_name(self):
        return self.__event_class_name
