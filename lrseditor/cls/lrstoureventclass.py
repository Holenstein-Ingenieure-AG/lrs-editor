# -*- coding: utf-8 -*-
"""
/***************************************************************************
    name             :  LRS-Editor
    description      :  QGIS plugin for editing linear reference systems
    begin            :  2021-06-15
    copyright        :  (C) 2021 by Reto Meier (Holenstein Ingenieure AG)
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
import locale

from qgis.core import QgsFeature, QgsGeometry, QgsPointXY, QgsFeatureRequest

from ..cls.lrslayerclass import LRSLayerClass
from ..cls.lrseventnamesclass import LRSEventNamesClass
from ..utils import qgis_utils
from ..utils import misc_utils


class LRSTourEventClass(LRSLayerClass):

    def __init__(self, pg_conn, schema, layer):
        LRSLayerClass.__init__(self, layer)
        self.__schema = schema
        self.__layer = layer
        self.__pg_conn = pg_conn
        self.__event_class_name = qgis_utils.tablename_by_layername_get(self.__schema, self.__layer.name)
        self.__layer_mt = qgis_utils.layer_by_tablename_get(self.__schema, self.__event_class_name + "_mt")
        self.__tablename_mt = self.__event_class_name + "_mt"
        self.__table_et_name = self.__event_class_name + "_et"
        self.__tour_event_names = LRSEventNamesClass(self.__pg_conn, self.__schema, self.__event_class_name, "t")

    def events_update(self, routelist, route_class, srid, tol):
        for route_id in routelist:
            fields = """{id}, {frommeas}, {tomeas}, {frompoint_id}, {topoint_id}""" \
                     .format(id="id", frommeas="frommeas", tomeas="tomeas", frompoint_id="frompoint_id",
                             topoint_id="topoint_id")
            where = "route_id = '" + route_id + "'"
            order = "event_id ASC, frommeas ASC"
            events_list = self.__pg_conn.table_select(self.__schema, self.__tablename_mt, fields, where, order)

            for events in events_list:
                frommeas_new = self.__event_point_update(events[3], events[1], route_class, route_id, srid, tol)
                tomeas_new = self.__event_point_update(events[4], events[2], route_class, route_id, srid, tol)
                where = "id = " + str(events[0])
                if frommeas_new > -1:
                    expression = """frommeas = {frommeas_new}""".format(frommeas_new=frommeas_new)
                    self.__pg_conn.table_update1(self.__schema, self.__tablename_mt, expression, where)
                if tomeas_new > -1:
                    expression = """tomeas = {tomeas_new}""".format(tomeas_new=tomeas_new)
                    self.__pg_conn.table_update1(self.__schema, self.__tablename_mt, expression, where)

        self.__layer.updateExtents()

    def __event_point_update(self, event_uuid, meas, route_class, route_id, srid, tol):
        fields = """{id}, {x}, {y}""".format(id="id", x="ST_X(geom)", y="ST_Y(geom)")
        where = "uuid = '" + event_uuid + "'"
        event = self.__pg_conn.table_select(self.__schema, self.__event_class_name, fields, where)[0]
        # get existing point
        x, y = event[1], event[2]
        qgis_point = QgsPointXY(x, y)
        # get new event point
        result_new = route_class.point_meas_get(route_id, qgis_point, srid)
        x_new, y_new = result_new[0].x(), result_new[0].y()
        meas_new = result_new[1]
        # get diff to new event point
        dist = misc_utils.points_dist_get([x, y], [x_new, y_new])
        meas_diff = abs(meas_new - meas)
        now_utc = self.datetime
        expression = ""
        if dist > tol:
            # new geom, route changes along event point
            expression = """geom = ST_SetSRID(ST_MakePoint({x}, {y}), {srid}), azi = {azi}, changetstz = '{utc}', 
                         apprtstz = '1000-01-01 01:01:01', geomtstz = '{utc}'""" \
                         .format(x=x_new, y=y_new, srid=srid, azi=result_new[2], utc=now_utc)
        elif dist <= tol < meas_diff:
            # only meas changes, route changes underneath event point
            expression = """azi = {azi}, changetstz = '{utc}'""".format(azi=result_new[2], utc=now_utc)

        if len(expression) > 0:
            self.__pg_conn.table_update1(self.__schema, self.__event_class_name, expression, where)
            return meas_new
        else:
            # no changes, route changes above event point
            return -1

    def event_meas_get(self, event_uuid, route_id):
        event_list = self.__events_part_get(event_uuid)
        # inconsistent data, more or less than one point found
        if len(event_list) != 1:
            return None
        # check for same route_id
        if route_id != event_list[0][2]:
            return []
        event_id = event_list[0][1]
        events_list = self.__events_tour_get(event_id, route_id)
        # order by frommeas
        events_list.sort(key=operator.itemgetter(4), reverse=False)
        # get position (indices) of event_uuid in events_list
        [listind, pointtype] = \
            [(i, sub.index(event_uuid)) for (i, sub) in enumerate(events_list) if event_uuid in sub][0]

        if pointtype == 5:
            # is frompoint
            if listind == 0:
                # route start
                minmeas = 0
            else:
                minmeas = events_list[listind - 1][6]
            maxmeas = events_list[listind][6]
            measfield = "frommeas"
            # add tomeas of same tour part to check
            samemeas = event_list[0][6]
        elif pointtype == 7:
            # is topoint
            if listind == len(events_list) - 1:
                # route end
                maxmeas = -99
            else:
                maxmeas = events_list[listind + 1][4]
            minmeas = events_list[listind][4]
            measfield = "tomeas"
            # add frommeas of same tour part to check
            samemeas = event_list[0][4]
        else:
            return None
        # return feature.id mt-table, minmeas, maxmeas, measfield to update, meas of same tour part
        return [event_list[0][0], minmeas, maxmeas, measfield, samemeas]

    def event_name_get(self, event_uuid):
        event_list = self.__events_part_get(event_uuid)
        # inconsistent data, more or less than one point found
        if len(event_list) != 1:
            return None
        event_uuid = event_list[0][1]
        event_id = self.__tour_event_names.event_id_get(None, event_uuid)
        event_name = self.__tour_event_names.event_name_get(event_id)
        toursortnr = event_list[0][3]
        return [event_name, toursortnr]

    def tour_delete(self, event_uuid):
        event_list = self.__events_part_get(event_uuid)
        # inconsistent data, more or less than one point found
        if len(event_list) != 1:
            return False
        event_id = event_list[0][1]
        # get all events for the tour
        events_list = self.__events_tour_get(event_id)
        for events in events_list:
            where = "uuid = '" + events[5] + "'"
            self.__pg_conn.table_delete_row(self.__schema, self.__event_class_name, where)
            where = "uuid = '" + events[7] + "'"
            self.__pg_conn.table_delete_row(self.__schema, self.__event_class_name, where)
            where = "uuid = '" + events[1] + "'"
            self.__pg_conn.table_delete_row(self.__schema, self.__tablename_mt, where)

        # delete event name
        where = "uuid = '" + event_id + "'"
        self.__pg_conn.table_delete_row(self.__schema, self.__table_et_name, where)
        return True

    def events_sql_delete(self, route_id):
        where = "route_id = '" + route_id + "'"
        fields = "id, event_id, sortnr, frompoint_id, topoint_id"
        order = "event_id ASC, sortnr ASC"
        event_list = self.__pg_conn.table_select(self.__schema, self.__tablename_mt, fields, where, order)
        for event in event_list:
            feat_id = event[0]
            where = "id = " + str(feat_id)
            # get current sortnr
            toursortnr_old = self.__pg_conn.table_select(self.__schema, self.__tablename_mt, "sortnr",
                                                         where)[0][0]
            event_id = event[1]
            fields = "id, sortnr"
            where = "event_id = '" + event_id + "'"
            order = "sortnr ASC"
            # create list with sortnr to update
            events_list = self.__pg_conn.table_select(self.__schema, self.__tablename_mt, fields,
                                                      where, order)
            tour_list = []
            for events in events_list:
                if events[1] > toursortnr_old:
                    tour_list.append([events[0], events[1]])
                    tour_list.sort(key=operator.itemgetter(1), reverse=False)
            # delete event points and record in measure table
            frompoint_id = event[3]
            topoint_id = event[4]
            where = "uuid = '" + frompoint_id + "'"
            self.__pg_conn.table_delete_row(self.__schema, self.__event_class_name, where)
            where = "uuid = '" + topoint_id + "'"
            self.__pg_conn.table_delete_row(self.__schema, self.__event_class_name, where)
            where = "id = " + str(event[0])
            self.__pg_conn.table_delete_row(self.__schema, self.__tablename_mt, where)
            # update sortnr of tour
            for tour_event in tour_list:
                toursortnr = tour_event[1]
                where = "id = " + str(tour_event[0])
                expression = "sortnr = " + str(toursortnr - 1)
                self.__pg_conn.table_update1(self.__schema, self.__tablename_mt, expression, where)

    def event_delete(self, event_uuid):
        result = False
        event_list = self.__events_part_get(event_uuid)
        # inconsistent data, more or less than one point found
        if len(event_list) != 1:
            return result

        toursortnr_old = event_list[0][3]
        events_list = self.__events_tour_get(event_list[0][1])
        tour_list = []
        # create list with sortnr to update
        for events in events_list:
            if events[3] > toursortnr_old:
                tour_list.append([events[0], events[3]])
        tour_list.sort(key=operator.itemgetter(1), reverse=False)

        frompoint_id = self.feature_id_get("uuid", event_list[0][5])
        topoint_id = self.feature_id_get("uuid", event_list[0][7])

        self.__layer.beginEditCommand("Delete Tour Event")
        if self.__layer.deleteFeatures([frompoint_id[0], topoint_id[0]]):
            self.__layer_mt.startEditing()
            if self.__layer_mt.isEditable():
                sumbool = 0
                ind = self.__layer_mt.fields().indexFromName('sortnr')
                self.__layer_mt.beginEditCommand("Delete Tour Event")
                for event in tour_list:
                    # update sortnr of tour
                    toursortnr = event[1]
                    sumbool += self.__layer_mt.changeAttributeValue(event[0], ind, toursortnr - 1)
                if sumbool == len(tour_list):
                    if self.__layer_mt.deleteFeature(event_list[0][0]):
                        self.__layer_mt.endEditCommand()
                        self.__layer.endEditCommand()
                        self.__layer.updateExtents()
                        result = True
                    else:
                        self.__layer_mt.destroyEditCommand()
                        self.__layer.rollBack()
                else:
                    self.__layer_mt.destroyEditCommand()
                    self.__layer.rollBack()
            else:
                self.__layer.rollBack()
        else:
            self.__layer.destroyEditCommand()

        return result

    def event_move(self, feat_id_tomove, qgis_point, azi, feat_id_mt, measfield, meas):
        now_utc = self.datetime
        values_dict = {
            'azi': azi,
            'changetstz': now_utc,
            'geomtstz': now_utc
        }
        self.__layer.beginEditCommand("Move Tour Event")
        sumbool = self.attribute_values_change(feat_id_tomove, values_dict)
        sumbool += self.__layer.changeGeometry(feat_id_tomove,
                                               QgsGeometry.fromPointXY(QgsPointXY(qgis_point.x(), qgis_point.y())))
        if sumbool == 2:
            self.__layer_mt.startEditing()
            if self.__layer_mt.isEditable():
                ind = self.__layer_mt.fields().indexFromName(measfield)
                self.__layer_mt.beginEditCommand("Move Tour Event")
                if self.__layer_mt.changeAttributeValue(feat_id_mt, ind, meas):
                    self.__layer_mt.endEditCommand()
                    self.__layer.endEditCommand()
                    self.__layer.updateExtents()
                else:
                    self.__layer_mt.destroyEditCommand()
                    self.__layer.rollBack()
            else:
                self.__layer.rollBack()
        else:
            self.__layer.destroyEditCommand()

    def events_withoutgeom_get(self):
        # no sql, get actual saved attribute values of the layer
        request = QgsFeatureRequest().setFlags(QgsFeatureRequest.NoGeometry)
        request.setSubsetOfAttributes(['event_id'], self.__layer_mt.fields())
        # use set for unique values
        event_uuid_used = set()
        for feature in self.__layer_mt.getFeatures(request):
            event_uuid_used.add(feature['event_id'])
        # get all event_names
        fields = "uuid, name"
        event_names_all = self.__pg_conn.table_select(self.__schema, self.__table_et_name, fields)
        event_uuid_all = set()
        event_namedict = {}
        for val in event_names_all:
            event_uuid_all.add(val[0])
            event_namedict[val[0]] = val[1]

        # compare sets
        event_uuid_unused = set(event_uuid_all).difference(event_uuid_used)
        event_names_unused = [event_namedict[event_uuid] for event_uuid in event_uuid_unused]
        event_names_unused.sort(key=locale.strxfrm)
        return event_names_unused

    def tour_meas_get(self, event_uuid, route_id):
        event_list = self.__events_part_get(event_uuid)
        # inconsistent data, more or less than one point found
        if len(event_list) != 1:
            return None
        event_id = event_list[0][1]
        events_list = self.__events_tour_get(event_id, route_id)
        # order by frommeas
        events_list.sort(key=operator.itemgetter(4), reverse=False)
        return events_list

    def event_append(self, event_uuid, result_fi, result_se, route_id, direction):
        result = False
        event_list = self.__events_part_get(event_uuid)
        # inconsistent data, more or less than one point found
        if len(event_list) != 1:
            return result

        pointtype = event_list[0].index(event_uuid)
        routedir_old = event_list[0][8]
        toursortnr_old = event_list[0][3]

        # decide if new part is before or after
        if pointtype == 5:
            # is frompoint
            if routedir_old:
                toursortnr = toursortnr_old - 1
            else:
                toursortnr = toursortnr_old + 1
        elif pointtype == 7:
            # is topoint
            if routedir_old:
                toursortnr = toursortnr_old + 1
            else:
                toursortnr = toursortnr_old - 1
        else:
            return result
        if toursortnr == 0:
            toursortnr = 1

        # define routedir
        if not direction:
            tomeas = result_fi[1]
            frommeas = result_se[1]
            if toursortnr > toursortnr_old:
                routedir = False
            else:
                routedir = True
            feature_fi, uuid_id_fi = self.__event_feature_get(result_se[0], result_se[2])
            feature_se, uuid_id_se = self.__event_feature_get(result_fi[0], result_fi[2])
        else:
            tomeas = result_se[1]
            frommeas = result_fi[1]
            if toursortnr > toursortnr_old:
                routedir = True
            else:
                routedir = False
            feature_fi, uuid_id_fi = self.__event_feature_get(result_fi[0], result_fi[2])
            feature_se, uuid_id_se = self.__event_feature_get(result_se[0], result_se[2])

        event_id = event_list[0][1]
        events_list = self.__events_tour_get(event_id)
        tour_list = []
        # create list with sortnr to update
        for events in events_list:
            if events[3] >= toursortnr:
                tour_list.append([events[0], events[3]])
        tour_list.sort(key=operator.itemgetter(1), reverse=False)

        self.__layer.beginEditCommand("Append Tour Event")
        if self.__layer.addFeatures([feature_fi, feature_se]):
            self.__layer_mt.startEditing()
            if self.__layer_mt.isEditable():
                sumbool = 0
                ind = self.__layer_mt.fields().indexFromName('sortnr')
                self.__layer_mt.beginEditCommand("Append Tour Event")
                for event in tour_list:
                    # update sortnr of tour
                    sumbool += self.__layer_mt.changeAttributeValue(event[0], ind, event[1] + 1)
                if sumbool == len(tour_list):
                    feature = QgsFeature(self.__layer_mt.fields())
                    feature['uuid'] = self.uuid
                    feature['event_id'] = event_id
                    feature['route_id'] = route_id
                    feature['sortnr'] = toursortnr
                    feature['frommeas'] = frommeas
                    feature['tomeas'] = tomeas
                    feature['frompoint_id'] = uuid_id_fi
                    feature['topoint_id'] = uuid_id_se
                    feature['routedir'] = routedir
                    if self.__layer_mt.addFeature(feature):
                        self.__layer_mt.endEditCommand()
                        self.__layer.endEditCommand()
                        self.__layer.updateExtents()
                        result = True
                    else:
                        self.__layer_mt.destroyEditCommand()
                        self.__layer.rollBack()
                else:
                    self.__layer_mt.destroyEditCommand()
                    self.__layer.rollBack()
            else:
                self.__layer.rollBack()
        else:
            self.__layer.destroyEditCommand()

        return result

    def event_sql_insert(self, qgis_point_fi, qgis_point_se, event_uuid, route_id, route_class, toursortnr, srid,
                         fields_list, fields_values):
        now_utc = self.datetime
        result_fi = route_class.point_meas_get(route_id, qgis_point_fi, srid)
        result_se = route_class.point_meas_get(route_id, qgis_point_se, srid)
        uuid_id_fi = self.uuid
        uuid_id_se = self.uuid
        azi_fi = result_fi[2]
        azi_se = result_se[2]
        if result_fi[1] < result_se[1]:
            # in route direction
            frommeas = result_fi[1]
            frompoint_id = uuid_id_fi
            tomeas = result_se[1]
            topoint_id = uuid_id_se
            routedir = True
        else:
            # opposite route direction
            frommeas = result_se[1]
            frompoint_id = uuid_id_se
            tomeas = result_fi[1]
            topoint_id = uuid_id_fi
            routedir = False

        fields = "uuid, geom, azi, apprtstz, createtstz, changetstz, geomtstz"
        values = "'{uuid}', ST_SetSRID(ST_MakePoint({x}, {y}), {srid}), {azi}, '{now_utc}', '{now_utc}', " \
                 "'{now_utc}', '{now_utc}'" \
                 .format(uuid=uuid_id_fi, x=result_fi[0].x(), y=result_fi[0].y(), srid=srid, azi=azi_fi,
                         now_utc=now_utc)
        self.__pg_conn.table_insert(self.__schema, self.__event_class_name, fields, values)
        values = "'{uuid}', ST_SetSRID(ST_MakePoint({x}, {y}), {srid}), {azi}, '{now_utc}', '{now_utc}', " \
                 "'{now_utc}', '{now_utc}'" \
                 .format(uuid=uuid_id_se, x=result_se[0].x(), y=result_se[0].y(), srid=srid, azi=azi_se,
                         now_utc=now_utc)
        self.__pg_conn.table_insert(self.__schema, self.__event_class_name, fields, values)

        uuid_id = self.uuid
        fields = "uuid, event_id, route_id, sortnr, frommeas, tomeas, frompoint_id, topoint_id, routedir"
        values = "'{uuid}', '{event_id}', '{route_id}', {sortnr}, {frommeas}, {tomeas}, '{frompoint_id}', " \
                 "'{topoint_id}', {routedir}" \
                 .format(uuid=uuid_id, event_id=event_uuid, route_id=route_id, sortnr=toursortnr, frommeas=frommeas,
                         tomeas=tomeas, frompoint_id=frompoint_id, topoint_id=topoint_id, routedir=routedir)

        # additional values of fields to insert
        for i in range(len(fields_list)):
            value = fields_values[i]
            fieldname = fields_list[i]
            field_type = self.__pg_conn.field_type_get(self.__schema, self.__tablename_mt, fieldname)[1]
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

        self.__pg_conn.table_insert(self.__schema, self.__tablename_mt, fields, values)

    def event_insert(self, qgis_point_fi, qgis_point_se, sortnr_fi, sortnr_se, event_uuid, route_id,
                     route_class, toursortnr, srid):
        result_fi = route_class.point_meas_get(route_id, qgis_point_fi, srid, sortnr_fi)
        result_se = route_class.point_meas_get(route_id, qgis_point_se, srid, sortnr_se)
        feature_fi, uuid_id_fi = self.__event_feature_get(result_fi[0], result_fi[2])
        feature_se, uuid_id_se = self.__event_feature_get(result_se[0], result_se[2])
        if result_fi[1] < result_se[1]:
            # in route direction
            frommeas = result_fi[1]
            frompoint_id = uuid_id_fi
            tomeas = result_se[1]
            topoint_id = uuid_id_se
            routedir = True
        else:
            # opposite route direction
            frommeas = result_se[1]
            frompoint_id = uuid_id_se
            tomeas = result_fi[1]
            topoint_id = uuid_id_fi
            routedir = False

        self.__layer.beginEditCommand("Insert Tour Event")
        if self.__layer.addFeatures([feature_fi, feature_se]):
            self.__layer_mt.startEditing()
            if self.__layer_mt.isEditable():
                feature = QgsFeature(self.__layer_mt.fields())
                feature['uuid'] = self.uuid
                feature['event_id'] = event_uuid
                feature['route_id'] = route_id
                feature['sortnr'] = toursortnr
                feature['frommeas'] = frommeas
                feature['tomeas'] = tomeas
                feature['frompoint_id'] = frompoint_id
                feature['topoint_id'] = topoint_id
                feature['routedir'] = routedir
                self.__layer_mt.beginEditCommand("Insert Tour Event")
                if self.__layer_mt.addFeature(feature):
                    self.__layer_mt.endEditCommand()
                    self.__layer.endEditCommand()
                    self.__layer.updateExtents()
                else:
                    self.__layer_mt.destroyEditCommand()
                    self.__layer.rollBack()
            else:
                self.__layer.rollBack()
        else:
            self.__layer.destroyEditCommand()

    def __event_feature_get(self, qgis_point, azi):
        feature = QgsFeature(self.__layer.fields())
        now_utc = self.datetime
        uuid = self.uuid
        feature['uuid'] = uuid
        feature['azi'] = azi
        feature['apprtstz'] = now_utc
        feature['createtstz'] = now_utc
        feature['changetstz'] = now_utc
        feature['geomtstz'] = now_utc
        feature.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(qgis_point.x(), qgis_point.y())))
        return [feature, uuid]

    def __events_tour_get(self, event_id, route_id=None):
        # no sql, get actual saved attribute values of the layer
        # return all values from _mt for a tour (depending of route_id)
        request = QgsFeatureRequest().setFlags(QgsFeatureRequest.NoGeometry)
        request.setSubsetOfAttributes(['uuid', 'route_id', 'sortnr', 'frommeas', 'frompoint_id',
                                       'tomeas', 'topoint_id'], self.__layer_mt.fields())
        if route_id is None:
            expression = "event_id = \'" + event_id + "'"
        else:
            expression = "event_id = \'" + event_id + "' AND route_id = \'" + route_id + "'"
        request.setFilterExpression(expression)
        events_list = []
        for feature in self.__layer_mt.getFeatures(request):
            events_list.append([feature.id(), feature['uuid'], feature['route_id'], feature['sortnr'],
                                feature['frommeas'], feature['frompoint_id'], feature['tomeas'], feature['topoint_id']])
        return events_list

    def __events_part_get(self, event_uuid):
        # no sql, get actual saved attribute values of the layer
        # return single value from _mt (tour part)
        request = QgsFeatureRequest().setFlags(QgsFeatureRequest.NoGeometry)
        request.setSubsetOfAttributes(['event_id', 'route_id', 'sortnr', 'frommeas', 'frompoint_id',
                                       'tomeas', 'topoint_id', 'routedir'], self.__layer_mt.fields())
        expression = "frompoint_id = \'" + event_uuid + "' OR topoint_id = \'" + event_uuid + "'"
        request.setFilterExpression(expression)
        event_list = []
        for feature in self.__layer_mt.getFeatures(request):
            event_list.append([feature.id(), feature['event_id'], feature['route_id'], feature['sortnr'],
                               feature['frommeas'], feature['frompoint_id'], feature['tomeas'], feature['topoint_id'],
                               feature['routedir']])
        return event_list

    def events_approvable_get(self, route_class_name, tolerance, checkonly=False):
        fields = """{id}, {uuid}""".format(id="id", uuid="uuid")
        where = "apprtstz = '1000-01-01 01:01:01'"
        events = self.__pg_conn.table_select(self.__schema, self.__event_class_name, fields, where)

        if checkonly:
            if len(events) > 0:
                return True
            else:
                return False

        event_list = []
        route_id_set = set()
        for event in events:
            fields = """{event_id}, {route_id}, {frommeas}, {tomeas}"""\
                     .format(event_id="event_id", route_id="route_id", frommeas="frommeas", tomeas="tomeas")
            event_uuid = event[1]
            where = "frompoint_id = '" + event_uuid + "'"
            values_mt = self.__pg_conn.table_select(self.__schema, self.__tablename_mt, fields, where)
            pointtype = "from"
            if len(values_mt) == 0:
                where = "topoint_id = '" + event_uuid + "'"
                values_mt = self.__pg_conn.table_select(self.__schema, self.__tablename_mt, fields, where)
                pointtype = "to"
            if pointtype == "from":
                meas = values_mt[0][2]
            else:
                meas = values_mt[0][3]
            route_id = str(values_mt[0][1])
            where = "route_id = '" + route_id + "'"
            route_name = self.__pg_conn.table_select(self.__schema, route_class_name, "name", where)[0][0]
            route_id_set.add(route_name + "%%" + route_id)
            event_id = self.__tour_event_names.event_id_get(None, values_mt[0][0])
            event_name = self.__tour_event_names.event_name_get(event_id)
            event_list.append([route_name, event_name, event[0], meas])

        # sort list by route_name, tour_name and meas
        event_list.sort(key=operator.itemgetter(0, 1, 3))

        route_name_old = ""
        routedict = {}
        tmplist = []
        for count, event in enumerate(event_list):
            route_name = event[0]
            if route_name != route_name_old and count > 0:
                routedict[route_name_old] = tmplist
                tmplist = []
            val = str(event[2]) + ": " + (event[1]) + " / " + str(event[3])
            tmplist.append(val)
            route_name_old = route_name
        # get last one
        if len(event_list) > 0:
            routedict[route_name_old] = tmplist

        # check meas of changed routes
        routeerrdict = {}
        if len(route_id_set) > 0:
            for route_id in route_id_set:
                result = self.events_meas_check(route_id.split("%%")[1], tolerance)
                if result is not None:
                    tmplist = []
                    for errlist in result:
                        val = str(errlist[1]) + ": " + str(errlist[0]) + " / " + str(errlist[2])
                        tmplist.append(val)
                    routeerrdict[route_id.split("%%")[0]] = tmplist

        return routedict, routeerrdict

    def events_meas_check(self, route_id, tolerance):
        fields = """{id}, {event_id}, {frommeas}, {tomeas}, {frompoint_id}, {topoint_id}""" \
                    .format(id="id", event_id="event_id", frommeas="frommeas", tomeas="tomeas",
                            frompoint_id="frompoint_id", topoint_id="topoint_id")
        where = "route_id = '" + route_id + "'"
        order = "event_id ASC, frommeas ASC"
        events_list = self.__pg_conn.table_select(self.__schema, self.__tablename_mt, fields, where, order)

        result = []
        if len(events_list) == 0:
            return None
        event_uuid_old = None
        frommeas_old = 0
        tomeas_old = 0
        for events in events_list:
            frommeas = events[2]
            tomeas = events[3]
            event_uuid = events[1]
            # check measures of tour part
            measerror = False
            if (abs(tomeas - frommeas) < tolerance) or (frommeas > tomeas):
                measerror = True
            # check if on the route are parts of the same tour
            elif event_uuid == event_uuid_old:
                if self.overlaps_check(frommeas, frommeas_old, tomeas, tomeas_old, tolerance):
                    measerror = True

            if measerror:
                where = "uuid = '" + event_uuid + "'"
                try:
                    tour_name = self.__pg_conn.table_select(self.__schema, self.__table_et_name, "name", where)[0][0]
                except IndexError:
                    tour_name = "NONE"
                    pass

                where = "uuid = '" + events[4] + "'"
                feat_from = self.__pg_conn.table_select(self.__schema, self.__event_class_name, "id, geom",
                                                        where)[0]
                feat_id_from = feat_from[0]
                feat_geom_from = feat_from[1]
                where = "uuid = '" + events[5] + "'"
                feat_to = self.__pg_conn.table_select(self.__schema, self.__event_class_name, "id, geom",
                                                      where)[0]
                feat_id_to = feat_to[0]
                feat_geom_to = feat_to[1]
                result.append([tour_name, feat_id_from, frommeas, events[4], feat_geom_from])
                result.append([tour_name, feat_id_to, tomeas, events[5], feat_geom_to])

            frommeas_old = frommeas
            tomeas_old = tomeas
            event_uuid_old = event_uuid

        if len(result) > 0:
            return result
        else:
            return None

    def overlaps_check(self, frommeas, frommeas_old, tomeas, tomeas_old, tolerance):

        # overlapping a part of existing
        if (tomeas - frommeas_old) >= tolerance and tomeas < tomeas_old:
            return True
            # overlapping a part of existing
        if (tomeas_old - frommeas) >= tolerance and frommeas > frommeas_old:
            return True
            # new part over existing
        if (frommeas_old - frommeas) >= tolerance and tomeas - tomeas_old >= tolerance:
            return True
            # new part inside existing
        if (frommeas - frommeas_old) >= tolerance and tomeas_old - tomeas >= tolerance:
            return True
            # exact overlap of existing
        if abs(frommeas - frommeas_old) <= tolerance and abs(tomeas - tomeas_old) <= tolerance:
            return True
            # one overlapping point
        if abs(frommeas - frommeas_old) <= tolerance <= tomeas - tomeas_old:
            return True
            # one overlapping point
        if frommeas_old - frommeas >= tolerance >= abs(tomeas - tomeas_old):
            return True

        return False

    def event_point_check(self):
        # return missing event points (from/to)
        fields = "mt.uuid, mt.frompoint_id, mt.topoint_id, val.uuid"
        tablename_a = self.__tablename_mt + " mt"
        tablename_b = self.__event_class_name + " val"

        where = "val.uuid IS NULL"
        countfield = "mt.uuid"
        a_id_field = "mt.frompoint_id"
        b_id_field = "val.uuid"
        group = "mt.uuid, mt.frompoint_id, mt.topoint_id, val.uuid"

        result = []
        result_frompoint = self.__pg_conn.table_select_count_leftjoin(self.__schema, tablename_a, tablename_b, fields,
                                                                      countfield, a_id_field, b_id_field, group, where)
        for val in result_frompoint:
            result.append(["From", val[0], val[1]])

        a_id_field = "mt.topoint_id"
        result_topoint = self.__pg_conn.table_select_count_leftjoin(self.__schema, tablename_a, tablename_b, fields,
                                                                    countfield, a_id_field, b_id_field, group, where)
        for val in result_topoint:
            result.append(["To", val[0], val[2]])
        return result

    def event_approve(self, feat_id):
        now_utc = self.datetime
        where = "id = " + str(feat_id)
        expression = """apprtstz = '{utc}'""".format(utc=now_utc)
        self.__pg_conn.table_update1(self.__schema, self.__event_class_name, expression, where)

    def layer_mt_changes_commit(self, editing_stop=True):
        if self.__layer_mt.isEditable():
            self.__layer_mt.commitChanges(editing_stop)

    def layer_mt_rollback(self, delete_buffer=True):
        if self.__layer_mt.isEditable():
            self.__layer_mt.rollBack(delete_buffer)

    def layer_mt_modified(self):
        return self.__layer_mt.isModified()
