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
from qgis.core import QgsFeature, QgsGeometry, QgsPointXY

from ..cls.lrslayerclass import LRSLayerClass
from ..utils import qgis_utils
from ..utils import misc_utils


class LRSBasePointEventClass(LRSLayerClass):

    def __init__(self, pg_conn, schema, layer):
        LRSLayerClass.__init__(self, layer)
        self.__schema = schema
        self.__layer = layer
        self.__pg_conn = pg_conn
        self.__event_class_name = qgis_utils.tablename_by_layername_get(self.__schema, self.__layer.name)

    def basepoint_delete(self, feat_id):
        self.editing_start()
        self.__layer.beginEditCommand("Delete Base Point")
        if self.__layer.deleteFeature(feat_id):
            self.__layer.endEditCommand()
            self.__layer.updateExtents()
        else:
            self.__layer.destroyEditCommand()

    def basepoints_delete(self, fieldname, value):
        self.editing_start()
        feat_id_list = self.feature_id_get(fieldname, value)
        self.__layer.beginEditCommand("Delete Base Points")
        if self.__layer.deleteFeatures(feat_id_list):
            self.__layer.endEditCommand()
            self.__layer.updateExtents()
        else:
            self.__layer.destroyEditCommand()

    def basepoints_sql_delete(self, route_id):
        where = "route_id = '" + route_id + "'"
        fields = "id, event_id"
        basepoints_route_id = self.__pg_conn.table_select(self.__schema, self.__event_class_name, fields, where)
        point_events_reset = []
        for basepoint_route_id in basepoints_route_id:
            event_id = basepoint_route_id[1]
            where = "event_id = '" + event_id + "'"
            basepoints_event_id = self.__pg_conn.table_select(self.__schema, self.__event_class_name, fields, where)
            # return point events with one basepoint, to reset geom
            if len(basepoints_event_id) == 1:
                point_events_reset.append(event_id)
            # delete basepoints
            where = "id = " + str(basepoint_route_id[0])
            self.__pg_conn.table_delete_row(self.__schema, self.__event_class_name, where)
        return point_events_reset

    def basepoints_insert(self, qgis_point, route_class, event_id, routelist, srid):
        self.editing_start()
        now_utc = self.datetime
        self.__layer.beginEditCommand("Insert Base Points")
        sumbool = 0
        for route_id in routelist:
            feature = QgsFeature(self.__layer.fields())
            result = route_class.point_meas_get(route_id, qgis_point, srid)
            qgis_point_along = result[0]
            feature['uuid'] = self.uuid
            feature['route_id'] = route_id
            feature['event_id'] = event_id
            feature['meas'] = result[1]
            feature['azi'] = result[2]
            feature['apprtstz'] = now_utc
            feature['createtstz'] = now_utc
            feature['changetstz'] = now_utc
            feature['geomtstz'] = now_utc
            feature.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(qgis_point_along.x(), qgis_point_along.y())))
            sumbool += self.__layer.addFeature(feature)

        if sumbool == len(routelist):
            self.__layer.endEditCommand()
            self.__layer.updateExtents()
        else:
            self.__layer.destroyEditCommand()

    def basepoint_sql_insert(self, qgis_point, route_id, event_id, meas, azi, srid):
        now_utc = misc_utils.datetime_utc_get()
        uuid = misc_utils.uuid_get()
        fields = "uuid, geom, event_id, azi, route_id, meas, apprtstz, createtstz, changetstz, geomtstz"
        values = "'{uuid}', ST_SetSRID(ST_MakePoint({x}, {y}), {srid}), '{event_id}', {azi}, '{route_id}', " \
                 "{meas}, '{now_utc}', '{now_utc}', '{now_utc}', '{now_utc}'" \
                 .format(uuid=uuid, x=qgis_point.x(), y=qgis_point.y(), srid=srid, event_id=event_id, azi=azi,
                         route_id=route_id, meas=meas, now_utc=now_utc)

        self.__pg_conn.table_insert(self.__schema, self.__event_class_name, fields, values)

    def basepoint_insert(self, qgis_point, route_id, event_id, meas, azi):
        self.editing_start()
        feature = QgsFeature(self.__layer.fields())
        now_utc = self.datetime
        feature['uuid'] = self.uuid
        feature['route_id'] = route_id
        feature['event_id'] = event_id
        feature['meas'] = meas
        feature['azi'] = azi
        feature['apprtstz'] = now_utc
        feature['createtstz'] = now_utc
        feature['changetstz'] = now_utc
        feature['geomtstz'] = now_utc
        self.__layer.beginEditCommand("Insert Base Point")
        feature.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(qgis_point.x(), qgis_point.y())))
        if self.__layer.addFeature(feature):
            self.__layer.endEditCommand()
            self.__layer.updateExtents()
        else:
            self.__layer.destroyEditCommand()

    def basepoints_move(self, qgis_point, route_class, valuelist, srid):
        self.editing_start()
        now_utc = self.datetime
        self.__layer.beginEditCommand("Move Base Points")
        sumbool = 0
        for value in valuelist:
            feat_id = value[0]
            route_id = value[1]
            result = route_class.point_meas_get(route_id, qgis_point, srid)
            qgis_point_along = result[0]
            sumbool += self.attribute_value_change(feat_id, 'meas', result[1])
            sumbool += self.attribute_value_change(feat_id, 'azi', result[2])
            sumbool += self.attribute_value_change(feat_id, 'changetstz', now_utc)
            sumbool += self.attribute_value_change(feat_id, 'geomtstz', now_utc)
            sumbool += self.__layer.changeGeometry(feat_id, QgsGeometry.fromPointXY(QgsPointXY(qgis_point_along.x(),
                                                                                    qgis_point_along.y())))
        if (sumbool/5) == len(valuelist):
            self.__layer.endEditCommand()
            self.__layer.updateExtents()
        else:
            self.__layer.destroyEditCommand()

    def basepoints_update(self, routelist, route_class, srid, tol):
        now_utc = self.datetime
        for route_id in routelist:
            fields = """bp.{id}, {bp_x}, {bp_y}, bp.{meas}, bp.{event_id}, {ev_x}, {ev_y}""" \
                     .format(id="id", bp_x="ST_X(bp.geom)", bp_y="ST_Y(bp.geom)", meas="meas",
                             event_id="event_id", ev_x="ST_X(ev.geom)", ev_y="ST_Y(ev.geom)")
            countfield = "bp.id"
            tablename_a = self.__event_class_name + " bp"
            tablename_b = self.__event_class_name[:-3] + " ev"
            a_id_field = "bp.event_id"
            b_id_field = "ev.uuid"
            group = "bp.id, ev.geom"
            where = "bp.route_id = '" + route_id + "'"
            basepoints = self.__pg_conn.table_select_count_leftjoin(self.__schema, tablename_a, tablename_b, fields,
                                                                    countfield, a_id_field, b_id_field, group, where)
            for basepoint in basepoints:
                qgis_point = QgsPointXY(basepoint[5], basepoint[6])
                # get new basepoint with point event
                result = route_class.point_meas_get(route_id, qgis_point, srid)
                qgis_point_new = result[0]
                meas_new = result[1]
                dist = misc_utils.points_dist_get([basepoint[1], basepoint[2]], [qgis_point_new.x(),
                                                                                 qgis_point_new.y()])
                meas_diff = abs(meas_new - basepoint[3])
                if dist <= tol < meas_diff:
                    # new meas, route changes underneath basepoint
                    expression = """meas = {meas}, azi = {azi}, changetstz = '{utc}'""" \
                                 .format(meas=meas_new, azi=result[2], utc=now_utc)
                elif dist > tol:
                    # new geom, route changes along basepoint
                    expression = """geom = ST_SetSRID(ST_MakePoint({x}, {y}), {srid}), meas = {meas},
                                 azi = {azi}, apprtstz = '1000-01-01 01:01:01', changetstz = '{utc}',
                                 geomtstz = '{utc}'""" \
                                 .format(x=qgis_point_new.x(), y=qgis_point_new.y(), srid=srid, meas=meas_new,
                                         azi=result[2], utc=now_utc)
                else:
                    # route changes above basepoint
                    expression = ""
                if len(expression) > 0:
                    where_upd = "id = " + str(basepoint[0])
                    self.__pg_conn.table_update1(self.__schema, self.__event_class_name, expression, where_upd)
            self.__layer.updateExtents()

    def events_approvable_get(self, route_class_name, tolerance, checkonly=False):
        # keep tolerance as a parameter in function
        fields = """bp.{id}, bp.{meas}, bp.{event_id}, bp.{route_id}, ev.{name}""" \
                 .format(id="id", meas="meas", event_id="event_id", route_id="route_id", name="name")
        where = "bp.apprtstz = '1000-01-01 01:01:01'"
        a_id_field = "bp.event_id"
        b_id_field = "ev.uuid"
        tablename_a = self.__event_class_name + " bp"
        tablename_b = self.__event_class_name[:-3] + " ev"
        countfield = "bp.id"
        group = "bp.id, ev.name"
        order = "bp.route_id ASC, bp.meas ASC"
        basepoints = self.__pg_conn.table_select_count_leftjoin(self.__schema, tablename_a, tablename_b, fields,
                                                                countfield, a_id_field, b_id_field, group, where, order)

        if checkonly:
            if len(basepoints) > 0:
                return True
            else:
                return False

        route_name_old = ""
        routedict = {}
        tmplist = []
        for count, basepoint in enumerate(basepoints):
            route_id = str(basepoint[3])
            where = "route_id = '" + route_id + "'"
            route_name = self.__pg_conn.table_select(self.__schema, route_class_name, "name", where)[0][0]
            if route_name != route_name_old and count > 0:
                routedict[route_name_old] = tmplist
                tmplist = []
            val = str(basepoint[0]) + ": " + (basepoint[4]) + " / " + str(basepoint[1])
            tmplist.append(val)
            route_name_old = route_name
        # get last one
        if len(basepoints) > 0:
            routedict[route_name_old] = tmplist

        # add an empyt errdict
        routeerrdict = {}
        return routedict, routeerrdict

    def event_approve(self, feat_id):
        now_utc = self.datetime
        where = "id = " + str(feat_id)
        expression = """apprtstz = '{utc}'""".format(utc=now_utc)
        self.__pg_conn.table_update1(self.__schema, self.__event_class_name, expression, where)

    # get properties
    @property
    def event_class_name(self):
        return self.__event_class_name
