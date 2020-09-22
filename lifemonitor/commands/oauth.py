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


@blueprint.cli.command('create-client-oauth-code')
@click.argument("client_name")
@click.argument("client_uri")
@click.argument("client_redirect_uri")
@click.argument("scope")
@click.argument("client_auth_method",
                type=click.Choice(['client_secret_basic', 'client_secret_post']),
                default='client_secret_post')
@click.option("--username", default="1")  # should be the "admin" username
@with_appcontext
def create_client_oauth_code(client_name, client_uri, client_redirect_uri,
                             client_auth_method, scope, username):
    """
    Create a OAuth2 client with 'authorization_code' grant
    """
    user = User.find_by_username(username)
    logger.debug("USERNAME: %r", username)
    if not user:
        print("User not found", file=sys.stderr)
        sys.exit(99)
    logger.debug("User found: %r", user)
    client = server.create_client(user,
                                  client_name, client_uri,
                                  ['authorization_code', 'token', 'id_token'],
                                  ["code", "token"], scope,
                                  client_redirect_uri, client_auth_method)
    print("CLIENT ID: %s" % client.client_id)
    print("CLIENT SECRET: %s" % client.client_secret)
    print("AUTHORIZATION URL: <LIFE_MONITOR_BASE_URL>/oauth/authorize")
    print("ACCESS TOKEN URL: <LIFE_MONITOR_BASE_URL>/oauth/token")
    logger.debug("Client created")


@blueprint.cli.command('create-client-credentials')
@click.argument("client_name")
@click.argument("client_uri")
@click.argument("scope")
@click.argument("client_auth_method",
                type=click.Choice(['client_secret_basic', 'client_secret_post']),
                default='client_secret_post')
@click.option("--username", default="1")  # should be the "admin" username
@with_appcontext
def create_client_credentials(client_name, client_uri, client_auth_method, scope, username):
    """
    Create a OAuth2 client with 'client_credentials' grant
    """
    user = User.find_by_username(username)
    logger.debug("USERNAME: %r", username)
    if not user:
        print("User not found", file=sys.stderr)
        sys.exit(99)
    logger.debug("User found: %r", user)
    client = server.create_client(user,
                                  client_name, client_uri,
                                  'client_credentials', ["token"], scope,
                                  "", client_auth_method)
    print("CLIENT ID: %s" % client.client_id)
    print("CLIENT SECRET: %s" % client.client_secret)
    print("ACCESS TOKEN URL: <LIFE_MONITOR_BASE_URL>/oauth/token")
    logger.debug("Client created")
