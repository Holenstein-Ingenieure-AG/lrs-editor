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
from qgis.core import QgsProject, QgsSettings, QgsApplication, QgsAuthMethodConfig, QgsMapLayer, QgsDataSourceUri
from qgis.core import QgsVectorLayer
from qgis.gui import QgsVertexMarker
from qgis.PyQt import QtGui

SETTINGS_CONN_PATH = "PostgreSQL/connections/"


def qgis_entries_set(conn_type, conn_name, dbname, host, schema, port):
    qgisproj = QgsProject.instance()
    if conn_type == "project":
        qgisproj.writeEntry("LRS-Editor", "conn/conn_name", conn_name)
        qgisproj.writeEntry("LRS-Editor", "conn/dbname", dbname)
        qgisproj.writeEntry("LRS-Editor", "conn/host", host)
        qgisproj.writeEntry("LRS-Editor", "conn/schema", schema)
        qgisproj.writeEntry("LRS-Editor", "conn/port", port)
    elif conn_type == "basesystem":
        qgisproj.writeEntry("LRS-Editor", "conn_bs/conn_name", conn_name)
        qgisproj.writeEntry("LRS-Editor", "conn_bs/dbname", dbname)
        qgisproj.writeEntry("LRS-Editor", "conn_bs/host", host)
        qgisproj.writeEntry("LRS-Editor", "conn_bs/schema", schema)
        qgisproj.writeEntry("LRS-Editor", "conn_bs/port", port)


def qgis_entries_get(conn_type):
    qgisproj = QgsProject.instance()
    if conn_type == "project":
        conn_name = qgisproj.readEntry("LRS-Editor", "conn/conn_name", "None")[0]
        if conn_name == "None":
            return None
        dbname = qgisproj.readEntry("LRS-Editor", "conn/dbname", "None")[0]
        host = qgisproj.readEntry("LRS-Editor", "conn/host", "None")[0]
        schema = qgisproj.readEntry("LRS-Editor", "conn/schema", "None")[0]
        port = qgisproj.readEntry("LRS-Editor", "conn/port", "None")[0]
    else:
        conn_name = qgisproj.readEntry("LRS-Editor", "conn_bs/conn_name", "None")[0]
        if conn_name == "None":
            return None
        dbname = qgisproj.readEntry("LRS-Editor", "conn_bs/dbname", "None")[0]
        host = qgisproj.readEntry("LRS-Editor", "conn_bs/host", "None")[0]
        schema = qgisproj.readEntry("LRS-Editor", "conn_bs/schema", "None")[0]
        port = qgisproj.readEntry("LRS-Editor", "conn_bs/port", "None")[0]

    return conn_name, dbname, host, schema, port


def connection_names_get():
    settings = QgsSettings()
    settings.beginGroup(SETTINGS_CONN_PATH)
    keys = settings.allKeys()
    conn_name_list = []
    for key in keys:
        if key[-8:] == "database":
            # get connection names
            conn_name_list.append(key.split("/")[0])
    settings.endGroup()
    conn_name_list.sort()
    return conn_name_list


def connection_params_get(connection_name):
    groupname = SETTINGS_CONN_PATH + connection_name
    settings = QgsSettings()
    settings.beginGroup(groupname)
    host = settings.value('host')
    port = settings.value('port')
    dbname = settings.value('database')
    # sslmode = settings.value('sslmode')
    settings.endGroup()
    return host, port, dbname


def credentials_get(connection_name):
    groupname = SETTINGS_CONN_PATH + connection_name
    settings = QgsSettings()
    settings.beginGroup(groupname)
    auth_cfg_id = settings.value('authcfg', None)
    # check if authentication config id exists
    user = None
    passwd = None

    if auth_cfg_id:
        auth_man = QgsApplication.authManager()
        auth_cfg = QgsAuthMethodConfig()
        # load config from database (auth manager) into subclass
        auth_man.loadAuthenticationConfig(auth_cfg_id, auth_cfg, True)
        if auth_cfg.id():
            user = auth_cfg.config('username', '')
            passwd = auth_cfg.config('password', '')

    # credentials saved in settings (not recommended)
    else:
        user = settings.value('username')
        passwd = settings.value('password')

    settings.endGroup()
    # comment to allow empty user/passwd (e.g. Kerberos)
    # if not user or not passwd: return None
    return user, passwd


