# Copyright (c) 2020-2022 CRS4
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import logging
import os

import psycopg2 as psy
import psycopg2.sql as sql
import psycopg2.errors as errors
from flask import current_app
from flask_sqlalchemy import SQLAlchemy
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

# set module level logger
logger = logging.getLogger(__name__)

# set DB instance
db = SQLAlchemy()


def get_db_connection_param(name, settings=None):
    if settings and name in settings:
        return settings.get(name)
    if current_app and name in current_app.config:
        return current_app.config[name]
    return os.environ.get(name, None)


def db_connection_params(settings=None):
    return {
        'host': get_db_connection_param("POSTGRESQL_HOST", settings),
        'port': get_db_connection_param("POSTGRESQL_PORT", settings),
        'user': get_db_connection_param("POSTGRESQL_USERNAME", settings),
        'password': get_db_connection_param("POSTGRESQL_PASSWORD", settings),
        'dbname': get_db_connection_param("POSTGRESQL_DATABASE", settings)
    }


def db_uri(settings=None, override_db_name=None):
    """
    Build URI to connect to the DataBase
    :return:
    """
    # "postgresql:///{0}/app-dev.db".format(basedir)
    uri = get_db_connection_param('DATABASE_URI', settings)
    if uri is None:
        conn_params = db_connection_params(settings)
        uri = "postgresql://{user}:{passwd}@{host}:{port}/{dbname}".format(
            user=conn_params['user'],
            passwd=conn_params['password'],
            host=conn_params['host'],
            port=conn_params['port'],
            dbname=override_db_name or conn_params['dbname'])
    return uri


def db_connect(settings=None, override_db_name=None):
    conn_params = db_connection_params(settings)

    actual_db_name = override_db_name if override_db_name else conn_params['dbname']
    con = psy.connect(
        host=conn_params.get('host'),
        port=conn_params.get('port'),
        user=conn_params['user'],
        password=conn_params['password'],
        dbname=actual_db_name)
    logger.debug("Connected to database '%s'", actual_db_name)
    return con


def db_exists(db_name=None, settings=None):
    actual_db_name = db_name or get_db_connection_param("POSTGRESQL_DATABASE", settings)
    for dbname in (actual_db_name, 'postgres', 'template1', 'template0', None):
        try:
            conn = db_connect(settings=settings, override_db_name=actual_db_name)
            cursor = conn.cursor()
            cursor.execute(f"SELECT 1 FROM pg_database WHERE datname='{dbname}'")
            if cursor.fetchone():
                return True
        except errors.OperationalError:
            return False


def db_initialized(db_name=None, settings=None):
    return db_exists(settings=settings, db_name=db_name) and \
        db_table_exists('user', settings=settings, db_name=db_name)


def db_revision(db_name=None, settings=None):
    logger.debug("Getting DB revision...")
    try:
        conn = db_connect(settings=settings, override_db_name=db_name)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM alembic_version")
        row = cursor.fetchone()
        return row[0] if row else None
    except errors.UndefinedTable:
        return None


def db_table_exists(table_name: str, db_name=None, settings=None) -> bool:
    logger.debug(f"Checking if DB table '{table_name}' exists")
    try:
        conn = db_connect(settings=settings, override_db_name=db_name)
        cursor = conn.cursor()
        cursor.execute(f"SELECT * FROM information_schema.tables WHERE table_name = '{table_name}'")
        row = cursor.fetchone()
        return True if row else False
    except errors.OperationalError:
        return False


def create_db(settings=None, drop=False):
    actual_db_name = get_db_connection_param("POSTGRESQL_DATABASE", settings)
    logger.debug("Actual DB name: %r", actual_db_name)

    new_db_name = sql.Identifier(actual_db_name)

    con = db_connect(settings=settings, override_db_name='postgres')
    try:
        con.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        with con.cursor() as cur:
            if drop:
                cur.execute(
                    sql.SQL('DROP DATABASE IF EXISTS {}').format(new_db_name))
                cur.execute(sql.SQL('CREATE DATABASE {}').format(new_db_name))
            else:
                cur.execute(
                    'SELECT count(*) FROM pg_catalog.pg_database '
                    'WHERE datname = %s',
                    [actual_db_name])
                if not cur.fetchone()[0]:
                    cur.execute(sql.SQL('CREATE DATABASE {}').format(new_db_name))
    finally:
        con.close()

    logger.debug('DB %s created.', new_db_name.string)


def rename_db(old_name: str, new_name: str, settings=None):

    db.engine.dispose()
    con = db_connect(settings=settings, override_db_name='postgres')
    try:
        con.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        with con.cursor() as cur:
            cur.execute(f'ALTER DATABASE {old_name} RENAME TO {new_name}')
    finally:
        con.close()

    logger.debug('DB %s renamed to %s.', old_name, new_name)


def drop_db(db_name: str = None, settings=None):
    """Clear existing data and create new tables."""
    actual_db_name = db_name or get_db_connection_param("POSTGRESQL_DATABASE", settings)
    logger.debug("Actual DB name: %r", actual_db_name)
    db.engine.dispose()
    con = db_connect(settings=settings, override_db_name='postgres')
    try:
        con.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        with con.cursor() as cur:
            cur.execute(
                sql.SQL('DROP DATABASE IF EXISTS {}').format(sql.Identifier(actual_db_name)))
        logger.debug('database %s dropped', actual_db_name)
    finally:
        con.close()
