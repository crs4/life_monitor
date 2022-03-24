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
