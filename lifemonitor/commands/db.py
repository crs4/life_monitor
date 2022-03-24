# Copyright (c) 2020-2021 CRS4
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
import sys
from datetime import datetime

import click
from flask import current_app
from flask.cli import with_appcontext
from flask_migrate import cli, current, stamp, upgrade
from lifemonitor.auth.models import User

# set module level logger
logger = logging.getLogger()

# export from this module
commands = [cli.db]

# update help for the DB command
cli.db.help = "Manage database"

# set initial revision number
initial_revision = '8b2e530dc029'


@cli.db.command()
@click.option("-r", "--revision", default="head")
@with_appcontext
def init(revision):
    """
    Initialize app database
    """
    from lifemonitor.db import create_db, db, db_initialized, db_revision

    is_initialized = db_initialized()
    logger.info("LifeMonitor app initialized: %r", is_initialized)
    if is_initialized:
        current_revision = db_revision()
        if not current_revision:
            # if DB is initialized with no revision
            # set the initial revision and then apply migrations
            stamp(revision=initial_revision)
            logger.info(f"Set initial revision: {initial_revision}")
        # Apply migrations
        logger.info(f"Applying migrations up to revision '{revision}'...")
        upgrade(revision=revision)
        logger.info("Migrations applied!")
        logger.info("Current revision: %r", db_revision())
    else:
        logger.debug("Initializing DB...")
        create_db(settings=current_app.config)
        db.create_all()
        stamp()
        current()
        logger.info("DB initialized")
        # create a default admin user if not exists
        admin = User.find_by_username('admin')
        if not admin:
            admin = User('admin')
            admin.password = current_app.config["LIFEMONITOR_ADMIN_PASSWORD"]
            db.session.add(admin)
            db.session.commit()


@cli.db.command()
@with_appcontext
def wait_for_db():
    """
    Wait until that DBMS service is up and running
    """
    from lifemonitor.db import db_initialized, db_revision

    is_initialized = False
    while not is_initialized:
        is_initialized = db_initialized()
    logger.info("DB initialized")

    current_revision = None
    while current_revision is None:
        current_revision = db_revision()
    logger.info(f"Current revision: {current_revision}")


@cli.db.command()
@click.option("-f", "--file", default=None, help="Filename (default hhmmss_yyyymmdd.tar")
@with_appcontext
def backup(file):
    """
    Make a backup of the current app database
    """
    from lifemonitor.db import db_connection_params
    params = db_connection_params()
    if not file:
        file = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.tar"
    cmd = f"PGPASSWORD={params['password']} pg_dump -h {params['host']} -U {params['user']} -F t {params['dbname']} > {file}"
    os.system(cmd)
    msg = f"Created backup of database {params['dbname']} on {file}"
    logger.debug(msg)
    print(msg)


@cli.db.command()
@click.argument("file")
@click.option("-s", "--safe", default=False, is_flag=True,
              help="Preserve the current database renaming it as '<dbname>_yyyymmdd_hhmmss'")
@with_appcontext
def restore(file, safe=False):
    """
    Restore a backup of the app database
    """
    from lifemonitor.db import (create_db, db_connection_params, db_exists,
                                drop_db, rename_db)
    params = db_connection_params()
    db_copied = False
    if db_exists(params['dbname']):
        if safe:
            answer = input(f"The database '{params['dbname']}' will be renamed. Continue? (y/n): ")
            if not answer.lower() in ('y', 'yes'):
                sys.exit(0)
            new_db_name = f"{params['dbname']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            rename_db(params['dbname'], new_db_name)
            db_copied = True
            logger.debug(f"Current database '{params['dbname']}' renamed as '{new_db_name}'")
        else:
            answer = input(f"The database '{params['dbname']}' will be delete. Continue? (y/n): ")
            if not answer.lower() in ('y', 'yes'):
                sys.exit(0)
            drop_db()
            logger.debug(f"Current database '{params['dbname']}' deleted")
    create_db(current_app.config)
    cmd = f"PGPASSWORD={params['password']} pg_restore -h {params['host']} -U {params['user']} -d {params['dbname']} -v {file}"
    os.system(cmd)
    if db_copied:
        print(f"Existing database '{params['dbname']}' renamed as '{new_db_name}'")
    msg = f"Backup {file} restored to database '{params['dbname']}'"
    logger.debug(msg)
    print(msg)


@cli.db.command()
@click.argument("snapshot", default="current")
@with_appcontext
def drop(snapshot):
    """
    Drop (a snapshot of) the app database.

    A snapshot is specified by a datetime formatted as yyyymmdd_hhmmss: e.g., 20220324_100137.

    If no snaphot is provided the current app database will be removed.
    """
    from lifemonitor.db import db_connection_params, drop_db
    db_name = db_connection_params()['dbname']
    if snapshot and snapshot != "current":
        if not snapshot.startswith(db_name):
            db_name = f"{db_name}_{snapshot}"
        else:
            db_name = snapshot
    answer = input(f"The database '{db_name}' will be removed. Are you sure? (y/n): ")
    if answer.lower() in ('y', 'yes'):
        drop_db(db_name=db_name)
        print(f"Database '{db_name}' removed")
    else:
        print("Database deletion aborted")
