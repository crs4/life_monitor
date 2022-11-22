# Copyright (c) 2020-2022 CRS4
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
from lifemonitor.auth.models import ApiKey, User
from lifemonitor.auth.services import generate_new_api_key

# set module level logger
logger = logging.getLogger(__name__)

# define the blueprint for DB commands
blueprint = Blueprint('api-key', __name__)

# set CLI help
blueprint.cli.help = "Manage admin API keys"


@blueprint.cli.command('create')
@click.option("--scope", "scope",
              default="read", show_default=True)
@click.option("--length", "length", default=40, type=int, show_default=True)
@with_appcontext
def api_key_create(scope="read", length=40):
    """
    Create an API Key for the 'admin' user
    """
    username = "admin"
    logger.debug("Finding user '%s'...", username)
    user = User.find_by_username(username)
    if not user:
        print("User not found", file=sys.stderr)
        sys.exit(99)
    logger.debug("User found: %r", user)
    api_key = generate_new_api_key(user, scope, length)
    print("%r" % api_key)
    logger.debug("Api key created")


@blueprint.cli.command('list')
@with_appcontext
def api_key_list():
    """
    Create an API Key for the 'admin' user
    """
    username = "admin"
    logger.debug("Finding user '%s'...", username)
    user = User.find_by_username(username)
    if not user:
        print("User not found", file=sys.stderr)
        sys.exit(99)
    logger.debug("User found: %r", user)
    print('-' * 82)
    print("Api keys of user '%s'" % user.username)
    print('-' * 82)
    for key in user.api_keys:
        print(key)


@blueprint.cli.command('delete')
@click.argument("api_key")
@with_appcontext
def api_key_delete(api_key):
    """
    Create an API Key for the 'admin' user
    """
    logger.debug("Finding Api key '%s'...", api_key)
    key = ApiKey.find(api_key)
    if not key:
        print("Api key not found", file=sys.stderr)
        sys.exit(99)
    logger.debug("Api key found: %r", key)
    key.delete()
    print("Api key '%s' deleted!" % api_key)
    logger.debug("Api key created")


@blueprint.cli.command('clean')
@with_appcontext
def api_key_clean():
    """
    Create an API Key for the 'admin' user
    """
    username = "admin"
    logger.debug("Finding user '%s'...", username)
    user = User.find_by_username(username)
    if not user:
        print("User not found", file=sys.stderr)
        sys.exit(99)
    logger.debug("User found: %r", user)
    count = 0
    for key in user.api_keys:
        key.delete()
        print("Api key '%s' deleted!" % key.key)
        count += 1
    print("%d ApiKeys deleted!" % count, file=sys.stderr)
    logger.debug("ApiKeys of user '%s' deleted!", user.username)
