# -*- coding: utf-8 -*-
"""
/***************************************************************************
    name             :  LRS-Editor
    description      :  QGIS plugin for editing linear reference systems
    begin            :  2021-12-21
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


class LRSCheckClass:

    def __init__(self, pg_conn, schema, srid):
        self.__schema = schema
        self.__pg_conn = pg_conn

        if not self.exists:
            self.__pg_conn.table_check_class_create(self.__schema, srid)

    def insert(self, class_name, category, description, geom=None, uuid=None, route_name=None):
        if geom is not None and uuid is None and route_name is None:
            fields = "class_name, category, description, geom"
            values = "'{}', '{}', '{}', '{}'".format(class_name, category, description, geom)
        elif geom is None and uuid is not None and route_name is None:
            fields = "class_name, category, description, uuid"
            values = "'{}', '{}', '{}', '{}'".format(class_name, category, description, uuid)
        elif geom is None and uuid is None and route_name is not None:
            fields = "class_name, category, description, route_name"
            values = "'{}', '{}', '{}', '{}'".format(class_name, category, description, route_name)
        elif geom is not None and uuid is not None and route_name is None:
            fields = "class_name, category, description, geom, uuid"
            values = "'{}', '{}', '{}', '{}', '{}'".format(class_name, category, description, geom, uuid)
        elif geom is not None and uuid is None and route_name is not None:
            fields = "class_name, category, description, geom, route_name"
            values = "'{}', '{}', '{}', '{}', '{}'".format(class_name, category, description, geom, route_name)
        elif geom is None and uuid is not None and route_name is not None:
            fields = "class_name, category, description, uuid, route_name"
            values = "'{}', '{}', '{}', '{}', '{}'".format(class_name, category, description, uuid, route_name)
        elif geom is not None and uuid is not None and route_name is not None:
            fields = "class_name, category, description, geom, uuid, route_name"
            values = "'{}', '{}', '{}', '{}', '{}', '{}'".format(class_name, category, description, geom,
                                                                 uuid, route_name)
        else:
            fields = "class_name, category, description"
            values = "'{}', '{}', '{}'".format(class_name, category, description)
        self.__pg_conn.table_insert(self.__schema, "lrs_check_class", fields, values)

    def truncate(self):
        self.__pg_conn.table_truncate(self.__schema, "lrs_check_class")

    @property
    def exists(self):
        return self.__pg_conn.table_exists(self.__schema, "lrs_check_class")

    @property
    def err_count(self):
        where = "category = 'ERROR'"
        result = self.__pg_conn.table_select_group(self.__schema, "lrs_check_class", "COUNT(id)", "category", where)
        if len(result) > 0:
            return result[0][0]
        else:
            return 0

    @property
    def warn_count(self):
        where = "category = 'WARNING'"
        result = self.__pg_conn.table_select_group(self.__schema, "lrs_check_class", "COUNT(id)", "category", where)
        if len(result) > 0:
            return result[0][0]
        else:
            return 0

    @property
    def info_count(self):
        where = "category = 'INFO'"
        result = self.__pg_conn.table_select_group(self.__schema, "lrs_check_class", "COUNT(id)", "category", where)
        if len(result) > 0:
            return result[0][0]
        else:
            return 0
