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


class LRSBasesystem:
    def __init__(self, pg_conn, schema, project_id, pg_conn_bs, schema_bs):
        # project connection
        self.__pg_conn = pg_conn
        self.__schema = schema
        # basesystem connection
        self.__pg_conn_bs = pg_conn_bs
        self.__schema_bs = schema_bs

        self.__project_id = project_id
        self.__id = None
        self.__name = None
        self.__tolerance = None
        self.__base_class = None
        self.__base_geom_field = None
        self.__base_route_id_field = None
        self.__point_class = None
        self.__point_geom_field = None
        self.__point_route_id_field = None
        self.__point_sortnr_field = None
        self.__point_type_field = None

        if not self.__pg_conn.table_exists(self.__schema, "lrs_basesystem"):
            self.__pg_conn.table_basesystem_create(self.__schema)

        self.__data_get()

    def __data_get(self):
        fields = "project_id, id, name, tolerance, baseclass, basegeom, baserouteid, pointclass, " \
                 "pointgeom, pointrouteid, pointsortnr, pointtype"
        where = "project_id = " + str(self.__project_id)
        basesystem = self.__pg_conn.table_select(self.__schema, "lrs_basesystem", fields, where)
        if basesystem:
            # remove project_id from list
            del basesystem[0][0]
            self.__values_set(basesystem[0])

    def create(self, valuelist):
        fields = "project_id, name, tolerance, baseclass, basegeom, baserouteid, pointclass, " \
                 "pointgeom, pointrouteid, pointsortnr, pointtype"
        values = "{}, '{}', {}, '{}', '{}', '{}', '{}', '{}', '{}', '{}', '{}'".format(self.__project_id,
                                                                                       valuelist[0], valuelist[1],
                                                                                       valuelist[2], valuelist[3],
                                                                                       valuelist[4], valuelist[5],
                                                                                       valuelist[6], valuelist[7],
                                                                                       valuelist[8], valuelist[9])
        # return new id
        baseid = self.__pg_conn.table_insert(self.__schema, "lrs_basesystem", fields, values, "id")
        # insert missing values: id
        valuelist.insert(0, baseid)
        self.__values_set(valuelist)

    def update(self, valuelist):
        updatefields = ["name", "tolerance", "baseclass", "basegeom", "baserouteid", "pointclass", "pointrouteid",
                        "pointgeom", "pointsortnr", "pointtype"]
        valuefields = "id, name, tolerance, baseclass, basegeom, baserouteid, pointclass, pointgeom, pointrouteid, \
                       pointsortnr, pointtype"

        # insert missing values: id
        valuelist.insert(0, self.__id)
        # update2 can receive multiple values in lists
        newlist = []
        newlist.insert(0, valuelist)
        self.__pg_conn.table_update2(self.__schema, "lrs_basesystem", updatefields, "id", valuefields, newlist)

        self.__values_set(valuelist)

    def __topology_loops_check(self, srid):
        # check if column 'id' in baseclass and pointclass exists
        if not self.__pg_conn_bs.field_exists(self.__schema_bs, self.__base_class, "id"):
            return
        if not self.__pg_conn_bs.field_exists(self.__schema_bs, self.__point_class, "id"):
            return

        # get overlapping points
        routelist_equal_points = self.__pg_conn_bs.point_equals(self.__schema_bs, self.__point_class,
                                                                self.__point_geom_field, self.__point_route_id_field,
                                                                self.__point_sortnr_field)
        # create lrs_tmp1 table
        self.__pg_conn.linestring_loop_rep1(self.__schema, srid)

        fields1 = self.__base_geom_field + ", " + self.__base_route_id_field + ", id"
        fields2 = "geom, name, baseclass_id"
        for route in routelist_equal_points:
            # looping routes have just one path, no more route parts are allowed -> sortnr/pathnr should be 1
            route_closed = self.__pg_conn.linestring_closed(self.__schema, "geom", route[0], 1)[0]
            if route_closed[1]:
                # insert linestrings from baseclass into lrs_tmp1
                where = self.__base_route_id_field + " = '" + str(route_closed[0]) + "'"
                base_class_list = self.__pg_conn_bs.table_select(self.__schema_bs, self.__base_class, fields1, where)
                # truncate lrs_tmp1 before insert
                self.__pg_conn.table_truncate(self.__schema, "lrs_tmp1")
                for base_class_line in base_class_list:
                    values = "'{}', '{}', {}".format(base_class_line[0], base_class_line[1], base_class_line[2])
                    self.__pg_conn.table_insert(self.__schema, "lrs_tmp1", fields2, values)
                self.__pg_conn.linestring_loop_rep2(self.__schema, route_closed[0], route_closed[2], srid)
        # drop lrs_tmp1 table
        self.__pg_conn.linestring_loop_rep3(self.__schema)

    def data_check(self, logfile):
        logfile.write("CHECK DATA OF BASE SYSTEM", "INFORM")
        result = 0
        count = self.__pg_conn_bs.field_null_value_check(self.__schema_bs, self.__base_class,
                                                         self.__base_route_id_field, False)
        if count > 0:
            logfile.write("Base Class: Field " + self.__base_route_id_field + " has "
                          + str(count) + " NULL values", "ERROR")
        result += count

        count = self.__pg_conn_bs.field_null_value_check(self.__schema_bs, self.__point_class,
                                                         self.__point_route_id_field, False)
        if count > 0:
            logfile.write("Point Class: Field " + self.__point_route_id_field + " has "
                          + str(count) + " NULL values", "ERROR")
        result += count

        count = self.__pg_conn_bs.field_null_value_check(self.__schema_bs, self.__point_class,
                                                         self.__point_sortnr_field, True)
        if count > 0:
            logfile.write("Point Class: Field " + self.__point_sortnr_field + " has "
                          + str(count) + " NULL values", "ERROR")
        result += count

        count = self.__pg_conn_bs.field_null_value_check(self.__schema_bs, self.__point_class,
                                                         self.__point_type_field, True)
        if count > 0:
            logfile.write("Point Class: Field " + self.__point_type_field + " has "
                          + str(count) + " NULL values", "ERROR")
        result += count

        if result > 0:
            logfile.write("Route Update aborted", "INFORM")
            return False
        else:
            logfile.write("Data Check successfully finished", "INFORM")
            return True

    def topology_check(self, logfile):
        logfile.write("CHECK TOPOLOGY OF BASE SYSTEM", "INFORM")

        # naming: node = points from point class, point = start- or endpoint from linestring

        # get srid
        field = "srid"
        where = "id = " + str(self.__project_id)
        srid = self.__pg_conn.table_select(self.__schema, "lrs_project", field, where)[0][0]

        # get dsn to compare both conn
        dsn_dict1 = self.__pg_conn_bs.conn_dsn_get()
        dsn_dict2 = self.__pg_conn.conn_dsn_get()

        # create internal lrs_route_class, create and insert routes from baseclass
        self.__pg_conn.table_lrs_route_class_create(self.__schema, srid)
        if dsn_dict1 == dsn_dict2:
            # baseclass is in same db like lrs_route_class (faster)
            self.__pg_conn.lrs_route_class_insert(self.__schema, self.__base_class, self.__base_route_id_field,
                                                  self.__base_geom_field)
        else:
            # baseclass is in different db
            base_class_list = self.__pg_conn_bs.base_class_geom_select(self.__schema_bs, self.__base_class,
                                                                       self.__base_route_id_field,
                                                                       self.__base_geom_field)
            fields = "geom, name, pathnr"
            for base_class_line in base_class_list:
                pathnr = base_class_line[2]
                # set default value
                if pathnr is None:
                    pathnr = 1
                values = "'{}', '{}', {}".format(base_class_line[0], base_class_line[1], pathnr)
                self.__pg_conn.table_insert(self.__schema, "lrs_route_class", fields, values)

        # check loops, can only executed before route parts get sortnr, because looping routes have just one path
        self.__topology_loops_check(srid)

        # get all routes grouped from internal route class
        fields = "name, COUNT (pathnr)"
        routelist = self.__pg_conn.table_select_group(self.__schema, "lrs_route_class", fields, "name", None,
                                                      "name")

        # get all nodes for the routes from internal route class
        r_fields = "id, name, pathnr"
        routepointlist = self.__pg_conn.linestrings_nodes_get(self.__schema, "lrs_route_class",
                                                              "geom", fields=r_fields)

        # create dicts with points and id (-> no need to sort)
        # key = route_name+_+pathnr+_+S/E
        routedict = {}
        for routepoint in routepointlist:
            coords = [routepoint[4], routepoint[5]]
            key = routepoint[1] + "_" + str(routepoint[2]) + "_" + routepoint[3]
            routedict[key] = [coords, routepoint[0]]

        # prepare query for nodes
        n_fields = """{sortnr}, {type}, {x}, {y}""" \
            .format(sortnr=self.__point_sortnr_field, type=self.__point_type_field,
                    x="ST_X(" + self.__point_geom_field + ")", y="ST_Y(" + self.__point_geom_field + ")")
        n_order = """{sortnr} ASC, {type} ASC""" \
            .format(sortnr=self.__point_sortnr_field, type=self.__point_type_field)

        # loop routes
        routes_noupdate = []
        routeset = set()
        for route in routelist:
            route_name = route[0]
            routeset.add(route_name)
            path_count = route[1]

            # get nodes for route_name
            n_where = self.__point_route_id_field + " = '" + route_name + "'"
            nodelist = self.__pg_conn_bs.table_select(self.__schema_bs, self.__point_class,
                                                      n_fields, where=n_where, order=n_order)
            nodelist_count = len(nodelist)

            if 2 * path_count != nodelist_count:
                logfile.write("Route " + route_name + ": Number of paths does not match number of points, "
                                                      "route not valid", "ERROR")
                routes_noupdate.append(route_name)
            else:
                # loop paths, i.e. single LineString
                for i in range(1, path_count + 1):
                    # spoint = StartPoint of LineString, epoint = EndPoint of LineString
                    epoint = routedict[route_name + "_" + str(i) + "_E"][0]
                    spoint = routedict[route_name + "_" + str(i) + "_S"][0]
                    # loop nodes
                    point_type = -1
                    pos = 0
                    firstnode = None
                    for j in range(0, nodelist_count):
                        firstnode = [nodelist[j][2], nodelist[j][3]]
                        sdist = misc_utils.points_dist_get(firstnode, spoint)
                        edist = misc_utils.points_dist_get(firstnode, epoint)
                        # get first node
                        if sdist <= self.__tolerance:
                            # in direction of linestring
                            point_type = 1
                            pos = j
                            break
                        elif edist <= self.__tolerance:
                            # in opposite direction of linestring
                            point_type = 2
                            pos = j
                            break

                    if point_type == -1:
                        logfile.write("Route " + route_name + ", Path " + str(i) + ": No points found, "
                                                                                   "route not valid", "ERROR")
                        routes_noupdate.append(route_name)
                    else:
                        # first node attributes
                        firstsortnr = nodelist[pos][0]
                        firstnodetype = nodelist[pos][1]

                        if firstnodetype == 1:
                            k = pos + 1
                        else:
                            k = pos - 1

                        # get second node with attributes
                        secondnode = [nodelist[k][2], nodelist[k][3]]
                        secondsortnr = nodelist[k][0]
                        secondnodetype = nodelist[k][1]

                        # check sortnr
                        if firstsortnr != secondsortnr:
                            logfile.write("Route " + route_name + ": SortNr of points do not match, "
                                                                  "route not valid", "ERROR")
                            routes_noupdate.append(route_name)
                        else:
                            if firstsortnr != i:
                                logfile.write("Route " + route_name + ", Path " + str(i) +
                                              ": Path-Nr of route will be changed", "INFORM")

                                # change pathnr to the correct sortnr
                                route_class_id = routedict[route_name + "_" + str(i) + "_S"][1]
                                where = "id = " + str(route_class_id)
                                expression = "pathnr = " + str(firstsortnr)
                                self.__pg_conn.table_update1(self.__schema, "lrs_route_class", expression, where)

                        # check geom
                        if point_type == 1:
                            dist = misc_utils.points_dist_get(secondnode, epoint)
                        else:
                            dist = misc_utils.points_dist_get(secondnode, spoint)
                        if dist > self.__tolerance:
                            logfile.write("Route " + route_name + ", SortNr " + str(firstsortnr) +
                                          ": Start- or endpoint not in tolerated distance, route not valid", "ERROR")
                            routes_noupdate.append(route_name)

                        # check type
                        if firstnodetype == secondnodetype:
                            logfile.write("Route " + route_name + ", SortNr " + str(firstsortnr) +
                                          ": Start- and endpoint are of same type, route not valid", "ERROR")
                            routes_noupdate.append(route_name)
                        if firstnodetype != 1:
                            logfile.write("Route " + route_name + ", SortNr " + str(firstsortnr) +
                                          ": Startpoint is not of correct type, route not valid", "ERROR")
                            routes_noupdate.append(route_name)
                        if secondnodetype != 2:
                            logfile.write("Route " + route_name + ", SortNr " + str(firstsortnr) +
                                          ": Endpoint is not of correct type, route not valid", "ERROR")
                            routes_noupdate.append(route_name)

                        # detect loops
                        dist = misc_utils.points_dist_get(firstnode, secondnode)
                        if dist <= self.__tolerance:
                            lgtxt = "Route " + route_name + ", SortNr " + str(firstsortnr) + \
                                    ": Start- and endpoint have identical positions"
                            logfile.write(lgtxt, "INFORM")

                        # reversed direction
                        if point_type == 2:
                            logfile.write("Route " + route_name + ", Path " + str(i) +
                                          ": LineString in reversed direction", "INFORM")
                            # reverse line
                            route_class_id = routedict[route_name + "_" + str(i) + "_S"][1]
                            where = "id = " + str(route_class_id)
                            self.__pg_conn.linestring_reverse(self.__schema, "lrs_route_class", "geom", where)

        # remove duplicates and update status in lrs_route_class
        routes_noupdate = list(set(routes_noupdate))
        expression = "valid = 0"
        for val in routes_noupdate:
            where = "name = '" + val + "'"
            self.__pg_conn.table_update1(self.__schema, "lrs_route_class", expression, where)

        # check for unused nodes
        nodelist_all = self.__pg_conn_bs.table_select_group(self.__schema_bs, self.__point_class,
                                                            self.__point_route_id_field, self.__point_route_id_field)
        nodeset = set()
        for node in nodelist_all:
            nodeset.add(node[0].strip())
        nodeset_unused = nodeset.difference(routeset)
        for route_unused in nodeset_unused:
            logfile.write("Route " + route_unused + ": Points without LineString", "ERROR")

    def __values_set(self, valuelist):
        self.__id = valuelist[0]
        self.__name = valuelist[1]
        self.__tolerance = valuelist[2]
        self.__base_class = valuelist[3]
        self.__base_geom_field = valuelist[4]
        self.__base_route_id_field = valuelist[5]
        self.__point_class = valuelist[6]
        self.__point_geom_field = valuelist[7]
        self.__point_route_id_field = valuelist[8]
        self.__point_sortnr_field = valuelist[9]
        self.__point_type_field = valuelist[10]

    # get properties
    @property
    def id(self):
        return self.__id

    @property
    def name(self):
        return self.__name

    @property
    def tolerance(self):
        return self.__tolerance

    @property
    def base_class(self):
        return self.__base_class

    @property
    def base_route_id_field(self):
        return self.__base_route_id_field

    @property
    def base_geom_field(self):
        return self.__base_geom_field

    @property
    def point_class(self):
        return self.__point_class

    @property
    def point_geom_field(self):
        return self.__point_geom_field

    @property
    def point_route_id_field(self):
        return self.__point_route_id_field

    @property
    def point_sortnr_field(self):
        return self.__point_sortnr_field

    @property
    def point_type_field(self):
        return self.__point_type_field

    def __bool__(self):
        if self.__id is None:
            return False
        else:
            return True
