import logging
from flask import Blueprint
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
    from lifemonitor.db import db
    logger.debug("Initializing DB...")
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
