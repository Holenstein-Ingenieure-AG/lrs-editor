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
import datetime


class LogFile:
    def __init__(self, path):
        self.__fullfilename = path
        if os.path.exists(self.__fullfilename):
            os.remove(self.__fullfilename)
        self.__file = open(self.__fullfilename, 'a')
        self.__starttime = self.__datetime_get()[0]
        self.__warn_count = 0
        self.__err_count = 0

        self.__file.write(self.__datetime_get()[1] + "|INFORM |LRS-EDITOR - LOGFILE" + '\n')

    def __datetime_get(self):
        now = datetime.datetime.now()
        # get time without microseconds
        dtime = now.replace(microsecond=0)
        # time as string
        stime = now.strftime("%Y-%m-%d %H:%M:%S")
        return [dtime, stime]

    def write(self, text, logtype="INFORM"):
        if logtype == "WARNING":
            self.__warn_count += 1
        elif logtype == "ERROR":
            self.__err_count += 1
            logtype = logtype + "  "
        elif logtype == "INFORM":
            logtype = logtype + " "
        elif logtype == "UPDATE":
            logtype = logtype + " "

        self.__file.write(self.__datetime_get()[1] + "|" + logtype + "|" + text + '\n')

    def close(self):
        finaltime = self.__datetime_get()[0]
        duration = finaltime - self.__starttime
        text = self.__datetime_get()[1] + "|INFORM |WARNINGS: " + str(self.__warn_count) + \
                                          ", ERRORS: " + str(self.__err_count) + '\n'
        self.__file.write(text)
        self.__file.write(self.__datetime_get()[1] + "|INFORM |DURATION: " + str(duration))
        self.__file.close()

    def __del__(self):
        self.__file.close()

    @property
    def warn_count(self):
        return self.__warn_count

    @property
    def err_count(self):
        return self.__err_count
