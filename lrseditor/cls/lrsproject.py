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

from ..utils import misc_utils
from ..cls.lrseventclasses import LRSEventClasses
from ..cls.lrsrouteclass import LRSRouteClass


class LRSProject:
    def __init__(self, pg_conn, schema):
        self.__pg_conn = pg_conn
        self.__schema = schema
        self.__id = None
        self.__name = None
        self.__route_class = None
        self.__route_class_name = None
        self.__tolerance = None
        self.__logfile_path = None
        self.__routeupdatetstz = None
        self.__lrs_event_classes = None
        self.__srid = None

        if not self.__pg_conn.table_exists(self.__schema, "lrs_project"):
            self.__pg_conn.table_proj_create(self.__schema)

        self.__data_get()

    def __data_get(self):
        fields = "id, name, routeclass, tolerance, logfile, routeupdatetstz, srid"
        projlist = self.__pg_conn.table_select(self.__schema, "lrs_project", fields)
        if projlist:
            self.__values_set(projlist[0])

    def create(self, valuelist, srid):
        fields = "name, routeclass, tolerance, logfile, srid"
        values = "'{}', '{}', {}, '{}', {}".format(valuelist[0], valuelist[1], valuelist[2], valuelist[3], srid)
        # return new id
        project_id = self.__pg_conn.table_insert(self.__schema, "lrs_project", fields, values, "id")
        valuelist.insert(0, project_id)
        # insert missing values: routeupdatetstz, srid
        valuelist.insert(5, None)
        valuelist.insert(6, srid)

        self.__values_set(valuelist)
        # create route class table
        if not self.__pg_conn.table_exists(self.__schema, self.__route_class_name.lower()):
            self.__pg_conn.table_route_class_create(self.__schema, self.__route_class_name, srid)

    def update(self, valuelist):
        expression = "name = '" + valuelist[0] + "', routeclass = '" + valuelist[1] + \
                     "', tolerance = " + str(valuelist[2]) + ", logfile = '" + valuelist[3] + "'"
        where = "id = " + str(self.__id)
        self.__pg_conn.table_update1(self.__schema, "lrs_project", expression, where)

        # rename of route class should be prevented
        if valuelist[1] != self.__route_class_name:
            if self.__pg_conn.table_exists(self.__schema, self.__route_class_name):
                self.__pg_conn.table_rename(self.__schema, self.__route_class_name, valuelist[1])

        valuelist.insert(0, self.__id)

        # insert missing values: routeupdatetstz, srid
        valuelist.insert(5, None)
        valuelist.insert(6, self.__srid)

        self.__values_set(valuelist)

    def routes_synchronize(self, basesystem_id, logfile):
        logfile.write("UPDATE ROUTE CLASS", "INFORM")
        self.__route_class = LRSRouteClass(self.__pg_conn, self.__schema, self.__route_class_name)

        # get existing routes from route class and valid routes from lrs_route_class
        routelist_valid = self.__pg_conn.table_select_group(self.__schema, "lrs_route_class", "name", "name",
                                                            "valid = 1", "name")
        routelist_exist = self.__pg_conn.table_select_group(self.__schema, self.__route_class_name, "name", "name",
                                                            None, "name")
        # convert into set
        routeset_valid = set(route[0] for route in routelist_valid)
        routeset_exist = set(route[0] for route in routelist_exist)
        # compare, get differences -> new routes
        routeset_new = routeset_valid.difference(routeset_exist)
        # insert new routes
        for route_new in routeset_new:
            self.__route_class.route_insert(route_new, basesystem_id)
            logfile.write("Route " + route_new + ": new route inserted", "INFORM")

        # get ALL routes from lrs_route_class
        routelist_all = self.__pg_conn.table_select_group(self.__schema, "lrs_route_class", "name", "name",
                                                          None, "name")
        # convert into set
        routeset_all = set(route[0] for route in routelist_all)
        # compare, get differences -> routes to delete
        routeset_del = routeset_exist.difference(routeset_all)
        # get name and route_id of routes to delete
        route_del_list = []
        for route_name_del in routeset_del:
            where = "name = '" + route_name_del + "'"
            route_id_del_list = self.__pg_conn.table_select(self.__schema, self.__route_class_name, "route_id", where)
            for route_id_del in route_id_del_list:
                route_del_list.append([route_id_del[0], route_name_del])

        # get all event classes
        self.__lrs_event_classes = LRSEventClasses(self.__pg_conn, self.__schema, self.__id)
        # check if events reference the routes to delete
        # create a list with unique route_id to delete
        # create a list with route_id with existing events
        route_del_list_def = []
        route_del_list_tmp = []
        for route_del in route_del_list:
            event_class_name_list = []
            route_id = str(route_del[0])
            route_name = route_del[1]
            for clid in self.__lrs_event_classes.event_class_idlist:
                event_class_name = self.__lrs_event_classes.event_class_names[clid]
                event_class_type = self.__lrs_event_classes.event_class_types[clid]
                where = "route_id = '" + route_id + "'"
                classname = ""
                if event_class_type == "p":
                    classname = event_class_name + "_bp"
                elif event_class_type == "c":
                    classname = event_class_name
                elif event_class_type == "t":
                    classname = event_class_name + "_mt"
                if len(self.__pg_conn.table_select(self.__schema, classname, "id", where)) > 0:
                    event_class_name_list.append(event_class_name)
            if len(event_class_name_list) > 0:
                for val in event_class_name_list:
                    logfile.write("Route " + route_name + ": Basesystem does not exist anymore, but still has events "
                                                          "of class " + val, "ERROR")
                    route_del_list_tmp.append([route_name, route_id, val])
            else:
                route_del_list_def.append(route_name)
        # delete routes
        for route_name_del in route_del_list_def:
            self.__route_class.route_delete(route_name_del)
            logfile.write("Route " + route_name_del + ": deleted", "INFORM")

        # return changed routes, compares only VALID routes
        routelist = self.__pg_conn.linestring_compare(self.__schema, self.__route_class_name, "geom")

        routelist_upd = []
        for route in routelist:
            if not route[1] is None:
                route_name = route[0]
                if not route[1]:
                    # st_equals = false -> not considering order of coord
                    where = "name = '" + route_name + "'"
                    route_id = self.__pg_conn.table_select(self.__schema, self.__route_class_name,
                                                           "route_id", where)[0][0]
                    self.__route_class.route_update(route_name, route_id, basesystem_id)
                    routelist_upd.append(route_id)
                    logfile.write("Route " + route_name + ": updated", "INFORM")
                elif route[1] and not route[2]:
                    # st_equals = true, st_orderingequals = false -> no route update
                    logfile.write("Route " + route_name + ": coordinates are not in the same order. Route not updated.",
                                  "ERROR")

        # update length of all routes
        self.__route_class.routes_length_update()

        return routelist_upd, route_del_list_tmp

    def __values_set(self, valuelist):
        self.__id = valuelist[0]
        self.__name = valuelist[1]
        self.__route_class_name = valuelist[2]
        self.__tolerance = valuelist[3]
        self.__logfile_path = valuelist[4]
        self.__routeupdatetstz = valuelist[5]
        self.__srid = valuelist[6]

    # get properties
    @property
    def id(self):
        return self.__id

    @property
    def name(self):
        return self.__name

    @property
    def route_class_name(self):
        return self.__route_class_name

    @property
    def tolerance(self):
        return self.__tolerance

    @property
    def logfile_path(self):
        return self.__logfile_path

    @property
    def srid(self):
        return self.__srid

    @property
    def routeupdatetstz(self):
        if self.__routeupdatetstz is not None:
            tstz = self.__routeupdatetstz.replace(microsecond=0)
            ts = tstz.replace(tzinfo=None)
            # time as string
            stime = ts.strftime("%Y-%m-%d %H:%M:%S")
            return stime
        else:
            return None

    # set property without a value -> regular function
    def routeupdatetstz_set(self):
        now_utc = misc_utils.datetime_utc_get()
        expression = "routeupdatetstz = '" + now_utc + "'"
        where = "id = " + str(self.__id)
        self.__pg_conn.table_update1(self.__schema, "lrs_project", expression, where)

    def __bool__(self):
        if self.__id is None:
            return False
        else:
            return True
