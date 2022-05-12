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
import re
import sys

import click
from flask import Blueprint
from flask.cli import with_appcontext
from lifemonitor.api.services import LifeMonitor

# set module level logger
logger = logging.getLogger(__name__)

# define the blueprint for DB commands
blueprint = Blueprint('registry', __name__)

# set CLI help
blueprint.cli.help = "Manage workflow registries"

# instance of LifeMonitor service
lm = LifeMonitor.get_instance()

supported_registries = ["seek"]


def print_registry_info(registry):
    output = f"""\n
{'*'*100}
Workflow Registry '{registry.name}' (uuid: {registry.uuid}, type: {registry.type}) registered!
{'*'*100}\n\n
OAuth2 settings to connect to LifeMonitor:
{'-'*100}
REGISTRY NAME: {registry.name}
REGISTRY API URL: {registry.uri}
REGISTRY CLIENT NAME: {registry.client_name}
REGISTRY CLIENT ID: {registry.client_credentials.client_id}
REGISTRY CLIENT SECRET: {registry.client_credentials.client_secret}
REGISTRY CLIENT ALLOWED SCOPES: {registry.client_credentials.client_metadata['scope']}
REGISTRY CLIENT ALLOWED FLOWS: {registry.client_credentials.client_metadata['grant_types']}
REGISTRY CLIENT REDIRECT URIs: {registry.client_credentials.redirect_uris}
REGISTRY CLIENT AUTH METHOD: {registry.client_credentials.auth_method}
AUTHORIZE URL: <LIFE_MONITOR_BASE_URL>/oauth2/authorize/{registry.client_name}
ACCESS TOKEN URL: <LIFE_MONITOR_BASE_URL>/oauth2/token
CALLBACK URL: <LIFE_MONITOR_BASE_URL>/oauth2/authorized/{registry.client_name}[?next=<URL>]
"""
    print(output)


@blueprint.cli.command('add')
@click.argument("name")
@click.argument("type", type=click.Choice(supported_registries), default=supported_registries[0])
@click.argument("client-id")
@click.argument("client-secret")
@click.argument("api-url")
@click.option("--client-name", default=None,
              help="Short name which identifies the registry on LifeMonitor")
@click.option("--redirect-uris", default=None,
              help="Redirect URIs (comma separated) to be used with authorization code flow")
@click.option("--client-auth-method",
              help="Specifies the method used for authenticating the registry with LifeMonitor",
              type=click.Choice(['client_secret_basic', 'client_secret_post']),
              default='client_secret_post')
@with_appcontext
def add_registry(name, type, client_id, client_secret, client_auth_method, api_url, client_name, redirect_uris):
    """
    Add a new workflow registry and generate its OAuth2 credentials
    """
    try:
        # At the moment client_credentials of registries
        # are associated with the admin account
        registry = lm.add_workflow_registry(type, name,
                                            client_id, client_secret,
                                            client_name=client_name,
                                            client_auth_method=client_auth_method,
                                            api_base_url=api_url,
                                            redirect_uris=redirect_uris)
        logger.info("Registry '%s' created!" % name)
        print_registry_info(registry)
    except Exception as e:
        try:
            detail = re.search('DETAIL:\\s*(.+)', str(e)).group(1)
        except AttributeError:
            detail = str(e)
        print(f"ERROR: {detail}", file=sys.stderr)


@blueprint.cli.command('update')
@click.argument("uuid")
@click.option("--name", default=None,
              help="Short name to identify the registry")
@click.option("--client-id", default=None,
              help="OAuth2 Client ID to access to the registry")
@click.option("--client-secret", default=None,
              help="OAuth2 Client Secret to access to the registry")
@click.option("--client-name", default=None,
              help="Short name which identifies the registry on LifeMonitor")
@click.option("--api-url", default=None, help="Base URL of the registry")
@click.option("--redirect-uris", default=None,
              help="Redirect URIs (comma separated) to be used with authorization code flow")
@click.option("--client-auth-method",
              help="Specifies the method used for authenticating the registry with LifeMonitor",
              type=click.Choice(['client_secret_basic', 'client_secret_post']),
              default=None)
@with_appcontext
def update_registry(uuid, name,
                    client_id, client_secret, client_name,
                    client_auth_method, api_url, redirect_uris):
    """
    Update a workflow registry
    """
    try:
        registry = lm.update_workflow_registry(uuid,
                                               name=name,
                                               client_id=client_id,
                                               client_secret=client_secret,
                                               client_auth_method=client_auth_method,
                                               api_base_url=api_url,
                                               redirect_uris=redirect_uris)
        logger.info("Registry '%s' updated!" % name)
        print_registry_info(registry)
    except Exception as e:
        try:
            detail = re.search('DETAIL:\\s*(.+)', str(e)).group(1)
        except AttributeError:
            detail = str(e)
        print(f"ERROR: {detail}", file=sys.stderr)


@blueprint.cli.command('list')
@with_appcontext
def list_registries():
    """ List all workflow registries """
    try:
        registries = lm.get_workflow_registries()
        if len(registries) == 0:
            print("\n No Workflow Registry found !!!\n")
        else:
            print(f"\n Workflow Registries:\n{'*'*80}")
            for r in registries:
                print(f"{r.uuid} (name='{r.name}', type={r.type})")
            print("\n")
    except Exception as e:
        try:
            detail = re.search('DETAIL:\\s*(.+)', str(e)).group(1)
        except AttributeError:
            detail = str(e)
        logger.exception(e)
        print(f"ERROR: {detail}", file=sys.stderr)


@blueprint.cli.command('show')
@click.argument("name")
@with_appcontext
def show_registry(name):
    """ Show info of a workflow registry """
    try:
        registry = lm.get_workflow_registry_by_name(name)
        if not registry:
            print(f"\n Workflow Registry '{name}' not found !!!\n")
        else:
            print_registry_info(registry)
    except Exception as e:
        try:
            detail = re.search('DETAIL:\\s*(.+)', str(e)).group(1)
        except AttributeError:
            detail = str(e)
        logger.exception(e)
        print(f"ERROR: {detail}", file=sys.stderr)
