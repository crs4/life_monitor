import re
import sys
import click
import logging
from flask import Blueprint
from flask.cli import with_appcontext
from lifemonitor.api.services import LifeMonitor

# set module level logger
logger = logging.getLogger(__name__)

# define the blueprint for DB commands
blueprint = Blueprint('registry', __name__)

# instance of LifeMonitor service
lm = LifeMonitor.get_instance()

supported_registries = ["seek"]


def print_registry_info(registry):
    output = f"""
    \nWorkflow Registry '{registry.name}' (uuid: {registry.uuid}, type: {registry.type}) registered!
    \nOAuth2 Settings to connect to LifeMonitor:
    - REGISTRY NAME: {registry.name}
    - REGISTRY CLIENT ID: {registry.client_credentials.client_id}
    - REGISTRY CLIENT SECRET: {registry.client_credentials.client_secret}
    - REGISTRY CLIENT ALLOWED SCOPES: {registry.client_credentials.client_metadata['scope']}
    - REGISTRY CLIENT ALLOWED FLOWS: {registry.client_credentials.client_metadata['grant_types']}
    - REGISTRY CLIENT REDIRECT URIs: {registry.client_credentials.redirect_uris}
    * AUTHORIZE URL: <LIFE_MONITOR_BASE_URL>/oauth2/authorize
    * ACCESS TOKEN URL: <LIFE_MONITOR_BASE_URL>/oauth2/token
    """
    print(output)


@blueprint.cli.command('add')
@click.argument("name")
@click.argument("type", type=click.Choice(supported_registries), default=supported_registries[0])
@click.argument("client-id")
@click.argument("client-secret")
@click.argument("api-url")
@click.option("--redirect-uris", default=None,
              help="Redirect URIs (comma separated) to be used with authorization code flow")
@with_appcontext
def add_registry(name, type, client_id, client_secret, api_url, redirect_uris):
    """
    Add a new Workflow Registry and generate its OAuth2 credentials
    """
    try:
        # At the moment client_credentials of registries
        # are associated with the admin account
        registry = lm.add_workflow_registry(type, name,
                                            client_id, client_secret, api_url, redirect_uris)
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
@click.option("--api-url", default=None, help="Base URL of the registry")
@click.option("--redirect-uris", default=None,
              help="Redirect URIs (comma separated) to be used with authorization code flow")
@with_appcontext
def update_registry(uuid, name, client_id, client_secret, api_url, redirect_uris):
    """
    Update an existing Workflow Registry
    """
    try:
        registry = lm.update_workflow_registry(uuid, name,
                                               client_id, client_secret, api_url,
                                               redirect_uris)
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
    try:
        registries = lm.get_workflow_registries()
        if len(registries) == 0:
            print("\n No Workflow Registry found !!!\n")
        else:
            print(f"\n Workflow Registries:\n{'*'*80}")
            for r in registries:
                print(f" - {r.uuid}: name='{r.name}', type={r.type}")
            print("\n")
    except Exception as e:
        try:
            detail = re.search('DETAIL:\\s*(.+)', str(e)).group(1)
        except AttributeError:
            detail = str(e)
        logger.exception(e)
        print(f"ERROR: {detail}", file=sys.stderr)
