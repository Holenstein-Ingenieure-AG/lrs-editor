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
import psycopg2
import psycopg2.extras

EXCLUDE_TABLENAME = ["lrs_project", "lrs_basesystem", "lrs_event_classes", "lrs_route_class", "lrs_tmp1",
                     "lrs_check_class"]


class PGConn:
    def __init__(self, dbname, host, port, user, passwd):
        self.dbname = dbname
        self.host = host
        self.port = port
        self.user = user
        self.passwd = passwd
        self.conn = None

    def conn_dsn_get(self):
        dsn_dict = self.conn.get_dsn_parameters()
        return dsn_dict

    def db_connect(self):
        return_message = None
        try:
            self.conn = psycopg2.connect(dbname=self.dbname, host=self.host, user=self.user, password=self.passwd,
                                         port=self.port)
        except psycopg2.Error as e:
            return_message = str(e)
        finally:
            return return_message

    def db_close(self):
        if self.conn is not None:
            self.conn.close()
            self.conn = None

    def postgis_exists(self):
        cur = self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        query = """SELECT EXISTS(SELECT extname FROM pg_catalog.pg_extension WHERE extname = 'postgis')"""
        cur.execute(query)
        return bool(cur.fetchone()[0])

    def srid_auth_get(self, srid):
        cur = self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        query = """SELECT auth_name, auth_srid FROM public.spatial_ref_sys WHERE srid = {srid}"""\
                .format(srid=srid)
        cur.execute(query)
        result = cur.fetchone()
        return result

    def srid_find(self, schema, tablename, geomfield):
        cur = self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        query = """SELECT Find_SRID('{schema}', '{tablename}', '{geomfield}');"""\
                .format(schema=schema, tablename=tablename, geomfield=geomfield)
        cur.execute(query)
        return cur.fetchone()[0]

    def system_table_exists(self, tablename):
        if tablename in EXCLUDE_TABLENAME:
            return True
        else:
            return False

    def table_exists(self, schema, tablename):
        cur = self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        query = """SELECT EXISTS(SELECT * FROM pg_catalog.pg_tables WHERE schemaname = '{schema}' AND 
                tablename = '{tablename}')""".format(schema=schema, tablename=tablename)
        cur.execute(query)
        return bool(cur.fetchone()[0])

    def table_rename(self, schema, tablename, tablename_new):
        cur = self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        query = """ALTER TABLE {schema}.{tablename} RENAME TO {tablename_new};""" \
                .format(schema=schema, tablename=tablename, tablename_new=tablename_new)
        cur.execute(query)
        self.conn.commit()

    def tablenames_get(self, schema):
        cur = self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        query = """SELECT tablename FROM pg_catalog.pg_tables WHERE schemaname = '{schema}'"""\
                .format(schema=schema)
        cur.execute(query)
        rows_list = cur.fetchall()
        tablename_list = []
        for row in rows_list:
            if not row[0] in EXCLUDE_TABLENAME:
                tablename_list.append(row[0])
        return sorted(tablename_list)

    def tablenames_geom_get(self, schema, dimension):
        cur = self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        query = """SELECT f_table_name, type, coord_dimension FROM public.geometry_columns 
                WHERE f_table_schema = '{schema}' AND coord_dimension = {dimension}"""\
                .format(schema=schema, dimension=dimension)
        cur.execute(query)
        rows_list = cur.fetchall()
        tables_list = []
        for row in rows_list:
            if not row[0] in EXCLUDE_TABLENAME:
                tables_list.append([row[0], row[1]])
        return sorted(tables_list)

    def field_exists(self, schema, tablename, field):
        cur = self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        query = """SELECT EXISTS(SELECT * FROM information_schema.columns 
                WHERE table_schema = '{schema}' AND table_name = '{tablename}' AND column_name = '{field}')"""\
                .format(schema=schema, tablename=tablename, field=field)
        cur.execute(query)
        return bool(cur.fetchone()[0])

    def field_type_get(self, schema, tablename, field):
        cur = self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        query = """SELECT table_name, column_name, data_type FROM information_schema.columns WHERE
                table_schema = '{schema}' AND table_name = '{tablename}' AND column_name = '{field}'""" \
                .format(schema=schema, tablename=tablename, field=field)
        cur.execute(query)
        data_type = cur.fetchone()[2]
        # mapping/generalize the different data types
        type_dict = {'bigint': 'number', 'integer': 'number', 'smallint': 'number', 'double precision': 'number',
                     'numeric': 'number', 'real': 'number', 'text': 'string', 'character': 'string',
                     'character varying': 'string', 'date': 'date', 'time': 'time', 'timestamp': 'timestamp',
                     'boolean': 'boolean'}
        return [data_type, type_dict.get(data_type, 'other')]

    def field_null_value_check(self, schema, tablename, field, isnumeric):
        cur = self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        if isnumeric:
            query = """SELECT COUNT(*) FROM {schema}.{tablename} WHERE {field} IS NULL """\
                    .format(schema=schema, tablename=tablename, field=field)
        else:
            query = """SELECT COUNT(*) FROM {schema}.{tablename} WHERE {field} = '' IS NOT FALSE """ \
                    .format(schema=schema, tablename=tablename, field=field)
        cur.execute(query)
        return cur.fetchall()[0][0]

    def fieldnames_get(self, schema, tablename):
        cur = self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        query = """SELECT table_schema, table_name, column_name, data_type FROM information_schema.columns WHERE 
                table_schema = '{schema}' AND table_name = '{tablename}' ORDER BY column_name ASC;""" \
                .format(schema=schema, tablename=tablename)
        cur.execute(query)
        rows_list = cur.fetchall()
        # mapping/generalize the different data types
        type_dict = {'bigint': 'integer', 'integer': 'integer', 'smallint': 'integer', 'double precision': 'float',
                     'numeric': 'float', 'real': 'float', 'text': 'string', 'character': 'string',
                     'character varying': 'string', 'date': 'date', 'time': 'time', 'timestamp': 'timestamp',
                     'boolean': 'boolean'}
        fieldname_list = []
        for row in rows_list:
            fieldname_list.append([row[2], type_dict.get(row[3].lower(), 'other')])
        return fieldname_list

    def fieldnames_geom_get(self, schema, tablename):
        cur = self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        query = """SELECT f_table_schema, f_table_name, f_geometry_column FROM public.geometry_columns WHERE  
                f_table_schema = '{schema}' AND f_table_name = '{tablename}' ORDER BY f_geometry_column ASC;""" \
                .format(schema=schema, tablename=tablename)
        cur.execute(query)
        rows_list = cur.fetchall()
        fieldname_list = []
        for row in rows_list:
            fieldname_list.append(row[2])
        return fieldname_list

    def row_exists(self, schema, tablename, where):
        cur = self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        query = """SELECT EXISTS(SELECT 1 FROM {schema}.{tablename} WHERE {where});"""\
                .format(schema=schema, tablename=tablename, where=where)
        cur.execute(query)
        return bool(cur.fetchone()[0])

    def table_truncate(self, schema, tablename):
        cur = self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        trunc = """TRUNCATE {schema}.{tablename} RESTART IDENTITY;""" \
            .format(schema=schema, tablename=tablename)
        cur.execute(trunc)
        self.conn.commit()

    def view_drop(self, schema, viewname):
        cur = self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        drop = """DROP VIEW IF EXISTS {schema}.{viewname} CASCADE;""".format(schema=schema, viewname=viewname)
        cur.execute(drop)
        self.conn.commit()

    def schemes_get(self):
        cur = self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        query = "SELECT nspname FROM pg_namespace WHERE nspname !~ '^pg_' AND nspname != 'information_schema'"
        cur.execute(query)
        schemes_list = map(lambda row: row[0], cur.fetchall())
        return sorted(schemes_list)

    def table_proj_create(self, schema):
        cur = self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        lrs_project_name = EXCLUDE_TABLENAME[0]
        create = """CREATE TABLE {schema}.{lrs_project_name}(id SERIAL PRIMARY KEY, name VARCHAR(100) UNIQUE NOT NULL,
                    routeclass VARCHAR(100) NOT NULL, tolerance DOUBLE PRECISION NOT NULL, logfile TEXT NOT NULL, 
                    routeupdatetstz TIMESTAMPTZ, srid INTEGER NOT NULL);"""\
                    .format(schema=schema, lrs_project_name=lrs_project_name)
        cur.execute(create)
        comment = """COMMENT ON TABLE {schema}.{lrs_project_name} IS 'LRS-Editor, Project System Table';""" \
                  .format(schema=schema, lrs_project_name=lrs_project_name)
        cur.execute(comment)
        self.conn.commit()

    def table_basesystem_create(self, schema):
        cur = self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        lrs_basesystem_name = EXCLUDE_TABLENAME[1]
        create = """CREATE TABLE {schema}.{lrs_basesystem_name}(id SERIAL PRIMARY KEY, 
                    name VARCHAR(100) UNIQUE NOT NULL,
                    project_id INTEGER NOT NULL, tolerance DOUBLE PRECISION NOT NULL, baseclass VARCHAR(100) NOT NULL,
                    basegeom VARCHAR(100) NOT NULL, baserouteid VARCHAR(100) NOT NULL, pointclass VARCHAR(100) NOT NULL,
                    pointgeom VARCHAR(100) NOT NULL, pointrouteid VARCHAR(100) NOT NULL, 
                    pointsortnr VARCHAR(100) NOT NULL, pointtype VARCHAR(100) NOT NULL);"""\
                    .format(schema=schema, lrs_basesystem_name=lrs_basesystem_name)
        cur.execute(create)
        comment = """COMMENT ON TABLE {schema}.{lrs_basesystem_name} IS 'LRS-Editor, Basesystem System Table';""" \
                  .format(schema=schema, lrs_basesystem_name=lrs_basesystem_name)
        cur.execute(comment)
        self.conn.commit()

    def table_event_classes_create(self, schema):
        cur = self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        lrs_event_classes_name = EXCLUDE_TABLENAME[2]
        create = """CREATE TABLE {schema}.{lrs_event_classes_name}(id SERIAL PRIMARY KEY, 
                    name VARCHAR(100) UNIQUE NOT NULL,
                    project_id INTEGER NOT NULL, type VARCHAR(2) NOT NULL, options INTEGER NOT NULL );"""\
                    .format(schema=schema, lrs_event_classes_name=lrs_event_classes_name)
        cur.execute(create)
        comment = """COMMENT ON TABLE {schema}.lrs_event_classes IS 'LRS-Editor, Event Classes System Table';""" \
                  .format(schema=schema, lrs_event_classes_name=lrs_event_classes_name)
        cur.execute(comment)
        self.conn.commit()

    def table_check_class_create(self, schema, srid):
        cur = self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        lrs_check_class_name = EXCLUDE_TABLENAME[5]
        create = """CREATE TABLE {schema}.{lrs_check_class_name}(id SERIAL PRIMARY KEY, geom geometry(Point,{srid}), 
                    class_name VARCHAR(100) NOT NULL, uuid UUID, category VARCHAR(10) NOT NULL,
                    route_name VARCHAR(100), description VARCHAR(200) NOT NULL);"""\
                    .format(schema=schema, lrs_check_class_name=lrs_check_class_name, srid=srid)
        cur.execute(create)
        idx = """CREATE INDEX IF NOT EXISTS idx_{lrs_check_class_name}_geom ON {schema}.{lrs_check_class_name}
                 USING gist (geom)""".format(schema=schema, lrs_check_class_name=lrs_check_class_name)
        cur.execute(idx)
        comment = """COMMENT ON TABLE {schema}.{lrs_check_class_name} IS 'LRS-Editor, Check Class System Table';""" \
            .format(schema=schema, lrs_check_class_name=lrs_check_class_name)
        cur.execute(comment)
        self.conn.commit()

    def table_select(self, schema, tablename, fields, where=None, order=None):
        cur = self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        if not where and not order:
            query = """SELECT {fields} FROM {schema}.{tablename};"""\
                .format(fields=fields, schema=schema, tablename=tablename)
        elif where and not order:
            query = """SELECT {fields} FROM {schema}.{tablename} WHERE {where};"""\
                .format(fields=fields, schema=schema, tablename=tablename, where=where)
        elif not where and order:
            query = """SELECT {fields} FROM {schema}.{tablename} ORDER BY {order};"""\
                .format(fields=fields, schema=schema, tablename=tablename, order=order)
        else:
            query = """SELECT {fields} FROM {schema}.{tablename} WHERE {where} ORDER BY {order};"""\
                .format(fields=fields, schema=schema, tablename=tablename, where=where, order=order)
        cur.execute(query)
        rows_list = cur.fetchall()
        return rows_list

    def table_select_group(self, schema, tablename, fields, group, where=None, order=None):
        cur = self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        if not where and not order:
            query = """SELECT {fields} FROM {schema}.{tablename} GROUP BY {group};"""\
                .format(fields=fields, schema=schema, tablename=tablename, group=group)
        elif not where and order:
            query = """SELECT {fields} FROM {schema}.{tablename} GROUP BY {group} ORDER BY {order};"""\
                .format(fields=fields, schema=schema, tablename=tablename, group=group, order=order)
        elif where and not order:
            query = """SELECT {fields} FROM {schema}.{tablename} WHERE {where} GROUP BY {group};"""\
                .format(fields=fields, schema=schema, tablename=tablename, where=where, group=group)
        else:
            query = """SELECT {fields} FROM {schema}.{tablename} WHERE {where} GROUP BY {group} ORDER BY {order};"""\
                .format(fields=fields, schema=schema, tablename=tablename, where=where, group=group, order=order)
        cur.execute(query)
        rows_list = cur.fetchall()
        return rows_list

    def table_select_count_leftjoin(self, schema, tablename_a, tablename_b, fields, countfield, a_id_field,
                                    b_id_field, group, where=None, order=None):
        cur = self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        if not where and not order:
            query = """SELECT {fields}, COUNT({countfield}) FROM {schema}.{tablename_a} LEFT JOIN  
                    {schema}.{tablename_b} ON {a_id_field} = {b_id_field} GROUP BY {group};""" \
                    .format(schema=schema, tablename_a=tablename_a, tablename_b=tablename_b, fields=fields,
                            countfield=countfield, a_id_field=a_id_field, b_id_field=b_id_field, group=group)
        elif where and not order:
            query = """SELECT {fields}, COUNT({countfield}) FROM {schema}.{tablename_a} LEFT JOIN  
                    {schema}.{tablename_b} ON {a_id_field} = {b_id_field} WHERE {where} GROUP BY {group};""" \
                    .format(schema=schema, tablename_a=tablename_a, tablename_b=tablename_b, fields=fields,
                            countfield=countfield, a_id_field=a_id_field, b_id_field=b_id_field, where=where,
                            group=group)
        elif not where and order:
            query = """SELECT {fields}, COUNT({countfield}) FROM {schema}.{tablename_a} LEFT JOIN  
                    {schema}.{tablename_b} ON {a_id_field} = {b_id_field} GROUP BY {group} ORDER BY {order};""" \
                    .format(schema=schema, tablename_a=tablename_a, tablename_b=tablename_b, fields=fields,
                            countfield=countfield, a_id_field=a_id_field, b_id_field=b_id_field, group=group,
                            order=order)
        else:
            query = """SELECT {fields}, COUNT({countfield}) FROM {schema}.{tablename_a} LEFT JOIN  
                    {schema}.{tablename_b} ON {a_id_field} = {b_id_field} WHERE {where} GROUP BY {group} 
                    ORDER BY {order};""" \
                    .format(schema=schema, tablename_a=tablename_a, tablename_b=tablename_b, fields=fields,
                            countfield=countfield, a_id_field=a_id_field, b_id_field=b_id_field, where=where,
                            group=group, order=order)

        cur.execute(query)
        rows_list = cur.fetchall()
        return rows_list

    def table_delete_row(self, schema, tablename, where):
        cur = self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        delete = """DELETE FROM {schema}.{tablename} WHERE {where};""" \
                 .format(schema=schema, tablename=tablename, where=where)
        cur.execute(delete)
        self.conn.commit()

    def table_insert(self, schema, tablename, fields, values, returnfield=None):
        cur = self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        if not returnfield:
            insert = """INSERT INTO {schema}.{tablename} ({fields}) VALUES ({values});""" \
                    .format(schema=schema, tablename=tablename, fields=fields, values=values)
        else:
            insert = """INSERT INTO {schema}.{tablename} ({fields}) VALUES ({values}) RETURNING {retfield};""" \
                    .format(schema=schema, tablename=tablename, fields=fields, values=values, retfield=returnfield)
        cur.execute(insert)
        self.conn.commit()
        # returning last, new value of returnfield
        if returnfield:
            return cur.fetchone()[0]

    def table_insert_fromtable(self, schema, tablename, fields, fromfields, fromtablename, where=None):
        cur = self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        if not where:
            insert = """INSERT INTO {schema}.{tablename} ({fields}) SELECT {fromfields} FROM 
                    {schema}.{fromtablename};""" \
                    .format(schema=schema, tablename=tablename, fields=fields, fromfields=fromfields,
                            fromtablename=fromtablename)
        else:
            insert = """INSERT INTO {schema}.{tablename} ({fields}) SELECT {fromfields} FROM 
                    {schema}.{fromtablename} WHERE {where};""" \
                    .format(schema=schema, tablename=tablename, fields=fields, fromfields=fromfields,
                            fromtablename=fromtablename, where=where)
        cur.execute(insert)
        self.conn.commit()

    def table_update1(self, schema, tablename, expression, where):
        # update with same values for all rows
        cur = self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        update = """UPDATE {schema}.{tablename} SET {expression} WHERE {where};"""\
                 .format(schema=schema, tablename=tablename, expression=expression, where=where)
        cur.execute(update)
        self.conn.commit()

    def table_update2(self, schema, tablename, updatefields, idfield, valuefields, values):
        # update with multiple values
        expr = ""
        for field in updatefields:
            if len(expr) > 0:
                expr = expr + ", "
            expr = expr + field + " = data." + field
        cur = self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        update = """UPDATE {schema}.{tablename} SET {expr} FROM (VALUES %s) as data ({valuefields}) WHERE 
                {schema}.{tablename}.{idfield} = data.{idfield};"""\
                .format(schema=schema, tablename=tablename, expr=expr, valuefields=valuefields, idfield=idfield)
        psycopg2.extras.execute_values(cur, update, values)
        self.conn.commit()

    def table_update_fromtable(self, schema, updatetablename, expression, fromtablename, where):
        # update with values from another table
        cur = self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        update = """UPDATE {schema}.{updatetablename} SET {expression} FROM {schema}.{fromtablename} WHERE {where};""" \
                 .format(schema=schema, updatetablename=updatetablename, expression=expression,
                         fromtablename=fromtablename, where=where)
        cur.execute(update)
        self.conn.commit()

    def point_event_class_create(self, schema, event_class_name, srid):
        cur = self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        tablename = event_class_name
        create = """CREATE TABLE {schema}.{tablename}(id SERIAL PRIMARY KEY, uuid UUID NOT NULL, 
                    geom geometry(Point,{srid}), name VARCHAR(100) UNIQUE NOT NULL, createtstz TIMESTAMPTZ NOT NULL, 
                    changetstz TIMESTAMPTZ NOT NULL, geomtstz TIMESTAMPTZ);"""\
                    .format(schema=schema, tablename=tablename, srid=srid)
        cur.execute(create)
        idx = """CREATE INDEX IF NOT EXISTS idx_{tablename}_uuid ON {schema}.{tablename}
                 USING btree (uuid)""".format(schema=schema, tablename=tablename)
        cur.execute(idx)
        idx = """CREATE INDEX IF NOT EXISTS idx_{tablename}_geom ON {schema}.{tablename}
                 USING gist (geom)""".format(schema=schema, tablename=tablename)
        cur.execute(idx)
        comment = """COMMENT ON TABLE {schema}.{tablename} IS 'LRS-Editor, Point Name Table';"""\
                  .format(schema=schema, tablename=tablename)
        cur.execute(comment)
        self.conn.commit()
        tablename = event_class_name + "_bp"
        create = """CREATE TABLE {schema}.{tablename}(id SERIAL PRIMARY KEY, uuid UUID NOT NULL, 
                    geom geometry(Point,{srid}) NOT NULL, event_id UUID NOT NULL, azi DOUBLE PRECISION NOT NULL, 
                    route_id UUID NOT NULL, meas DOUBLE PRECISION NOT NULL, apprtstz TIMESTAMPTZ NOT NULL, 
                    createtstz TIMESTAMPTZ NOT NULL, changetstz TIMESTAMPTZ NOT NULL, 
                    geomtstz TIMESTAMPTZ NOT NULL);"""\
                    .format(schema=schema, tablename=tablename, srid=srid)
        cur.execute(create)
        idx = """CREATE INDEX IF NOT EXISTS idx_{tablename}_event_id ON {schema}.{tablename}
                 USING btree (event_id)""".format(schema=schema, tablename=tablename)
        cur.execute(idx)
        idx = """CREATE INDEX IF NOT EXISTS idx_{tablename}_route_id ON {schema}.{tablename}
                 USING btree (route_id)""".format(schema=schema, tablename=tablename)
        cur.execute(idx)
        idx = """CREATE INDEX IF NOT EXISTS idx_{tablename}_geom ON {schema}.{tablename}
                 USING gist (geom)""".format(schema=schema, tablename=tablename)
        cur.execute(idx)
        comment = """COMMENT ON TABLE {schema}.{tablename} IS 'LRS-Editor, Base Point Event Table';"""\
                  .format(schema=schema, tablename=tablename)
        cur.execute(comment)
        self.conn.commit()

    def cont_event_class_create(self, schema, event_class_name, srid):
        cur = self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        tablename = event_class_name
        create = """CREATE TABLE {schema}.{tablename}(id SERIAL PRIMARY KEY, uuid UUID NOT NULL, 
                    geom geometry(Point,{srid}) NOT NULL, event_id UUID NOT NULL, azi DOUBLE PRECISION NOT NULL, 
                    route_id UUID NOT NULL, frommeas DOUBLE PRECISION NOT NULL, tomeas DOUBLE PRECISION NOT NULL,
                    apprtstz TIMESTAMPTZ NOT NULL, createtstz TIMESTAMPTZ NOT NULL,
                    changetstz TIMESTAMPTZ NOT NULL, geomtstz TIMESTAMPTZ NOT NULL);"""\
                    .format(schema=schema, tablename=tablename, srid=srid)
        cur.execute(create)
        idx = """CREATE INDEX IF NOT EXISTS idx_{tablename}_event_id ON {schema}.{tablename}
                 USING btree (event_id)""".format(schema=schema, tablename=tablename)
        cur.execute(idx)
        idx = """CREATE INDEX IF NOT EXISTS idx_{tablename}_route_id ON {schema}.{tablename}
                 USING btree (route_id)""".format(schema=schema, tablename=tablename)
        cur.execute(idx)
        idx = """CREATE INDEX IF NOT EXISTS idx_{tablename}_geom ON {schema}.{tablename}
                 USING gist (geom)""".format(schema=schema, tablename=tablename)
        cur.execute(idx)
        comment = """COMMENT ON TABLE {schema}.{tablename} IS 'LRS-Editor, Continuous Event Table';""" \
                  .format(schema=schema, tablename=tablename)
        cur.execute(comment)
        self.conn.commit()

        table_et_name = event_class_name + "_et"
        create = """CREATE TABLE {schema}.{table_et_name}(id SERIAL PRIMARY KEY, uuid UUID NOT NULL, 
                    name VARCHAR(100) UNIQUE NOT NULL, createtstz TIMESTAMPTZ NOT NULL, 
                    changetstz TIMESTAMPTZ NOT NULL);"""\
                    .format(schema=schema, table_et_name=table_et_name)
        cur.execute(create)
        idx = """CREATE INDEX IF NOT EXISTS idx_{table_et_name}_uuid ON {schema}.{table_et_name}
                 USING btree (uuid)""".format(schema=schema, table_et_name=table_et_name)
        cur.execute(idx)
        comment = """COMMENT ON TABLE {schema}.{table_et_name} IS 'LRS-Editor, Continuous Name Table';""" \
                  .format(schema=schema, table_et_name=table_et_name)
        cur.execute(comment)
        self.conn.commit()

    def cont_event_view_create(self, schema, event_class_name, route_class_name, srid):
        cur = self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        exclude_fieldname = ["id", "geom", "uuid", "name", "createtstz", "changetstz", "geomtstz", "event_id", "azi",
                             "route_id", "frommeas", "tomeas", "apprtstz"]
        fields = self.fieldnames_get(schema, event_class_name)
        user_fields = ""
        for field in fields:
            fieldname = field[0]
            if fieldname not in exclude_fieldname:
                user_fields = ''.join((user_fields, ", ", fieldname))

        viewname = "v_" + event_class_name
        table_et_name = event_class_name + "_et"
        create = """CREATE or REPLACE VIEW {schema}.{viewname} as SELECT 
                    a.id,
                    a.uuid,
                    a.frommeas,
                    a.tomeas, 
                    ST_LocateBetween(ST_AddMeasure(
                    ST_Collect(rc.geom ORDER BY rc.sortnr ASC), 0, 
                    ST_Length(ST_Collect(rc.geom ORDER BY rc.sortnr ASC))), 
                    a.frommeas, a.tomeas)::geometry(MultiLineStringM,{srid}) as geom,
                    a.event_id,
                    a.createtstz,
                    a.changetstz,
                    a.geomtstz,
                    a.apprtstz,
                    b.name as event_name,
                    rc.name as route_name
                    {user_fields}
                    FROM {schema}.{event_class_name} a 
                    LEFT JOIN {schema}.{route_class_name} rc ON a.route_id = rc.route_id 
                    LEFT JOIN {schema}.{table_et_name} b ON a.event_id = b.uuid 
                    GROUP BY a.id, b.name, rc.name;""" \
                    .format(schema=schema, viewname=viewname, srid=srid, event_class_name=event_class_name,
                            user_fields=user_fields, route_class_name=route_class_name, table_et_name=table_et_name)
        cur.execute(create)
        comment = """COMMENT ON VIEW {schema}.{viewname} IS 'LRS-Editor, Continuous Event View';""" \
                  .format(schema=schema, viewname=viewname)
        cur.execute(comment)
        self.conn.commit()

    def tour_event_class_create(self, schema, event_class_name, srid):
        cur = self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        tablename = event_class_name
        create = """CREATE TABLE {schema}.{tablename}(id SERIAL PRIMARY KEY, uuid UUID NOT NULL,   
                    geom geometry(Point,{srid}) NOT NULL, azi DOUBLE PRECISION NOT NULL, 
                    apprtstz TIMESTAMPTZ NOT NULL, createtstz TIMESTAMPTZ NOT NULL, 
                    changetstz TIMESTAMPTZ NOT NULL, geomtstz TIMESTAMPTZ NOT NULL);""" \
                    .format(schema=schema, tablename=tablename, srid=srid)
        cur.execute(create)
        idx = """CREATE INDEX IF NOT EXISTS idx_{tablename}_uuid ON {schema}.{tablename}
                 USING btree (uuid)""".format(schema=schema, tablename=tablename)
        cur.execute(idx)
        idx = """CREATE INDEX IF NOT EXISTS idx_{tablename}_geom ON {schema}.{tablename}
                 USING gist (geom)""".format(schema=schema, tablename=tablename)
        cur.execute(idx)
        comment = """COMMENT ON TABLE {schema}.{tablename} IS 'LRS-Editor, Tour Event Table';""" \
                  .format(schema=schema, tablename=tablename)
        cur.execute(comment)
        self.conn.commit()

        table_mt_name = event_class_name + "_mt"
        create = """CREATE TABLE {schema}.{table_mt_name}(id SERIAL PRIMARY KEY, uuid UUID NOT NULL, 
                    event_id UUID NOT NULL, route_id UUID NOT NULL, sortnr INTEGER NOT NULL, 
                    frommeas DOUBLE PRECISION NOT NULL, tomeas DOUBLE PRECISION NOT NULL, 
                    frompoint_id UUID NOT NULL, topoint_id UUID NOT NULL, routedir BOOLEAN NOT NULL);""" \
                    .format(schema=schema, table_mt_name=table_mt_name)
        cur.execute(create)
        idx = """CREATE INDEX IF NOT EXISTS idx_{table_mt_name}_event_id ON {schema}.{table_mt_name}
                 USING btree (event_id)""".format(schema=schema, table_mt_name=table_mt_name)
        cur.execute(idx)
        idx = """CREATE INDEX IF NOT EXISTS idx_{table_mt_name}_route_id ON {schema}.{table_mt_name}
                 USING btree (route_id)""".format(schema=schema, table_mt_name=table_mt_name)
        cur.execute(idx)
        idx = """CREATE INDEX IF NOT EXISTS idx_{table_mt_name}_frompoint_id ON {schema}.{table_mt_name}
                 USING btree (frompoint_id)""".format(schema=schema, table_mt_name=table_mt_name)
        cur.execute(idx)
        idx = """CREATE INDEX IF NOT EXISTS idx_{table_mt_name}_topoint_id ON {schema}.{table_mt_name}
                 USING btree (topoint_id)""".format(schema=schema, table_mt_name=table_mt_name)
        cur.execute(idx)
        comment = """COMMENT ON TABLE {schema}.{table_mt_name} IS 'LRS-Editor, Tour Measure Table';""" \
                  .format(schema=schema, table_mt_name=table_mt_name)
        cur.execute(comment)
        self.conn.commit()

        table_et_name = event_class_name + "_et"
        create = """CREATE TABLE {schema}.{table_et_name}(id SERIAL PRIMARY KEY, uuid UUID NOT NULL, 
                    name VARCHAR(100) UNIQUE NOT NULL, createtstz TIMESTAMPTZ NOT NULL, 
                    changetstz TIMESTAMPTZ NOT NULL);""" \
                    .format(schema=schema, table_et_name=table_et_name)
        cur.execute(create)
        idx = """CREATE INDEX IF NOT EXISTS idx_{table_et_name}_uuid ON {schema}.{table_et_name}
                 USING btree (uuid)""".format(schema=schema, table_et_name=table_et_name)
        cur.execute(idx)
        comment = """COMMENT ON TABLE {schema}.{table_et_name} IS 'LRS-Editor, Tour Name Table';""" \
                  .format(schema=schema, table_et_name=table_et_name)
        cur.execute(comment)
        self.conn.commit()

    def tour_event_view_create(self, schema, event_class_name, route_class_name, srid):
        cur = self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        exclude_fieldname = ["id", "geom", "uuid", "name", "createtstz", "changetstz", "geomtstz", "event_id", "azi",
                             "route_id", "sortnr", "frommeas", "tomeas", "frompoint_id", "topoint_id", "routedir",
                             "apprtstz"]
        table_mt_name = event_class_name + "_mt"
        fields = self.fieldnames_get(schema, table_mt_name)
        user_fields = ""
        for field in fields:
            fieldname = field[0]
            if fieldname not in exclude_fieldname:
                user_fields = ''.join((user_fields, ", ", fieldname))

        viewname = "v_" + event_class_name
        table_et_name = event_class_name + "_et"
        create = """CREATE or REPLACE VIEW {schema}.{viewname} as SELECT 
                    a.id, 
                    a.uuid,
                    a.routedir,
                    a.sortnr,
                    a.frommeas,
                    a.tomeas,
                    CASE WHEN routedir THEN 
                    ST_LocateBetween(ST_AddMeasure(
                    ST_Collect(rc.geom ORDER BY rc.sortnr ASC), 0, 
                    ST_Length(ST_Collect(rc.geom ORDER BY rc.sortnr ASC))), 
                    a.frommeas, a.tomeas)::geometry(MultiLineStringM,{srid})
                    ELSE
                    ST_Reverse(
                    ST_LocateBetween(ST_AddMeasure(
                    ST_Collect(rc.geom ORDER BY rc.sortnr ASC), 0, 
                    ST_Length(ST_Collect(rc.geom ORDER BY rc.sortnr ASC))), 
                    a.frommeas, a.tomeas))::geometry(MultiLineStringM,{srid})
                    END as geom,
                    a.event_id,
                    b.name as event_name,
                    rc.name as route_name
                    {user_fields}
                    FROM {schema}.{table_mt_name} a 
                    LEFT JOIN {schema}.{route_class_name} rc ON a.route_id = rc.route_id 
                    LEFT JOIN {schema}.{table_et_name} b ON a.event_id = b.uuid 
                    GROUP BY a.id, b.name, rc.name;""" \
                    .format(schema=schema, viewname=viewname, srid=srid, table_mt_name=table_mt_name,
                            user_fields=user_fields, route_class_name=route_class_name, table_et_name=table_et_name)
        cur.execute(create)
        comment = """COMMENT ON VIEW {schema}.{viewname} IS 'LRS-Editor, Tour Event View';""" \
                  .format(schema=schema, viewname=viewname)
        cur.execute(comment)
        self.conn.commit()

    def point_event_class_delete(self, schema, event_class_name):
        cur = self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        tablename_list = [event_class_name, event_class_name + "_bp"]
        for tablename in tablename_list:
            drop = """DROP TABLE IF EXISTS {schema}.{tablename};"""\
                    .format(schema=schema, tablename=tablename)
            cur.execute(drop)
            self.conn.commit()

    def cont_event_class_delete(self, schema, event_class_name):
        cur = self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        # drop tables with view (-> CASCADE)
        tablename_list = [event_class_name, event_class_name + "_et"]
        for tablename in tablename_list:
            drop = """DROP TABLE IF EXISTS {schema}.{tablename} CASCADE;"""\
                    .format(schema=schema, tablename=tablename)
            cur.execute(drop)
            self.conn.commit()

    def tour_event_class_delete(self, schema, event_class_name):
        cur = self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        # drop tables with view (-> CASCADE)
        tablename_list = [event_class_name, event_class_name + "_et", event_class_name + "_mt"]
        for tablename in tablename_list:
            drop = """DROP TABLE IF EXISTS {schema}.{tablename} CASCADE;""" \
                .format(schema=schema, tablename=tablename)
            cur.execute(drop)
            self.conn.commit()

    def linestring_nodes_get(self, schema, tablename, geomfield, fields, where, order=None):
        cur = self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        if not order:
            query = """SELECT 
                    ST_X(ST_StartPoint({geomfield})) as SX,
                    ST_Y(ST_StartPoint({geomfield})) as SY,
                    ST_X(ST_EndPoint({geomfield})) as EX,
                    ST_Y(ST_EndPoint({geomfield})) as EY, 
                    {fields} 
                    FROM {schema}.{tablename} WHERE {where};""" \
                    .format(fields=fields, geomfield=geomfield, schema=schema, tablename=tablename, where=where)
        else:
            query = """SELECT 
                    ST_X(ST_StartPoint({geomfield})) as SX,
                    ST_Y(ST_StartPoint({geomfield})) as SY,
                    ST_X(ST_EndPoint({geomfield})) as EX,
                    ST_Y(ST_EndPoint({geomfield})) as EY, 
                    {fields} 
                    FROM {schema}.{tablename} WHERE {where} ORDER BY {order};""" \
                    .format(fields=fields, geomfield=geomfield, schema=schema, tablename=tablename, where=where,
                            order=order)

        cur.execute(query)
        rows_list = cur.fetchall()
        return rows_list

    def linestrings_nodes_get(self, schema, tablename, geomfield, fields=None):
        cur = self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        if not fields:
            query = """SELECT 'S' as KIND, ST_X(ST_StartPoint({geomfield})) as X,
                    ST_Y(ST_StartPoint({geomfield})) as Y FROM {schema}.{tablename}
                    UNION ALL
                    SELECT 'E' as KIND, ST_X(ST_EndPoint({geomfield})) as X,
                    ST_Y(ST_EndPoint({geomfield})) as Y FROM {schema}.{tablename}
                    ;"""\
                    .format(geomfield=geomfield, schema=schema, tablename=tablename)
        else:
            query = """SELECT {fields}, 'S' as KIND, ST_X(ST_StartPoint({geomfield})) as X,
                    ST_Y(ST_StartPoint({geomfield})) as Y FROM {schema}.{tablename}
                    UNION ALL
                    SELECT {fields}, 'E' as KIND, ST_X(ST_EndPoint({geomfield})) as X,
                    ST_Y(ST_EndPoint({geomfield})) as Y FROM {schema}.{tablename}
                    ;"""\
                    .format(fields=fields, geomfield=geomfield, schema=schema, tablename=tablename)
        cur.execute(query)
        rows_list = cur.fetchall()
        return rows_list

    def linestring_loop_rep1(self, schema, srid):
        cur = self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        lrs_tmp1 = EXCLUDE_TABLENAME[4]
        if not self.table_exists(schema, lrs_tmp1):
            create = """CREATE TABLE {schema}.{lrs_tmp1}(id SERIAL PRIMARY KEY,
                        geom geometry(LineString,{srid}) NOT NULL, name VARCHAR(100) NOT NULL, 
                        baseclass_id INTEGER NOT NULL);""" \
                .format(schema=schema, lrs_tmp1=lrs_tmp1, srid=srid)
            cur.execute(create)
            comment = """COMMENT ON TABLE {schema}.{lrs_tmp1} IS 'LRS-Editor, Tmp-Class1';""" \
                .format(schema=schema, lrs_tmp1=lrs_tmp1)
            cur.execute(comment)
            self.conn.commit()

    def linestring_loop_rep2(self, schema, route_id, lrs_id, srid):
        cur = self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        lrs_tmp1 = EXCLUDE_TABLENAME[4]
        lrs_rc_name = EXCLUDE_TABLENAME[3]

        # to create correct loops: remove first point, collect/merge linestrings and insert first point again
        # get first point of linestring with min id
        query = """SELECT ST_AsText(ST_StartPoint(geom)) FROM {schema}.{lrs_tmp1} 
                   WHERE baseclass_id = (SELECT MIN(baseclass_id) FROM {schema}.{lrs_tmp1}  
                   WHERE name = '{route_id}');"""\
                   .format(schema=schema, lrs_tmp1=lrs_tmp1, route_id=route_id)
        cur.execute(query)
        startpoint = cur.fetchall()[0][0]

        # remove first point of linestring with min id
        update1 = """UPDATE {schema}.{lrs_tmp1} SET geom = ST_RemovePoint(geom, 0) 
                   WHERE baseclass_id = (SELECT MIN(baseclass_id) FROM {schema}.{lrs_tmp1}  
                   WHERE name = '{route_id}');""" \
                   .format(schema=schema, lrs_tmp1=lrs_tmp1, route_id=route_id)
        cur.execute(update1)
        self.conn.commit()

        # collect and merge linestrings, considering direction by order of id
        update2 = """UPDATE {schema}.{lrs_rc_name} SET geom = subquery.new_geom 
                     FROM (SELECT ST_LineMerge(ST_Collect(b.geom ORDER BY b.baseclass_id ASC)) as new_geom
                     FROM {schema}.{lrs_tmp1} b WHERE b.name = '{route_id}') as subquery
                     WHERE id = {lrs_id};""" \
                     .format(schema=schema, lrs_rc_name=lrs_rc_name, lrs_tmp1=lrs_tmp1, route_id=route_id,
                             lrs_id=lrs_id)
        cur.execute(update2)
        self.conn.commit()

        # insert startpoint to complete loop
        update3 = """UPDATE {schema}.{lrs_rc_name} SET geom = ST_AddPoint(geom, ST_GeomFromText('{startpoint}', 
                    {srid}), 0) WHERE id = {lrs_id};""" \
                     .format(schema=schema, lrs_rc_name=lrs_rc_name, startpoint=startpoint, srid=srid, lrs_id=lrs_id)
        cur.execute(update3)
        self.conn.commit()

    def linestring_loop_rep3(self, schema):
        cur = self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        lrs_tmp1 = EXCLUDE_TABLENAME[4]
        drop = """DROP TABLE IF EXISTS {schema}.{lrs_tmp1} CASCADE;""" \
               .format(schema=schema, lrs_tmp1=lrs_tmp1)
        cur.execute(drop)
        self.conn.commit()

    def linestring_reverse(self, schema, tablename, geomfield, where):
        cur = self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        update = """UPDATE {schema}.{tablename} SET {geomfield} = ST_Reverse({geomfield}) WHERE {where};""" \
                 .format(schema=schema, tablename=tablename, geomfield=geomfield, where=where)
        cur.execute(update)
        self.conn.commit()

    def linestring_closed(self, schema, geomfield, route_id, pathnr):
        cur = self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        lrs_rc_name = EXCLUDE_TABLENAME[3]
        query = """SELECT name, ST_IsClosed({geomfield}), id FROM {schema}.{lrs_rc_name} 
                WHERE name = '{route_id}' AND pathnr = {pathnr};"""\
                .format(schema=schema, lrs_rc_name=lrs_rc_name, geomfield=geomfield, route_id=route_id, pathnr=pathnr)
        cur.execute(query)
        rows_list = cur.fetchall()
        return rows_list

    def point_equals(self, schema, tablename, geomfield, route_id_field, sortnr_field):
        cur = self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        query = """SELECT TRIM(BOTH FROM a.{route_id_field}), a.{sortnr_field} 
                FROM {schema}.{tablename} a, {schema}.{tablename} b
                WHERE ST_Equals(a.{geomfield}, b.{geomfield}) AND
                a.id <> b.id AND a.{route_id_field} = b.{route_id_field} AND a.{sortnr_field} = b.{sortnr_field} 
                GROUP BY a.{route_id_field}, a.{sortnr_field};"""\
                .format(schema=schema, tablename=tablename, geomfield=geomfield, route_id_field=route_id_field,
                        sortnr_field=sortnr_field)
        cur.execute(query)
        rows_list = cur.fetchall()
        return rows_list

    def linestring_compare(self, schema, tablename, geomfield):
        # st_equals and st_orderingequals
        cur = self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        lrs_rc_name = EXCLUDE_TABLENAME[3]
        query = """SELECT a.name, 
                ST_Equals(ST_LineMerge(ST_Collect(a.geom ORDER BY a.name ASC, a.pathnr ASC)),  
                ST_LineMerge(ST_Collect(b.{geomfield} ORDER BY b.name ASC, b.sortnr ASC))),  
                ST_OrderingEquals(ST_LineMerge(ST_Collect(a.geom ORDER BY a.name ASC, a.pathnr ASC)),  
                ST_LineMerge(ST_Collect(b.{geomfield} ORDER BY b.name ASC, b.sortnr ASC)))                 
                FROM {schema}.{lrs_rc_name} a LEFT JOIN {schema}.{tablename} b ON a.name = b.name 
                WHERE a.valid = 1 GROUP BY a.name;""" \
                .format(schema=schema, tablename=tablename, geomfield=geomfield, lrs_rc_name=lrs_rc_name)
        # returns boolean value
        cur.execute(query)
        rows_list = cur.fetchall()
        return rows_list

    def point_within1(self, schema, tablename_a, tablename_b, fields, a_geomfield, b_geomfield,
                      tolerance, a_id_field, b_id_field, group):
        cur = self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        query = """SELECT {fields}, ST_DWithin(a.{a_geomfield}, ST_LineMerge(ST_Collect(b.{b_geomfield} 
                ORDER BY b.name ASC, b.sortnr ASC)), {tolerance}) FROM {schema}.{tablename_a} a, 
                {schema}.{tablename_b} b WHERE a.{a_id_field} = b.{b_id_field} GROUP BY {group};""" \
                .format(schema=schema, tablename_a=tablename_a, tablename_b=tablename_b, fields=fields,
                        a_geomfield=a_geomfield, b_geomfield=b_geomfield, tolerance=tolerance, a_id_field=a_id_field,
                        b_id_field=b_id_field, group=group)

        # ST_DWithin returns boolean value
        cur.execute(query)
        rows_list = cur.fetchall()
        return rows_list

    def point_within2(self, schema, tablename_a, tablename_b, tablename_c, fields, b_geomfield, c_geomfield,
                      tolerance, where, group):
        cur = self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        query = """SELECT {fields}, ST_DWithin(b.{b_geomfield}, ST_LineMerge(ST_Collect(c.{c_geomfield} 
                ORDER BY c.name ASC, c.sortnr ASC)), {tolerance}) FROM {schema}.{tablename_a} a, 
                {schema}.{tablename_b} b, {schema}.{tablename_c} c 
                WHERE {where} GROUP BY {group};""" \
                .format(schema=schema, tablename_a=tablename_a, tablename_b=tablename_b, tablename_c=tablename_c,
                        fields=fields, b_geomfield=b_geomfield, c_geomfield=c_geomfield, tolerance=tolerance,
                        where=where, group=group)
        # ST_DWithin returns boolean value
        cur.execute(query)
        rows_list = cur.fetchall()
        return rows_list

    def point_class_create(self, schema, tablename, nodelist, srid):
        cur = self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        create = """CREATE TABLE {schema}.{tablename}(id SERIAL PRIMARY KEY, geom geometry(Point,{srid}) NOT NULL,                        
                    pointtype VARCHAR(100) NOT NULL);""" \
                    .format(schema=schema, tablename=tablename, srid=srid)
        cur.execute(create)
        self.conn.commit()

        for row in nodelist:
            insert = """INSERT INTO {schema}.{tablename} (geom, pointtype) VALUES 
                        (ST_SetSRID(ST_MakePoint({x}, {y}), {srid}), '{type}');""" \
                        .format(schema=schema, tablename=tablename, x=row[1], y=row[2], srid=srid, type=row[0])
            cur.execute(insert)
            self.conn.commit()

    def table_route_class_create(self, schema, tablename, srid):
        cur = self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        create = """CREATE TABLE {schema}.{tablename}(id SERIAL PRIMARY KEY, geom geometry(LineString,{srid}) NOT NULL,
                    sortnr INTEGER NOT NULL, route_id UUID NOT NULL, name VARCHAR(100) NOT NULL,
                    basesystem_id INTEGER NOT NULL, createtstz TIMESTAMPTZ NOT NULL, changetstz TIMESTAMPTZ NOT NULL, 
                    geomtstz TIMESTAMPTZ NOT NULL, length DOUBLE PRECISION);""" \
                    .format(schema=schema, tablename=tablename, srid=srid)
        cur.execute(create)
        idx = """CREATE INDEX IF NOT EXISTS idx_{tablename}_route_id ON {schema}.{tablename}
                 USING btree (route_id)""".format(schema=schema, tablename=tablename)
        cur.execute(idx)
        idx = """CREATE INDEX IF NOT EXISTS idx_{tablename}_geom ON {schema}.{tablename}
                 USING gist (geom)""".format(schema=schema, tablename=tablename)
        cur.execute(idx)
        comment = """COMMENT ON TABLE {schema}.{tablename} IS 'LRS-Editor, Route Class Table';""" \
                  .format(schema=schema, tablename=tablename)
        cur.execute(comment)
        self.conn.commit()

    def table_lrs_route_class_create(self, schema, srid):
        cur = self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        lrs_rc_name = EXCLUDE_TABLENAME[3]
        if not self.table_exists(schema, lrs_rc_name):
            create = """CREATE TABLE {schema}.{lrs_rc_name}(id SERIAL PRIMARY KEY,
                        geom geometry(LineString,{srid}) NOT NULL, name VARCHAR(100) NOT NULL, 
                        pathnr INTEGER DEFAULT 1, valid INTEGER DEFAULT 1);""" \
                        .format(schema=schema, lrs_rc_name=lrs_rc_name, srid=srid)
            cur.execute(create)
            idx = """CREATE INDEX IF NOT EXISTS idx_{lrs_rc_name}_geom ON {schema}.{lrs_rc_name}
                     USING gist (geom)""".format(schema=schema, lrs_rc_name=lrs_rc_name)
            cur.execute(idx)
            comment = """COMMENT ON TABLE {schema}.{lrs_rc_name} IS 'LRS-Editor, Route Class System Table';""" \
                .format(schema=schema, lrs_rc_name=lrs_rc_name)
            cur.execute(comment)
            self.conn.commit()
        else:
            # truncate table, reset sequences
            trunc = """TRUNCATE {schema}.{lrs_rc_name} RESTART IDENTITY;""" \
                    .format(schema=schema, lrs_rc_name=lrs_rc_name)
            cur.execute(trunc)
            self.conn.commit()

    def lrs_route_class_insert(self, schema, tablename, idfield, geomfield):
        cur = self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        lrs_rc_name = EXCLUDE_TABLENAME[3]
        insert = """INSERT INTO {schema}.{lrs_rc_name} (geom, name, pathnr) SELECT 
                    (ST_Dump(ST_LineMerge(new_geom))).geom, TRIM(BOTH FROM idfield), 
                    (ST_Dump(ST_LineMerge(new_geom))).path[1] FROM
                    (SELECT e.{idfield} as idfield, ST_Collect(e.{geomfield}) as new_geom FROM
                    {schema}.{tablename} e GROUP BY e.{idfield}) as subquery;""" \
            .format(schema=schema, lrs_rc_name=lrs_rc_name, tablename=tablename, geomfield=geomfield, idfield=idfield)
        cur.execute(insert)
        self.conn.commit()

        expression = "pathnr = DEFAULT"
        where = "pathnr IS NULL"
        self.table_update1(schema, lrs_rc_name, expression, where)

    def base_class_geom_select(self, schema, tablename, idfield, geomfield):
        cur = self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        lrs_rc_name = EXCLUDE_TABLENAME[3]
        query = """SELECT (ST_Dump(ST_LineMerge(new_geom))).geom, TRIM(BOTH FROM idfield), 
                   (ST_Dump(ST_LineMerge(new_geom))).path[1] FROM 
                   (SELECT e.{idfield} as idfield, ST_Collect(e.{geomfield}) as new_geom FROM
                   {schema}.{tablename} e GROUP BY e.{idfield}) as subquery;""" \
                    .format(schema=schema, lrs_rc_name=lrs_rc_name, tablename=tablename, geomfield=geomfield,
                            idfield=idfield)
        cur.execute(query)
        rows_list = cur.fetchall()
        return rows_list

    def max_number_get(self, schema, tablename, field, where=None):
        cur = self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        if not where:
            query = """SELECT {field} FROM {schema}.{tablename} ORDER BY {field} DESC LIMIT 1;""" \
                    .format(field=field, schema=schema, tablename=tablename)
        else:
            query = """SELECT {field} FROM {schema}.{tablename} WHERE {where} ORDER BY {field} DESC LIMIT 1;""" \
                    .format(field=field, schema=schema, tablename=tablename, where=where)

        cur.execute(query)
        # returns just a single row -> add to variable before cursor throws result away, when calling fetchone twice
        result = cur.fetchone()
        if result is not None:
            return result[0]
        else:
            return 0

    def linestring_length_get(self, schema, tablename, route_id, sortnr, geomfield):
        cur = self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        query = """SELECT ST_Length({geomfield}) FROM {schema}.{tablename} WHERE 
                    route_id = '{route_id}' AND sortnr = {sortnr};"""\
                .format(geomfield=geomfield, schema=schema, tablename=tablename, route_id=route_id, sortnr=sortnr)
        cur.execute(query)
        result = cur.fetchone()
        if result is not None:
            return result[0]
        else:
            return 0

    def linestring_length_update(self, schema, tablename, geomfield, field):
        cur = self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        update = """UPDATE {schema}.{tablename} SET {field} = ST_Length({geomfield});"""\
                 .format(geomfield=geomfield, schema=schema, tablename=tablename, field=field)
        cur.execute(update)
        self.conn.commit()

    def linestring_dist_get(self, schema, tablename, route_id, sortnr, x, y, geomfield, srid):
        # must be LineString
        cur = self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        query = """SELECT ST_LineLocatePoint(a.{geomfield}, ST_SetSRID(ST_MakePoint({x}, {y}), {srid})) FROM 
                    {schema}.{tablename} a WHERE route_id = '{route_id}' AND sortnr = {sortnr};"""\
                .format(geomfield=geomfield, schema=schema, tablename=tablename, route_id=route_id, sortnr=sortnr,
                        x=x, y=y, srid=srid)
        cur.execute(query)
        result = cur.fetchone()
        if result is not None:
            return result[0]
        else:
            return 0

    def linestring_point_get(self, schema, tablename, route_id, sortnr, fract, geomfield):
        # must be LineString, returns OGC Well-Known text representation (WKT)
        cur = self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        query = """SELECT ST_AsText(ST_LineInterpolatePoint(a.{geomfield}, {fract})) FROM 
                    {schema}.{tablename} a WHERE route_id = '{route_id}' AND sortnr = {sortnr};"""\
                .format(geomfield=geomfield, schema=schema, tablename=tablename, route_id=route_id, sortnr=sortnr,
                        fract=fract)
        cur.execute(query)
        # must return a point, not a list
        result = cur.fetchone()[0]
        return result

    def linestring_azi_get(self, pg_point1, pg_point2):
        # pg_point1: first point along the directed route (minor value of meas)
        # points must be OGC Well-Known text representation (WKT)
        cur = self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        query = """SELECT degrees(ST_Azimuth(ST_GeomFromText('{pg_point1}'), ST_GeomFromText('{pg_point2}')));"""\
                .format(pg_point1=pg_point1, pg_point2=pg_point2)
        cur.execute(query)
        # must return a value, not a list
        result = cur.fetchone()[0]
        return result

    def linestring_sortnr_get(self, schema, tablename, route_id, x, y, geomfield, srid):
        # get sortnr of closest LineString from a point, with given route_id
        cur = self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        query = """SELECT sortnr FROM {schema}.{tablename} a WHERE route_id = '{route_id}' ORDER BY  
                    ST_Distance(ST_SetSRID(ST_MakePoint({x}, {y}), {srid}), a.{geomfield}) ASC LIMIT 1;"""\
                .format(geomfield=geomfield, schema=schema, tablename=tablename, route_id=route_id, x=x, y=y, srid=srid)
        cur.execute(query)
        # must return a value, not a list
        result = cur.fetchone()[0]
        return result
