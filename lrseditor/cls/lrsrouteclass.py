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
from qgis.core import QgsPoint

from ..cls.lrslayerclass import LRSLayerClass
from ..utils import qgis_utils
from ..utils import misc_utils


class LRSRouteClass(LRSLayerClass):

    def __init__(self, pg_conn, schema, route_class_name):
        self.__schema = schema
        self.__pg_conn = pg_conn
        self.__name = route_class_name
        self.__layer = qgis_utils.layer_by_tablename_get(self.__schema, self.__name)
        LRSLayerClass.__init__(self, self.__layer)

    def route_name_get(self, route_id, sortnr=None):
        if not sortnr:
            where = "route_id = '" + route_id + "'"
        else:
            where = "route_id = '" + route_id + "' and sortnr = " + str(sortnr)

        result = self.__pg_conn.table_select(self.__schema, self.__name, "name", where)
        if len(result) > 0:
            return result[0][0]
        else:
            return None

    def route_id_get(self, route_name, sortnr=None):
        if not sortnr:
            where = "name = '" + route_name + "'"
        else:
            where = "name = '" + route_name + "' and sortnr = " + str(sortnr)

        result = self.__pg_conn.table_select(self.__schema, self.__name, "route_id", where)
        if len(result) > 0:
            return result[0][0]
        else:
            return None

    def route_update(self, route_name, route_id, basesystem_id):
        # get all routes from lrs_route_class
        where = "name = '" + str(route_name) + "'"
        fields = "name, pathnr"
        order = "name ASC, pathnr ASC"
        routelist_lrs = self.__pg_conn.table_select(self.__schema, "lrs_route_class", fields, where, order)
        routeset_lrs = set(str(route[0]) + "&&" + str(route[1]) for route in routelist_lrs)
        # get all routes from route class
        fields = "name, sortnr"
        order = "name ASC, sortnr ASC"
        routelist = self.__pg_conn.table_select(self.__schema, self.__name, fields, where, order)
        routeset = set(str(route[0]) + "&&" + str(route[1]) for route in routelist)

        # get route parts to delete
        route_parts_del = routeset.difference(routeset_lrs)
        # delete route parts
        for route_part in route_parts_del:
            route_name, sortnr = route_part.split("&&")[0], route_part.split("&&")[1]
            where = "name = '" + str(route_name) + "' AND sortnr = " + str(sortnr)
            self.__pg_conn.table_delete_row(self.__schema, self.__name, where)

        # update route part or insert new one
        now_utc = misc_utils.datetime_utc_get()
        for route_part in sorted(routeset_lrs):
            route_name, sortnr = route_part.split("&&")[0], route_part.split("&&")[1]
            where = "name = '" + str(route_name) + "' AND sortnr = " + str(sortnr)
            if self.__pg_conn.row_exists(self.__schema, self.__name, where):
                updatetablename = self.__name + " a"
                fromtablename = "lrs_route_class b"
                expression = "geom = b.geom"
                where_upd = "a.name = b.name AND a.sortnr = b.pathnr AND a.name = '" + route_name + "' AND " \
                            "a.sortnr = " + str(sortnr)
                # update geom
                self.__pg_conn.table_update_fromtable(self.__schema, updatetablename, expression,
                                                      fromtablename, where_upd)
                where_upd = "name = '" + route_name + "' AND sortnr = " + str(sortnr)
                expression = "geomtstz = '" + now_utc + "', changetstz = '" + now_utc + "'"
                # update tstz
                self.__pg_conn.table_update1(self.__schema, self.__name, expression, where_upd)
            else:
                fields = "geom, sortnr, name, route_id, basesystem_id, createtstz, changetstz, geomtstz"
                fromfields = "geom, pathnr, name, '" + route_id + "', '" + str(basesystem_id) + "', '" + now_utc + \
                             "', '" + now_utc + "', '" + now_utc + "'"
                where_ins = "name = '" + str(route_name) + "' AND pathnr = " + str(sortnr)
                # insert new part
                self.__pg_conn.table_insert_fromtable(self.__schema, self.__name, fields, fromfields,
                                                      "lrs_route_class", where_ins)

    def route_insert(self, route_name, basesystem_id):
        # insert route from lrs_route_class
        fields = "geom, sortnr, name, route_id, basesystem_id, createtstz, changetstz, geomtstz"
        now_utc = misc_utils.datetime_utc_get()
        where = "name = '" + route_name + "'"
        uuid = self.uuid
        fromfields = "geom, pathnr, name, '" + str(uuid) + "', '" + str(basesystem_id) + "', '" + now_utc + \
                     "', '" + now_utc + "', '" + now_utc + "'"
        self.__pg_conn.table_insert_fromtable(self.__schema, self.__name, fields, fromfields,
                                              "lrs_route_class", where)

    def route_delete(self, route_name):
        where = "name = '" + route_name + "'"
        self.__pg_conn.table_delete_row(self.__schema, self.__name, where)

    def route_reselect(self):
        selected = False
        values = self.selection_values_get(["id", "name", "sortnr"])
        names_multiple = []
        id_list = []
        for value in values:
            names_multiple.append(value[1] + " - SortNr " + str(value[2]))
            id_list.append(value[0])
        feat_id = self.selection_reselect(id_list, names_multiple, "Reselect", "Select Route:")
        if feat_id is not None:
            self.__layer.selectByIds([feat_id])
            selected = True
        return selected

    def point_meas_get(self, route_id, qgis_point, srid, sortnr=None):
        # get closest LineString from a point, respectively the sortnr
        if not sortnr:
            sortnr = self.__pg_conn.linestring_sortnr_get(self.__schema, self.__name, route_id,
                                                          qgis_point.x(), qgis_point.y(), "geom", srid)

        # return fraction at the position of qgis_point
        fract = self.__pg_conn.linestring_dist_get(self.__schema, self.__name, route_id, sortnr,
                                                   qgis_point.x(), qgis_point.y(), "geom", srid)
        meas, length = self.__meas_get(route_id, sortnr, fract)
        azi = self.__azi_get(route_id, sortnr, fract, length)
        qgis_point_along = QgsPoint()
        pg_point = self.__pg_conn.linestring_point_get(self.__schema, self.__name, route_id, sortnr, fract, "geom")
        qgis_point_along.fromWkt(pg_point)

        return [qgis_point_along, meas, azi]

    def point_routeend_get(self, route_id):
        # return point at route end
        where = "route_id = '" + route_id + "'"
        maxsortnr = self.__pg_conn.max_number_get(self.__schema, self.__name, "sortnr", where)
        meas, length = self.__meas_get(route_id, maxsortnr, 1)
        azi = self.__azi_get(route_id, maxsortnr, 1, length)
        qgis_point_end = QgsPoint()
        pg_point = self.__pg_conn.linestring_point_get(self.__schema, self.__name, route_id, maxsortnr, 1, "geom")
        qgis_point_end.fromWkt(pg_point)

        return [qgis_point_end, meas, azi]

    def routes_length_update(self):
        self.__pg_conn.linestring_length_update(self.__schema, self.__name, "geom", "length")

    def route_length_get(self, route_id):
        fields = """{route_id}, {length}""".format(route_id="route_id", length="length")
        where = "route_id = '" + route_id + "'"
        length_list = self.__pg_conn.table_select(self.__schema, self.__name, fields, where)
        # sum for routes with multipart
        total_length = 0
        for length in length_list:
            total_length = total_length + length[1]
        return total_length

    def __azi_get(self, route_id, sortnr, fract, length):
        # get azimuth, calc points 0.1 m above and underneath
        # needs length to convert from percent to meters
        fract1 = fract - (0.1 / length)
        if fract1 < 0:
            fract1 = 0
        fract2 = fract + (0.1 / length)
        if fract2 > 1:
            fract2 = 1

        pg_point1 = self.__pg_conn.linestring_point_get(self.__schema, self.__name, route_id, sortnr, fract1, "geom")
        pg_point2 = self.__pg_conn.linestring_point_get(self.__schema, self.__name, route_id, sortnr, fract2, "geom")
        return self.__pg_conn.linestring_azi_get(pg_point1, pg_point2)

    def __meas_get(self, route_id, sortnr, fract):
        # meas respects multipart linestring
        meas = 0
        length_sel = 0
        for i in range(1, sortnr + 1):
            length = self.__pg_conn.linestring_length_get(self.__schema, self.__name, route_id, i, "geom")
            if i != sortnr:
                meas = meas + length
            else:
                meas = meas + length * fract
                length_sel = length
                break
        # meas = total distance till position (fract), length = length of linestring with sortnr i
        return meas, length_sel

    # get properties
    @property
    def name(self):
        return self.__name
