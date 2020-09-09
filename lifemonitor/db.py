import os

import logging
from flask_sqlalchemy import SQLAlchemy
import psycopg2 as psy
import psycopg2.sql as sql
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

# set module level logger
logger = logging.getLogger(__name__)

# set DB instance
db = SQLAlchemy()


def db_connection_params():
    return {
        'host': os.getenv("POSTGRESQL_HOST"),
        'port': os.getenv("POSTGRESQL_PORT"),
        'user': os.getenv("POSTGRESQL_USERNAME"),
        'password': os.getenv("POSTGRESQL_PASSWORD"),
        'dbname': os.getenv("POSTGRESQL_DATABASE")
    }


def db_uri():
    """
    Build URI to connect to the DataBase
    :return:
    """
    # "postgresql:///{0}/app-dev.db".format(basedir)
    if os.getenv('DATABASE_URI'):
        uri = os.getenv('DATABASE_URI')
    else:
        conn_params = db_connection_params()
        uri = "postgresql://{user}:{passwd}@{host}:{port}/{dbname}".format(
            user=conn_params['user'],
            passwd=conn_params['password'],
            host=conn_params['host'],
            port=conn_params['port'],
            dbname=conn_params['dbname'])
    return uri


def db_connect(conn_params=None, override_db_name=None):
    if conn_params is None:
        conn_params = db_connection_params()

    actual_db_name = override_db_name if override_db_name else conn_params['dbname']
    con = psy.connect(
        host=conn_params.get('host'),
        port=conn_params.get('port'),
        user=conn_params['user'],
        password=conn_params['password'],
        dbname=actual_db_name)
    logger.debug("Connected to database '%s'", actual_db_name)
    return con


def create_db(conn_params=None, drop=False):
    if conn_params is None:
        conn_params = db_connection_params()
    logger.debug("Connection params: %r", conn_params)

    new_db_name = sql.Identifier(conn_params['dbname'])

    con = db_connect(conn_params, 'postgres')
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
                    [conn_params['dbname']])
                if not cur.fetchone()[0]:
                    cur.execute(sql.SQL('CREATE DATABASE {}').format(new_db_name))
    finally:
        con.close()

    logger.debug('DB %s created.', new_db_name.string)


def drop_db(conn_params=None):
    """Clear existing data and create new tables."""
    if conn_params is None:
        conn_params = db_connection_params()
    logger.debug("Connection params: %r", conn_params)

    logger.debug('drop_db %s', conn_params)

    con = db_connect(conn_params, 'postgres')
    try:
        con.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        with con.cursor() as cur:
            cur.execute(
                sql.SQL('DROP DATABASE IF EXISTS {}').format(sql.Identifier(conn_params['dbname'])))
        logger.debug('database %s dropped', conn_params['dbname'])
    finally:
        con.close()
