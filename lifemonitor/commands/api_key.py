import sys
import click
import logging
from flask import Blueprint, current_app, g
from flask.cli import with_appcontext

from lifemonitor.auth.services import generate_new_api
from lifemonitor.auth.models import User, ApiKey

# set module level logger
logger = logging.getLogger(__name__)

# define the blueprint for DB commands
blueprint = Blueprint('api-key', __name__)


@blueprint.cli.command('create')
@click.argument("username")
@click.option("--scope", "scope",  # type=click.Choice(ApiKey.SCOPES),
              default="read", show_default=True)
@click.option("--length", "length", default=40, type=int, show_default=True)
@with_appcontext
def api_key_create(username, scope="read", length=40):
    """
    Create an API Key for a given user (identified by username)
    """
    from lifemonitor.app import db
    logger.debug("Finding User '%s'...", username)
    user = User.find_by_username(username)
    if not user:
        print("User not found")
        sys.exit(99)
    logger.debug("User found: %r", user)
    api_key = generate_new_api(user, scope, length)
    print("%r" % api_key)
    logger.debug("ApiKey created")


@blueprint.cli.command('list')
@click.argument("username")
@with_appcontext
def api_key_list(username):
    """
    Create an API Key for a given user (identified by username)
    """
    from lifemonitor.app import db
    logger.debug("Finding User '%s'...", username)
    user = User.find_by_username(username)
    if not user:
        print("User not found")
        sys.exit(99)
    logger.debug("User found: %r", user)
    print('-' * 82)
    print("User '%s' ApiKeys" % user.username)
    print('-' * 82)
    for key in user.api_keys:
        print(key)


@blueprint.cli.command('delete')
@click.argument("api_key")
@with_appcontext
def api_key_delete(api_key):
    """
    Create an API Key for a given user (identified by username)
    """
    from lifemonitor.app import db
    logger.debug("Finding ApiKey '%s'...", api_key)
    key = ApiKey.find(api_key)
    if not key:
        print("ApiKey not found")
        sys.exit(99)
    logger.debug("ApiKey found: %r", key)
    key.delete()
    print("ApiKey '%s' deleted!" % api_key)
    logger.debug("ApiKey created")


@blueprint.cli.command('clean')
@click.argument("username")
@with_appcontext
def api_key_clean(username):
    """
    Create an API Key for a given user (identified by username)
    """
    from lifemonitor.app import db
    logger.debug("Finding User '%s'...", username)
    user = User.find_by_username(username)
    if not user:
        print("User not found")
        sys.exit(99)
    logger.debug("User found: %r", user)
    count = 0
    for key in user.api_keys:
        key.delete()
        print("ApiKey '%s' deleted!" % key.key)
        count += 1
    print("%d ApiKeys deleted!" % count)
    logger.debug("ApiKeys of User '%s' deleted!", user.username)
