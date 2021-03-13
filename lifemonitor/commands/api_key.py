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
import sys

import click
from flask import Blueprint
from flask.cli import with_appcontext

from lifemonitor.auth.services import generate_new_api_key
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
    logger.debug("Finding User '%s'...", username)
    user = User.find_by_username(username)
    if not user:
        print("User not found", file=sys.stderr)
        sys.exit(99)
    logger.debug("User found: %r", user)
    api_key = generate_new_api_key(user, scope, length)
    print("%r" % api_key)
    logger.debug("ApiKey created")


@blueprint.cli.command('list')
@click.argument("username")
@with_appcontext
def api_key_list(username):
    """
    Create an API Key for a given user (identified by username)
    """
    logger.debug("Finding User '%s'...", username)
    user = User.find_by_username(username)
    if not user:
        print("User not found", file=sys.stderr)
        sys.exit(99)
    logger.debug("User found: %r", user)
    logger.info('-' * 82)
    logger.info("User '%s' ApiKeys", user.username)
    logger.info('-' * 82)
    for key in user.api_keys:
        print(key)


@blueprint.cli.command('delete')
@click.argument("api_key")
@with_appcontext
def api_key_delete(api_key):
    """
    Create an API Key for a given user (identified by username)
    """
    logger.debug("Finding ApiKey '%s'...", api_key)
    key = ApiKey.find(api_key)
    if not key:
        print("ApiKey not found", file=sys.stderr)
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
    logger.debug("Finding User '%s'...", username)
    user = User.find_by_username(username)
    if not user:
        print("User not found", file=sys.stderr)
        sys.exit(99)
    logger.debug("User found: %r", user)
    count = 0
    for key in user.api_keys:
        key.delete()
        print("ApiKey '%s' deleted!" % key.key)
        count += 1
    print("%d ApiKeys deleted!" % count, file=sys.stderr)
    logger.debug("ApiKeys of User '%s' deleted!", user.username)