def layer_by_tablename_get(schema, tablename):
    maplayers = QgsProject.instance().mapLayers().values()
    for maplayer in maplayers:
        if maplayer.isValid() and (maplayer.type() == QgsMapLayer.VectorLayer):
            searchstring = '"' + schema + '"."' + tablename + '"'
            if searchstring in maplayer.source():
                return maplayer


def tablename_by_layername_get(schema, layername):
    maplayers = QgsProject.instance().mapLayers().values()
    for maplayer in maplayers:
        if maplayer.isValid() and (maplayer.type() == QgsMapLayer.VectorLayer):
            if maplayer.name == layername:
                searchstring = 'table="' + schema + '".'
                for spl in maplayer.source().split():
                    if searchstring in spl:
                        return spl.split(".")[1].replace('"', '')


def layer_create(entries, credentials, layername, geomfield, readonly, srid, lrslayer=True):
    uri = QgsDataSourceUri()
    uri.setConnection(entries[2], entries[4], entries[1], credentials[0], credentials[1], QgsDataSourceUri.SslDisable)
    # qgis needs an id-Field! (Important for views)
    uri.setDataSource(entries[3], layername, geomfield, "", "id")
    if geomfield is not None:
        uri.setSrid(str(srid))
    layer = QgsVectorLayer(uri.uri(False), layername, "postgres")
    if not layer.isValid():
        return None
    # flag values from 0 to 7, see docs
    # 5: required, searchable, identifiable
    if lrslayer:
        layer.setFlags(QgsMapLayer.LayerFlag(5))
    layer.setReadOnly(readonly)
    return layer


def fields_readonly_set(layer, fields):
    form_config = layer.editFormConfig()
    for fieldname in fields:
        ind = layer.fields().indexFromName(fieldname)
        form_config.setReadOnly(ind, True)
    layer.setEditFormConfig(form_config)


def qgis_point_get(canvas, mouse_event):
    # returns QgsPointXY
    x = mouse_event.pos().x()
    y = mouse_event.pos().y()
    return canvas.getCoordinateTransform().toMapCoordinates(int(x), int(y))


def layer_select_by_rect(layer, rect, selection_behavior):
    if selection_behavior == "set":
        selection_enum = QgsVectorLayer.SetSelection
    elif selection_behavior == "add":
        selection_enum = QgsVectorLayer.AddToSelection
    elif selection_behavior == "intersect":
        selection_enum = QgsVectorLayer.IntersectSelection
    elif selection_behavior == "remove":
        selection_enum = QgsVectorLayer.RemoveFromSelection
    else:
        selection_enum = QgsVectorLayer.SetSelection

    layer.selectByRect(rect, selection_enum)


def layer_selection_values_get(layer, fieldnames):
    # returns values as list in order of the input fieldnames
    sel_feats_id = set(layer.selectedFeatureIds())
    # do not call getFeatures in a loop
    sel_feats = [feat for feat in layer.getFeatures() if feat.id() in sel_feats_id]

    valuelist = []
    for feat in sel_feats:
        values = []
        for fieldname in fieldnames:
            values.append(feat[fieldname])
        valuelist.append(values)

    return valuelist


def digimarker_get(canvas, point):
    marker = QgsVertexMarker(canvas)
    marker.setIconType(3)
    marker.setColor(QtGui.QColor(255, 0, 0))
    marker.setIconSize(10)
    marker.setPenWidth(2)
    marker.setCenter(point)
    return marker


def snapmarker_get(canvas, point):
    marker = QgsVertexMarker(canvas)
    marker.setIconType(1)
    marker.setColor(QtGui.QColor(255, 0, 255))
    marker.setIconSize(12)
    marker.setPenWidth(3)
    marker.setCenter(point)
    return marker
