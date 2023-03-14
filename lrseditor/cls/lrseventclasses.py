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


class LRSEventClasses:

    def __init__(self, pg_conn, schema, project_id):
        self.__pg_conn = pg_conn
        self.__schema = schema
        self.__project_id = project_id
        self.__namedict = None
        self.__typedict = None
        self.__optiondict = None
        # list with id as key values for dictionaries
        self.__idlist = None

        if not self.__pg_conn.table_exists(self.__schema, "lrs_event_classes"):
            self.__pg_conn.table_event_classes_create(self.__schema)

        self.__data_get()

    def __data_get(self):
        self.__namedict = {}
        self.__typedict = {}
        self.__optiondict = {}
        self.__idlist = []

        fields = "id, name, type, options, project_id"
        where = "project_id = " + str(self.__project_id)
        order = "id ASC"
        events = self.__pg_conn.table_select(self.__schema, "lrs_event_classes", fields, where, order)

        for event in events:
            self.__idlist.append(event[0])
            self.__namedict[event[0]] = event[1]
            self.__typedict[event[0]] = event[2]
            self.__optiondict[event[0]] = event[3]
        sorted(self.__idlist)

    def event_class_create(self, event_class_name, event_class_type, event_class_option, route_class_name):
        # get srid
        field = "srid"
        where = "id = " + str(self.__project_id)
        srid = self.__pg_conn.table_select(self.__schema, "lrs_project", field, where)[0][0]

        fields = "name, project_id, type, options"
        values = "'{}', {}, '{}', {}".format(event_class_name, self.__project_id, event_class_type, event_class_option)
        # return new id
        event_class_id = self.__pg_conn.table_insert(self.__schema, "lrs_event_classes", fields, values, "id")
        # create new event class tables
        if event_class_type == "p":
            self.__pg_conn.point_event_class_create(self.__schema, event_class_name, srid)
        elif event_class_type == "c":
            self.__pg_conn.cont_event_class_create(self.__schema, event_class_name, srid)
            self.__pg_conn.cont_event_view_create(self.__schema, event_class_name, route_class_name, srid)
        elif event_class_type == "t":
            self.__pg_conn.tour_event_class_create(self.__schema, event_class_name, srid)
            self.__pg_conn.tour_event_view_create(self.__schema, event_class_name, route_class_name, srid)
        # add to list and dictionaries
        self.__idlist.append(event_class_id)
        self.__namedict[event_class_id] = event_class_name
        self.__typedict[event_class_id] = event_class_type
        self.__optiondict[event_class_id] = event_class_option
        # sort key list
        sorted(self.__idlist)

    def event_class_delete(self, event_class_id):
        where = "id = " + str(event_class_id)
        # delete value and drop tables
        self.__pg_conn.table_delete_row(self.__schema, "lrs_event_classes", where)
        event_class_name = self.__namedict[event_class_id]
        event_class_type = self.__typedict[event_class_id]
        if event_class_type == "p":
            self.__pg_conn.point_event_class_delete(self.__schema, event_class_name)
        elif event_class_type == "c":
            self.__pg_conn.cont_event_class_delete(self.__schema, event_class_name)
        elif event_class_type == "t":
            self.__pg_conn.tour_event_class_delete(self.__schema, event_class_name)

        # remove from list and dictionaries
        self.__idlist.remove(event_class_id)
        self.__namedict.pop(event_class_id, None)
        self.__typedict.pop(event_class_id, None)
        self.__optiondict.pop(event_class_id, None)
        # sort key list
        sorted(self.__idlist)

    def event_class_type_get(self, event_class_name):
        ret_val = None
        for key, val in self.__namedict.items():
            if val == event_class_name:
                ret_val = self.event_class_types[key]
        return ret_val

    def event_classes_stat(self):
        count_c = 0
        count_p = 0
        count_t = 0
        for key, val in self.__typedict.items():
            if val == "c":
                count_c = count_c + 1
            elif val == "p":
                count_p = count_p + 1
            elif val == "t":
                count_t = count_t + 1

        return [count_c, count_p, count_t]

    # get properties
    @property
    def event_class_names(self):
        return self.__namedict

    @property
    def event_class_types(self):
        return self.__typedict

    @property
    def event_class_options(self):
        return self.__optiondict

    @property
    def event_class_idlist(self):
        return self.__idlist
