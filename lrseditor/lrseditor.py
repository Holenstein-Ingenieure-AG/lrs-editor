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
import os
import configparser
from qgis.core import QgsMapLayer, QgsProject
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction, QMessageBox
from qgis.PyQt.QtCore import Qt
# initialize Qt resources from file resources.py
# do not delete, though it isn't referenced
from .resources import *

from .tools.lrsmaptool import LRSMapTool
from .tools.lrsdigitool import LRSDigiTool
from .tools.lrsdeletetool import LRSDeleteTool
from .tools.lrsmovetool import LRSMoveTool
from .tools.lrsrouteclassupdate import LRSRouteClassUpdate
from .tools.lrseventnamesadmin import LRSEventNamesAdmin
from .tools.lrseventapprove import LRSEventApprove
from .gui.eventnamesdockwidget import EventNamesDockWidget
from .gui.eventapprovaldockwidget import EventApprovalDockWidget
from .gui.pointclasscreate import PointClassCreate
from .gui.project import ProjectSettings
from .gui.basesystem import BaseSystemSettings
from .gui.eventclassmanager import EventClassManager
from .gui.datacheck import DataCheck

ICONS_PATH = ':/plugins/lrseditor/icons/'


class LRSEditorPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.canvas = iface.mapCanvas()
        # get plugin directory
        self.plugin_dir = os.path.dirname(__file__)
        # get local language settings: de_CH -> de
        # locale = QSettings().value("locale/userLocale")[0:2]
        # localePath = os.path.join(self.plugin_dir, 'i18n', 'lrsplugin_{}.qm'.format(locale))
        self.lrstoolbar = None
        self.digitool = None
        self.__digitool = None
        self.movetool = None
        self.__movetool = None
        self.deletetool = None
        self.__deletetool = None
        self.eventnamestool = None
        self.__eventnamestool = None
        self.routeupdtool = None
        self.__routeupdtool = None
        self.eventapprtool = None
        self.__eventapprtool = None

        self.__projectmenu = None
        self.__basesystemmenu = None
        self.__sep1 = None
        self.__eventclassmanagermenu = None
        self.__sep2 = None
        self.__datacheckmenu = None
        self.__pointclasscreatemenu = None
        self.__sep3 = None
        self.__aboutmenu = None
        self.__eventnamesdockwidget = None
        self.__eventapprdockwidget = None

        self.layer_previous = None
        self.tool_previous = None
        self.comment_types = [
            'LRS-Editor, Route Class Table',
            'LRS-Editor, Continuous Event Table',
            'LRS-Editor, Point Name Table',
            'LRS-Editor, Base Point Event Table',
            'LRS-Editor, Tour Event Table',
        ]

    def initGui(self):
        # create menu
        self.__projectmenu = QAction("&Project Settings...", self.iface.mainWindow())
        self.iface.addPluginToMenu("&LRS-Editor", self.__projectmenu)
        self.__projectmenu.triggered.connect(self.project_dialog_show)
        self.__basesystemmenu = QAction("&Base System Settings...", self.iface.mainWindow())
        self.iface.addPluginToMenu("&LRS-Editor", self.__basesystemmenu)
        self.__basesystemmenu.triggered.connect(self.basesystem_dialog_show)
        self.__sep1 = QAction(None)
        self.__sep1.setSeparator(True)
        self.iface.addPluginToMenu("&LRS-Editor", self.__sep1)
        self.__eventclassmanagermenu = QAction("&Event Class Manager...", self.iface.mainWindow())
        self.iface.addPluginToMenu("&LRS-Editor", self.__eventclassmanagermenu)
        self.__eventclassmanagermenu.triggered.connect(self.eventclassmanager_dialog_show)
        self.__sep2 = QAction(None)
        self.__sep2.setSeparator(True)
        self.iface.addPluginToMenu("&LRS-Editor", self.__sep2)
        self.__datacheckmenu = QAction("&Data Check...", self.iface.mainWindow())
        self.iface.addPluginToMenu("&LRS-Editor", self.__datacheckmenu)
        self.__datacheckmenu.triggered.connect(self.datacheck_dialog_show)
        self.__pointclasscreatemenu = QAction("&Create Point Class...", self.iface.mainWindow())
        self.iface.addPluginToMenu("&LRS-Editor", self.__pointclasscreatemenu)
        self.__pointclasscreatemenu.triggered.connect(self.pointclass_create_dialog_show)
        self.__sep3 = QAction(None)
        self.__sep3.setSeparator(True)
        self.iface.addPluginToMenu("&LRS-Editor", self.__sep3)
        self.__aboutmenu = QAction("&About...", self.iface.mainWindow())
        self.iface.addPluginToMenu("&LRS-Editor", self.__aboutmenu)
        self.__aboutmenu.triggered.connect(self.about_dialog_show)

        # create tools
        self.__digitool = QAction(QIcon(ICONS_PATH + 'lrseditor_event_dig.png'), "Add Event", self.iface.mainWindow())
        self.__movetool = QAction(QIcon(ICONS_PATH + 'lrseditor_event_move.png'), "Move Event", self.iface.mainWindow())
        self.__deletetool = QAction(QIcon(ICONS_PATH + 'lrseditor_event_delete.png'), "Delete Event",
                                    self.iface.mainWindow())
        self.__eventnamestool = QAction(QIcon(ICONS_PATH + 'lrseditor_event_names.png'), "Admin Event Names",
                                        self.iface.mainWindow())
        self.__routeupdtool = QAction(QIcon(ICONS_PATH + 'lrseditor_route_upd.png'), "Update Route Class",
                                      self.iface.mainWindow())
        self.__eventapprtool = QAction(QIcon(ICONS_PATH + 'lrseditor_event_appr.png'), "Approve Events",
                                       self.iface.mainWindow())
        self.__digitool.setObjectName('LRSEditorAddEvent')
        self.__digitool.triggered.connect(self.digitool_clicked)
        self.__digitool.setCheckable(True)
        self.__digitool.setEnabled(False)
        self.__movetool.setObjectName('LRSEditorMoveEvent')
        self.__movetool.triggered.connect(self.movetool_clicked)
        self.__movetool.setCheckable(True)
        self.__movetool.setEnabled(False)
        self.__deletetool.setObjectName('LRSEditorDeleteEvent')
        self.__deletetool.triggered.connect(self.deletetool_clicked)
        self.__deletetool.setCheckable(True)
        self.__deletetool.setEnabled(False)
        self.__eventnamestool.setObjectName('LRSEditorEventNames')
        self.__eventnamestool.triggered.connect(self.event_names_dialog_show)
        self.__eventnamestool.setCheckable(False)
        self.__eventnamestool.setEnabled(True)
        self.__routeupdtool.setObjectName('LRSEditorRouteUpdate')
        self.__routeupdtool.triggered.connect(self.routeupdtool_run)
        self.__routeupdtool.setCheckable(False)
        self.__routeupdtool.setEnabled(True)
        self.__eventapprtool.setObjectName('LRSEditorApproveEvent')
        self.__eventapprtool.triggered.connect(self.eventapprtool_show)
        self.__eventapprtool.setCheckable(False)
        self.__eventapprtool.setEnabled(True)

        # create toolbar
        self.lrstoolbar = self.iface.addToolBar('LRS-Editor Toolbar')
        self.lrstoolbar.setObjectName("LRSEditorToolbar")
        self.lrstoolbar.setToolTip("LRS-Editor Edit Functions")
        self.lrstoolbar.addAction(self.__digitool)
        self.lrstoolbar.addAction(self.__movetool)
        self.lrstoolbar.addAction(self.__deletetool)
        self.lrstoolbar.addAction(self.__eventnamestool)
        self.lrstoolbar.addAction(self.__routeupdtool)
        self.lrstoolbar.addAction(self.__eventapprtool)

        # get signal for changed layer
        self.iface.currentLayerChanged.connect(self.currentlayer_changed)
        # get signal for changed tools
        self.canvas.mapToolSet.connect(self.tool_changed)

        # DockWidgets, must be set before Tools are enabled
        self.__eventnamesdockwidget = EventNamesDockWidget(self.iface.mainWindow(), self.iface)
        self.__eventapprdockwidget = EventApprovalDockWidget(self.iface.mainWindow(), self.iface)
        # prevent semi-transparent widget when init the plugin -> close
        self.__eventapprdockwidget.close()
        self.__eventnamesdockwidget.close()

    def unload(self):
        # only for tools in interaction with map
        self.canvas.unsetMapTool(self.digitool)
        self.canvas.unsetMapTool(self.movetool)
        self.canvas.unsetMapTool(self.deletetool)

        self.iface.removePluginMenu("&LRS-Editor", self.__projectmenu)
        self.iface.removePluginMenu("&LRS-Editor", self.__basesystemmenu)
        self.iface.removePluginMenu("&LRS-Editor", self.__sep1)
        self.iface.removePluginMenu("&LRS-Editor", self.__eventclassmanagermenu)
        self.iface.removePluginMenu("&LRS-Editor", self.__sep2)
        self.iface.removePluginMenu("&LRS-Editor", self.__datacheckmenu)
        self.iface.removePluginMenu("&LRS-Editor", self.__pointclasscreatemenu)
        self.iface.removePluginMenu("&LRS-Editor", self.__sep3)
        self.iface.removePluginMenu("&LRS-Editor", self.__aboutmenu)

        self.iface.removeToolBarIcon(self.__digitool)
        self.iface.removeToolBarIcon(self.__movetool)
        self.iface.removeToolBarIcon(self.__deletetool)
        self.iface.removeToolBarIcon(self.__eventnamestool)
        self.iface.removeToolBarIcon(self.__routeupdtool)
        self.iface.removeToolBarIcon(self.__eventapprtool)

        self.digitool = None
        self.movetool = None
        self.deletetool = None
        self.eventnamestool = None
        self.routeupdtool = None
        self.eventapprtool = None

        del self.lrstoolbar

        self.iface.removeDockWidget(self.__eventnamesdockwidget)
        self.iface.removeDockWidget(self.__eventapprdockwidget)

    def tool_changed(self, new_tool):
        # when tool changes, check if it is a LRSTool
        if not isinstance(new_tool, LRSMoveTool):
            self.__movetool.setChecked(False)
        if not isinstance(new_tool, LRSDeleteTool):
            self.__deletetool.setChecked(False)
        if not isinstance(new_tool, LRSDigiTool):
            self.__digitool.setChecked(False)

    def currentlayer_changed(self):
        layer = self.iface.activeLayer()
        # disconnect previous layer
        if self.layer_previous is not None:
            try:
                self.layer_previous.editingStarted.disconnect(self.layerediting_started)
            except (TypeError, RuntimeError):
                pass
            try:
                self.layer_previous.editingStopped.disconnect(self.layerediting_stopped)
            except (TypeError, RuntimeError):
                pass
        self.layer_previous = None

        # connect to active layer
        if layer is not None and layer.type() == QgsMapLayer.VectorLayer:
            comment_type = self.comment_type_get()
            if comment_type == 1 or comment_type == 2 or comment_type == 4:
                layer.editingStarted.connect(self.layerediting_started)
                layer.editingStopped.connect(self.layerediting_stopped)
                self.layer_previous = layer

        if layer is None or not layer.isValid() or (layer.type() != QgsMapLayer.VectorLayer):
            self.__digitool.setEnabled(False)
            self.__movetool.setEnabled(False)
            self.__deletetool.setEnabled(False)
            self.__eventnamestool.setEnabled(False)
            return
        if layer.isEditable():
            self.layerediting_started()
        else:
            self.layerediting_stopped()

    def layerediting_stopped(self):
        self.__digitool.setEnabled(False)
        self.__digitool.setChecked(False)
        self.__movetool.setEnabled(False)
        self.__movetool.setChecked(False)
        self.__deletetool.setEnabled(False)
        self.__deletetool.setChecked(False)
        comment_type = self.comment_type_get()
        if comment_type == 1 or comment_type == 2 or comment_type == 4:
            self.__eventnamestool.setEnabled(True)
        else:
            self.__eventnamestool.setEnabled(False)
        self.__routeupdtool.setEnabled(True)
        self.__eventapprtool.setEnabled(True)
        self.__eventnamesdockwidget.close()
        self.__eventapprdockwidget.close()
        if self.tool_previous is not None:
            self.canvas.setMapTool(self.tool_previous)

    def layerediting_started(self):
        layer = self.iface.activeLayer()
        if layer is None or not layer.isValid() or (layer.type() != QgsMapLayer.VectorLayer) or not layer.isEditable():
            return
        comment_type = self.comment_type_get()
        # check if LRS-Layer
        if comment_type == 1 or comment_type == 2 or comment_type == 4:
            # check for route class in project
            layers = QgsProject.instance().mapLayers().values()
            routeclasslayer = None
            for lay in layers:
                if lay.isValid() and (lay.type() == QgsMapLayer.VectorLayer):
                    val = lay.dataComment()
                    if val == self.comment_types[0]:
                        routeclasslayer = lay
                        break
            if routeclasslayer is None:
                self.iface.messageBar().pushInfo("No Route Class", "Add Route Class to QGIS Project before editing.")
                return

            self.iface.messageBar().pushInfo("LRS Event Classes", "Edit only with LRS Toolbar!")
            if not isinstance(self.canvas.mapTool(), LRSMapTool):
                self.tool_previous = self.canvas.mapTool()
            self.__digitool.setEnabled(True)
            self.__movetool.setEnabled(True)
            self.__deletetool.setEnabled(True)
            self.__eventnamestool.setEnabled(False)
            self.__routeupdtool.setEnabled(False)
            self.__eventapprtool.setEnabled(False)

            if comment_type == 1:
                if isinstance(self.canvas.mapTool(), LRSMoveTool) or isinstance(self.canvas.mapTool(), LRSDigiTool):
                    self.__eventnamesdockwidget.form_update()
                    self.iface.addDockWidget(Qt.RightDockWidgetArea, self.__eventnamesdockwidget)
            else:
                self.__eventnamesdockwidget.close()

            # disable QGIS Tools
            vertextool = self.iface.mainWindow().findChild(QAction, 'mActionVertexToolActiveLayer')
            vertextool.setEnabled(False)
            addfeattool = self.iface.mainWindow().findChild(QAction, 'mActionAddFeature')
            addfeattool.setEnabled(False)
        else:
            # other layer
            self.__digitool.setEnabled(False)
            self.__movetool.setEnabled(False)
            self.__deletetool.setEnabled(False)
            self.__eventnamestool.setEnabled(False)
            self.__routeupdtool.setEnabled(False)
            self.__eventapprtool.setEnabled(False)

            self.__eventnamesdockwidget.close()

    def comment_type_get(self):
        layer = self.iface.activeLayer()
        comment_type = -1
        if layer is None or not layer.isValid() or (layer.type() != QgsMapLayer.VectorLayer):
            return comment_type

        val = layer.dataComment()
        try:
            comment_type = self.comment_types.index(val)
        except ValueError:
            pass
        return comment_type

    def digitool_clicked(self):
        self.digitool = LRSDigiTool(self.iface, self.__eventnamesdockwidget)
        if self.digitool.approvable_check():
            if self.tool_previous is not None:
                self.canvas.setMapTool(self.tool_previous)
            return

        comment_type = self.comment_type_get()
        if comment_type == 1:
            self.__eventnamesdockwidget.form_update()
            self.iface.addDockWidget(Qt.RightDockWidgetArea, self.__eventnamesdockwidget)

        self.canvas.setMapTool(self.digitool)

    def movetool_clicked(self):
        self.movetool = LRSMoveTool(self.iface, self.__eventnamesdockwidget)
        if self.movetool.approvable_check():
            if self.tool_previous is not None:
                self.canvas.setMapTool(self.tool_previous)
            return

        comment_type = self.comment_type_get()
        if comment_type == 1:
            self.__eventnamesdockwidget.form_update()
            self.iface.addDockWidget(Qt.RightDockWidgetArea, self.__eventnamesdockwidget)

        self.canvas.setMapTool(self.movetool)

    def deletetool_clicked(self):
        self.deletetool = LRSDeleteTool(self.iface)
        if self.deletetool.approvable_check():
            if self.tool_previous is not None:
                self.canvas.setMapTool(self.tool_previous)
            return

        self.__eventnamesdockwidget.close()

        self.canvas.setMapTool(self.deletetool)

    def event_names_dialog_show(self):
        self.eventnamestool = LRSEventNamesAdmin(self.iface)
        if not self.eventnamestool.approvable_check():
            self.eventnamestool.dialog_show()

    def routeupdtool_run(self):
        self.routeupdtool = LRSRouteClassUpdate(self.iface)
        if not self.routeupdtool.lrs_layer_check():
            return
        if not self.routeupdtool.approvable_check():
            self.routeupdtool.update()

    def eventapprtool_show(self):
        self.eventapprtool = LRSEventApprove(self.iface)
        if not self.eventapprtool.lrs_layer_check():
            return
        if self.eventapprtool.approvable_check(False):
            self.__eventapprdockwidget.form_update()
            self.iface.addDockWidget(Qt.RightDockWidgetArea, self.__eventapprdockwidget)

    def project_dialog_show(self):
        dlg = ProjectSettings(self.iface)
        dlg.exec_()

    def basesystem_dialog_show(self):
        dlg = BaseSystemSettings(self.iface)
        dlg.exec_()

    def eventclassmanager_dialog_show(self):
        dlg = EventClassManager(self.iface)
        dlg.exec_()

    def datacheck_dialog_show(self):
        dlg = DataCheck(self.iface)
        dlg.exec_()

    def pointclass_create_dialog_show(self):
        dlg = PointClassCreate(self.iface)
        dlg.exec_()

    def about_dialog_show(self):
        metadata_path = os.path.join(self.plugin_dir, "metadata.txt")
        metadata_file = configparser.ConfigParser()
        metadata_file.read(metadata_path)
        version_text = metadata_file.get('general', 'version')
        description_text = metadata_file.get('general', 'description')

        msg = QMessageBox()
        msg.setIcon(QMessageBox.Information)
        msg.setTextFormat(Qt.RichText)
        msg.setWindowTitle("About LRS-Editor")
        msg.setText(
            """<h2>{title}</h2>
            <h4>{t1}</h4>
            <p>{t2}</p>
            <p align="justify">{t3}</p>"""
            .format(title="LRS-Editor", t1=description_text,
                    t2="Version {version}".format(version=version_text),
                    t3='The project is open source under the terms of GPLv2 or later.'
                       ' Developed and maintained by <a href="https://h-ing.ch">Holenstein Ingenieure AG</a>'
                       ' in cooperation with the <a href="https://geoinformation.tg.ch/">'
                       'Amt für Geoinformation of the Canton of Thurgau</a>,'
                       ' source code is on <a href="https://github.com/Holenstein-Ingenieure-AG/lrs-editor">'
                       'github</a>.'
                    )
        )
        msg.setStandardButtons(QMessageBox.Close)
        msg.exec_()
