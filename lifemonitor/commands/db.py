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
from flask import Blueprint, current_app
from flask.cli import with_appcontext
from lifemonitor.auth.models import User

# set module level logger
logger = logging.getLogger(__name__)

# define the blueprint for DB commands
blueprint = Blueprint('db', __name__)


@blueprint.cli.command('init')
@with_appcontext
def db_init():
    """
    Initialize the DB
    """
    from lifemonitor.db import db, create_db
    logger.debug("Initializing DB...")
    create_db(settings=current_app.config)
    db.create_all()
    logger.info("DB initialized")
    # create a default admin user if not exists
    admin = User.find_by_username('admin')
    if not admin:
        admin = User("admin")
        admin.password = "admin"
        db.session.add(admin)
        db.session.commit()


@blueprint.cli.command('clean')
@with_appcontext
def db_clean():
    """ Clean up DB """
    from lifemonitor.db import db
    db.session.rollback()
    for table in reversed(db.metadata.sorted_tables):
        db.session.execute(table.delete())
    db.session.commit()
    logger.info("DB deleted")
