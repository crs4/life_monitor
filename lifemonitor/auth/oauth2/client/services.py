from __future__ import annotations

import logging

from authlib.integrations.flask_client import FlaskRemoteApp, OAuth
from authlib.oauth2.rfc6749 import OAuth2Token
from flask import current_app
from flask_login import current_user
from lifemonitor.db import db

from ...models import User
# Config a module level logger
from .models import OAuthIdentity

# Config a module level logger
logger = logging.getLogger(__name__)


def fetch_token(name):
    logger.debug("NAME: %s", name)
    logger.debug("CURRENT APP: %r", current_app.config)
    api_key = current_app.config.get("{}_API_KEY".format(name.upper()), None)
    if api_key:
        logger.debug("FOUND an API KEY for the OAuth Service '%s': %s", name, api_key)
        return {"access_token": api_key}
    identity = OAuthIdentity.find_by_user_id(current_user.id, name)
    logger.debug("The token: %r", identity.token)
    return OAuth2Token(identity.token)


def update_token(name, token, refresh_token=None, access_token=None):
    if access_token or refresh_token:
        identity = OAuthIdentity.find_by_user_id(current_user.id, name)
    else:
        return

    # update old token
    identity.set_token(token)
    identity.save()


# Create an instance of OAuth registry for oauth clients.
oauth2_registry = OAuth(fetch_token=fetch_token, update_token=update_token)

current_providers_list = []


def get_providers():
    from .providers.github import GitHub
    from .providers.seek import Seek
    global current_providers_list
    providers = Seek.all()
    if current_app.config.get('GITHUB_CLIENT_ID', None) \
            and current_app.config.get('GITHUB_CLIENT_SECRET', None):
        providers.append(GitHub)
    # The current implementation doesn't support dynamic registration of WorkflowRegistries
    # The following a simple workaround to detect and reconfigure the oauth2registry
    # when the number of workflow registries changes
    if not current_providers_list or len(current_providers_list) != len(providers):
        config_oauth2_registry(current_app, providers=providers)
    current_providers_list = providers
    return providers


def config_oauth2_registry(app, providers=None):
    try:
        oauth2_backends = providers or get_providers()
        for backend in oauth2_backends:
            class RemoteApp(FlaskRemoteApp):
                NAME = backend.name
                OAUTH_APP_CONFIG = backend.oauth_config

            oauth2_registry.register(RemoteApp.NAME, overwrite=True, client_cls=RemoteApp)
        oauth2_registry.init_app(app)
    except Exception as e:
        logger.debug(e)


def merge_users(merge_from: User, merge_into: User, provider: str):
    assert merge_into != merge_from
    logger.debug("Trying to merge %r, %r, %r", merge_into, merge_from, provider)
    for identity in list(merge_from.oauth_identity.values()):
        identity.user = merge_into
        db.session.add(identity)
    # TODO: Move all oauth clients to the new user
    for client in list(merge_from.clients):
        client.user = merge_into
        db.session.add(client)
    # TODO: Check for other links to move to the new user
    # e.g., tokens, workflows, tests, ....
    db.session.delete(merge_from)
    db.session.commit()
    return merge_into
