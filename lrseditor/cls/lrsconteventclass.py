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
import operator

from qgis.core import QgsFeature, QgsGeometry, QgsPointXY, QgsFeatureRequest

from ..cls.lrslayerclass import LRSLayerClass
from ..utils import qgis_utils
from ..utils import misc_utils


class LRSContEventClass(LRSLayerClass):

    def __init__(self, pg_conn, schema, layer):
        LRSLayerClass.__init__(self, layer)
        self.__schema = schema
        self.__layer = layer
        self.__pg_conn = pg_conn
        self.__event_class_name = qgis_utils.tablename_by_layername_get(self.__schema, self.__layer.name)

    def events_get(self, route_id, reverse_order=False):
        # no sql, get actual saved attribute values of the layer
        request = QgsFeatureRequest().setFlags(QgsFeatureRequest.NoGeometry)
        request.setSubsetOfAttributes(['event_id', 'frommeas', 'tomeas'], self.__layer.fields())
        if isinstance(route_id, str):
            expression = "route_id = \'" + route_id + "'"
        else:
            expression = 'route_id = ' + str(route_id)
        request.setFilterExpression(expression)
        # sort the list (QgsFeatureRequest.OrderBy could be used, but slower?)
        event_list = []
        for feature in self.__layer.getFeatures(request):
            event_list.append([feature.id(), feature['event_id'], feature['frommeas'], feature['tomeas']])
        event_list.sort(key=operator.itemgetter(2), reverse=reverse_order)
        return event_list

    def event_sql_insert(self, qgis_point, event_id, azi, route_id, frommeas, tomeas, srid, fields_list, fields_values):
        now_utc = misc_utils.datetime_utc_get()
        uuid = misc_utils.uuid_get()
        fields = "uuid, geom, event_id, azi, route_id, frommeas, tomeas, apprtstz, createtstz, changetstz, geomtstz"
        values = "'{uuid}', ST_SetSRID(ST_MakePoint({x}, {y}), {srid}), '{event_id}', {azi}, '{route_id}', " \
                 "{frommeas}, {tomeas}, '{now_utc}', '{now_utc}', '{now_utc}', '{now_utc}'"\
                 .format(uuid=uuid, x=qgis_point.x(), y=qgis_point.y(), srid=srid, event_id=event_id, azi=azi,
                         route_id=route_id, frommeas=frommeas, tomeas=tomeas, now_utc=now_utc)

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

        self.__pg_conn.table_insert(self.__schema, self.__event_class_name, fields, values)

    def event_insert(self, qgis_point, route_id, event_uuid, frommeas, tomeas, azi, feat_id_toupd=None):
        feature = QgsFeature(self.__layer.fields())
        now_utc = self.datetime
        feature['uuid'] = self.uuid
        feature['route_id'] = route_id
        feature['event_id'] = event_uuid
        feature['frommeas'] = frommeas
        feature['tomeas'] = tomeas
        feature['azi'] = azi
        feature['apprtstz'] = now_utc
        feature['createtstz'] = now_utc
        feature['changetstz'] = now_utc
        feature['geomtstz'] = now_utc
        self.__layer.beginEditCommand("Insert Continuous Event")
        feature.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(qgis_point.x(), qgis_point.y())))
        if feat_id_toupd is None:
            # first event along the route
            if self.__layer.addFeature(feature):
                self.__layer.endEditCommand()
                self.__layer.updateExtents()
            else:
                self.__layer.destroyEditCommand()
        else:
            sumbool = self.__layer.addFeature(feature)
            sumbool += self.attribute_value_change(feat_id_toupd, 'changetstz', now_utc)
            sumbool += self.attribute_value_change(feat_id_toupd, 'frommeas', tomeas)
            if sumbool != 3:
                self.__layer.destroyEditCommand()
            else:
                self.__layer.endEditCommand()
                self.__layer.updateExtents()

    def event_move(self, feat_id_tomove, qgis_point, frommeas, tomeas, azi, feat_id_toupd):
        now_utc = self.datetime
        values_dict = {
            'azi': azi,
            'frommeas': frommeas,
            'tomeas': tomeas,
            'changetstz': now_utc,
            'geomtstz': now_utc
        }
        self.__layer.beginEditCommand("Move Continuous Event")
        sumbool = self.attribute_values_change(feat_id_tomove, values_dict)
        sumbool += self.__layer.changeGeometry(feat_id_tomove,
                                               QgsGeometry.fromPointXY(QgsPointXY(qgis_point.x(), qgis_point.y())))
        sumbool += self.attribute_value_change(feat_id_toupd, 'changetstz', now_utc)
        sumbool += self.attribute_value_change(feat_id_toupd, 'frommeas', tomeas)
        if sumbool != 4:
            self.__layer.destroyEditCommand()
        else:
            self.__layer.endEditCommand()
            self.__layer.updateExtents()

    def event_delete(self, feat_id, feat_id_toupd=None, frommeas=None):
        now_utc = self.datetime
        self.__layer.beginEditCommand("Delete Continuous Event")
        if feat_id_toupd is None:
            # last event along the route
            if self.__layer.deleteFeature(feat_id):
                self.__layer.endEditCommand()
                self.__layer.updateExtents()
            else:
                self.__layer.destroyEditCommand()
        else:
            sumbool = self.__layer.deleteFeature(feat_id)
            sumbool += self.attribute_value_change(feat_id_toupd, 'changetstz', now_utc)
            sumbool += self.attribute_value_change(feat_id_toupd, 'frommeas', frommeas)
            if sumbool != 3:
                self.__layer.destroyEditCommand()
            else:
                self.__layer.endEditCommand()
                self.__layer.updateExtents()

    def events_sql_delete(self, route_id):
        where = "route_id = '" + route_id + "'"
        fields = "id"
        events = self.__pg_conn.table_select(self.__schema, self.__event_class_name, fields, where)
        for event in events:
            where = "id = " + str(event[0])
            self.__pg_conn.table_delete_row(self.__schema, self.__event_class_name, where)

    def event_attribute_update(self, feat_id, fieldname, value):
        now_utc = self.datetime
        self.__layer.beginEditCommand("Update Continuous Event")
        sumbool = self.attribute_value_change(feat_id, fieldname, value)
        sumbool += self.attribute_value_change(feat_id, 'changetstz', now_utc)
        if sumbool != 2:
            self.__layer.destroyEditCommand()
        else:
            self.__layer.endEditCommand()

    def events_update(self, routelist, route_class, srid, tol):
        now_utc = self.datetime
        for route_id in routelist:
            fields = """{id}, {x}, {y}, {frommeas}, {tomeas}""" \
                        .format(id="id", x="ST_X(geom)", y="ST_Y(geom)", frommeas="frommeas", tomeas="tomeas")
            where = "route_id = '" + route_id + "'"
            order = "frommeas ASC"
            events = self.__pg_conn.table_select(self.__schema, self.__event_class_name, fields, where, order)

            if len(events) != 0:
                # get end point
                result_end = route_class.point_routeend_get(route_id)
                meas_end = result_end[1]
                frommeas = 0
                # get all events without the last one, prevent it to be deleted
                for event in events[:-1]:
                    feat_id = event[0]
                    # get existing point
                    x, y = event[1], event[2]
                    qgis_point = QgsPointXY(x, y)
                    # get new event point
                    result_new = route_class.point_meas_get(route_id, qgis_point, srid)
                    x_new, y_new = result_new[0].x(), result_new[0].y()
                    meas_new = result_new[1]
                    # get diff to new event point
                    dist = misc_utils.points_dist_get([x, y], [x_new, y_new])
                    meas_diff = abs(meas_new - event[4])
                    if (meas_new <= tol) or (meas_new > (meas_end - tol)):
                        # new event point is not along the route and will be deleted
                        # must be done first
                        self.__pg_conn.table_delete_row(self.__schema, self.__event_class_name, "id = " + str(feat_id))
                        expression = ""
                    elif dist > tol:
                        # new geom, route changes along event point
                        expression = """geom = ST_SetSRID(ST_MakePoint({x}, {y}), {srid}), frommeas = {frommeas}, 
                                     tomeas = {meas_new}, azi = {azi}, changetstz = '{utc}', 
                                     apprtstz = '1000-01-01 01:01:01', geomtstz = '{utc}'""" \
                                     .format(x=x_new, y=y_new, srid=srid,
                                             frommeas=frommeas, meas_new=meas_new, azi=result_new[2], utc=now_utc)
                        # set new frommeas
                        frommeas = meas_new
                    elif dist <= tol < meas_diff:
                        # only meas changes, route changes underneath event point
                        expression = """frommeas = {frommeas}, tomeas = {meas_new}, azi = {azi}, changetstz = '{utc}'""" \
                                     .format(frommeas=frommeas, meas_new=meas_new, azi=result_new[2], utc=now_utc)
                        # set new frommeas
                        frommeas = meas_new
                    else:
                        # no changes, route changes above event point
                        # set new frommeas
                        frommeas = meas_new
                        expression = ""
                    if len(expression) > 0:
                        self.__pg_conn.table_update1(self.__schema, self.__event_class_name, expression, "id = "
                                                     + str(feat_id))

                # get last point of route
                event_end = events[-1]
                x_new, y_new = result_end[0].x(), result_end[0].y()
                dist_end = misc_utils.points_dist_get([event_end[1], event_end[2]], [x_new, y_new])
                if dist_end > tol:
                    # new geom, route changes at the end
                    expression = """geom = ST_SetSRID(ST_MakePoint({x}, {y}), {srid}), frommeas = {frommeas}, 
                                 tomeas = {meas_end}, azi = {azi}, changetstz = '{utc}', 
                                 apprtstz = '1000-01-01 01:01:01', geomtstz = '{utc}'""" \
                                 .format(x=x_new, y=y_new, srid=srid,
                                         frommeas=frommeas, meas_end=meas_end, azi=result_end[2], utc=now_utc)
                else:
                    expression = """frommeas = {frommeas}, tomeas = {meas_end}, azi = {azi}, changetstz = '{utc}'""" \
                                 .format(frommeas=frommeas, meas_end=meas_end, azi=result_end[2], utc=now_utc)
                # update last point of route
                where = "id = " + str(event_end[0])
                self.__pg_conn.table_update1(self.__schema, self.__event_class_name, expression, where)

        self.__layer.updateExtents()

    def events_approvable_get(self, route_class_name, tolerance, checkonly=False):
        fields = """val.{id}, val.{tomeas}, val.{event_id}, val.{route_id}, et.{name}""" \
                 .format(id="id", tomeas="tomeas", event_id="event_id", route_id="route_id", name="name")

        where = "val.apprtstz = '1000-01-01 01:01:01'"
        tablename_a = self.__event_class_name + " val"
        tablename_b = self.__event_class_name + "_et et"
        a_id_field = "val.event_id"
        b_id_field = "et.uuid"
        countfield = "val.id"
        group = "val.id, et.name"
        order = "val.route_id ASC, val.tomeas ASC"
        events = self.__pg_conn.table_select_count_leftjoin(self.__schema, tablename_a, tablename_b, fields,
                                                            countfield, a_id_field, b_id_field, group, where, order)

        if checkonly:
            if len(events) > 0:
                return True
            else:
                return False

        route_name_old = ""
        routedict = {}
        tmplist = []
        # unique route_id in a set to check meas afterwards
        route_id_set = set()
        # get all events in a dict to display in the eventapprovaldockwidget
        for count, event in enumerate(events):
            route_id = str(event[3])
            where = "route_id = '" + route_id + "'"
            route_name = self.__pg_conn.table_select(self.__schema, route_class_name, "name", where)[0][0]
            route_id_set.add(route_name + "%%" + route_id)
            if route_name != route_name_old and count > 0:
                routedict[route_name_old] = tmplist
                tmplist = []
            val = str(event[0]) + ": " + (event[4]) + " / " + str(event[1])
            tmplist.append(val)
            route_name_old = route_name
        # get last one
        if len(events) > 0:
            routedict[route_name_old] = tmplist

        # check meas of changed routes
        routeerrdict = {}
        if len(route_id_set) > 0:
            for route_id in route_id_set:
                result = self.events_meas_check(route_id.split("%%")[1], tolerance, route_class_name)
                if result is not None:
                    tmplist = []
                    for errlist in result[0]:
                        val = str(errlist[0]) + ": " + str(errlist[3])
                        tmplist.append(val)
                    if len(tmplist) > 0:
                        routeerrdict[route_id.split("%%")[0]] = tmplist
        return routedict, routeerrdict

    def event_approve(self, feat_id):
        now_utc = self.datetime
        where = "id = " + str(feat_id)
        expression = """apprtstz = '{utc}'""".format(utc=now_utc)
        self.__pg_conn.table_update1(self.__schema, self.__event_class_name, expression, where)

    def events_meas_check(self, route_id, tolerance, route_class_name):
        fields = """{id}, {uuid}, {frommeas}, {tomeas}, {geom}""" \
                    .format(id="id", uuid="uuid", frommeas="frommeas", tomeas="tomeas",
                            geom="geom")
        where = "route_id = '" + route_id + "'"
        order = "frommeas ASC"
        event_list = self.__pg_conn.table_select(self.__schema, self.__event_class_name, fields, where, order)

        result = []
        # no events on route
        if len(event_list) == 0:
            return None

        # check if first meas is 0
        firstzero = True
        if event_list[0][2] > tolerance:
            firstzero = False

        # check following meas
        oldmeas = 0
        for event in event_list:
            frommeas = event[2]
            tomeas = event[3]
            if abs(frommeas - oldmeas) > tolerance:
                result.append([event[0], event[1], frommeas, tomeas, event[4]])
            oldmeas = tomeas

        # check last meas with length of route
        fields = """{route_id}, {length}""".format(route_id="route_id", length="length")
        length_list = self.__pg_conn.table_select(self.__schema, route_class_name, fields, where)
        # sum for routes with many parts
        total_length = 0
        for length in length_list:
            total_length = total_length + length[1]
        lastmeas = True
        if abs(total_length - oldmeas) > tolerance:
            lastmeas = False

        return result, firstzero, lastmeas
