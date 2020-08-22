from __future__ import annotations

import logging

from authlib.integrations.flask_client import FlaskRemoteApp
from authlib.integrations.flask_client import OAuth
from authlib.oauth2.rfc6749 import OAuth2Token
from flask import current_app
from flask_login import current_user

from lifemonitor.app import db
from .providers.github import GitHub
from .providers.seek import Seek
# Config a module level logger
from .models import OAuthIdentity
from ...models import User

logger = logging.getLogger(__name__)


def fetch_token(name):
    logger.debug("NAME: %s", name)
    logger.debug("CURRENT APP: %r", current_app.config)
    api_key = current_app.config.get("{}_API_KEY".format(name.upper()), None)
    if api_key:
        logger.debug("FOUND an API KEY for the OAuth Service '%s': %s", name, api_key)
        return {"access_token": api_key}
    identity = OAuthIdentity.find_by_user_provider(current_user.id, name)
    logger.debug("The token: %r", identity.token)
    return OAuth2Token(identity.token)


def update_token(name, token, refresh_token=None, access_token=None):
    if access_token or refresh_token:
        identity = OAuthIdentity.find_by_user_provider(current_user.id, name)
    else:
        return

    # update old token
    identity.token = token
    identity.save()


# Create an instance of OAuth registry for oauth clients.
oauth2_registry = OAuth(fetch_token=fetch_token, update_token=update_token)

# Register backend services
oauth2_backends = [GitHub, Seek]
for backend in oauth2_backends:
    class RemoteApp(backend, FlaskRemoteApp):
        OAUTH_APP_CONFIG = backend.OAUTH_CONFIG


    oauth2_registry.register(RemoteApp.NAME, overwrite=True, client_cls=RemoteApp)


def merge_users(merge_into: User, merge_from: User, provider: str):
    assert merge_into != merge_from
    identity = merge_from.oauth_identity[provider]
    del merge_from.oauth_identity[provider]
    identity.user = merge_into
    db.session.add(merge_into)
    if len(merge_from.oauth_identity) == 0 and not merge_from.password_hash:
        db.session.delete(merge_from)
    else:
        db.session.add(merge_from)
    db.session.commit()
    return merge_into