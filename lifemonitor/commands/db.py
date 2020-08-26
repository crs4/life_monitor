import logging
from flask import Blueprint
from flask.cli import with_appcontext

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
    from lifemonitor.app import db
    logger.debug("Initializing DB...")
    db.create_all()
    logger.info("DB initialized")
