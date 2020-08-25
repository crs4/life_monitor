import logging
import sys

import click
from flask import Blueprint
from flask.cli import with_appcontext
from lifemonitor.auth.models import User
from lifemonitor.auth.oauth2.server import server

# set module level logger
logger = logging.getLogger(__name__)

# define the blueprint for DB commands
blueprint = Blueprint('oauth', __name__)


@blueprint.cli.command('create-client')
@click.argument("username")
@click.argument("client_name")
@click.argument("client_uri")
@click.argument("client_redirect_uri")
@click.argument("scope")
@with_appcontext
def create_client(username, client_name, client_uri, client_redirect_uri, scope):
    """
    Create a OAuth2 client with 'authorization_code' grant
    """
    user = User.find_by_username(username)
    if not user:
        print("User not found", file=sys.stderr)
        sys.exit(99)
    logger.debug("User found: %r", user)
    client = server.create_client(user,
                                  client_name, client_uri,
                                  ["authorization_code"], ["token"], scope,
                                  client_redirect_uri)
    print("CLIENT ID: %s" % client.client_id)
    print("CLIENT SECRET: %s" % client.client_secret)
    logger.debug("Client created")


def invalidate_token(token):
    invalid_token = token.copy()
    invalid_token["expires_in"] = 10
    invalid_token["expires_at"] = token["created_at"] + 10
    return invalid_token


@blueprint.cli.command('invalidate-tokens')
@click.argument("username")
@with_appcontext
def token_invalidate(username):
    """
    Invalidate all tokens related with a given user
    """
    logger.debug("Finding User '%s'...", username)
    user = User.find_by_username(username)
    if not user:
        print("User not found", file=sys.stderr)
        sys.exit(99)
    logger.debug("User found: %r", user)
    count = 0
    for identity in user.oauth_identity.values():
        identity.token = invalidate_token(identity.token)
        identity.save()
        print("Token invalidated: %r !" % identity.token)
        count += 1
    print("%d Token invalidated!" % count, file=sys.stderr)
    logger.debug("Token of User '%s' invalidated!", user.username)
