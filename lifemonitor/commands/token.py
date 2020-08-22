import logging
import sys

import click
from flask import Blueprint
from flask.cli import with_appcontext
from lifemonitor.auth.models import User

# set module level logger
logger = logging.getLogger(__name__)

# define the blueprint for DB commands
blueprint = Blueprint('token', __name__)


def invalidate_token(token):
    invalid_token = token.copy()
    invalid_token["expires_in"] = 10
    invalid_token["expires_at"] = token["created_at"] + 10
    return invalid_token


@blueprint.cli.command('invalidate')
@click.argument("username")
@with_appcontext
def token_invalidate(username):
    """
    Create an API Key for a given user (identified by username)
    """
    logger.debug("Finding User '%s'...", username)
    user = User.find_by_username(username)
    if not user:
        print("User not found")
        sys.exit(99)
    logger.debug("User found: %r", user)
    count = 0
    for identity in user.oauth_identity.values():
        identity.token = invalidate_token(identity.token)
        identity.save()
        print("Token invalidated: %r !" % identity.token)
        count += 1
    print("%d Token invalidated!" % count)
    logger.debug("Token of User '%s' invalidated!", user.username)
