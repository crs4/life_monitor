from __future__ import annotations

import logging

import flask

from authlib.integrations.base_client import RemoteApp
from flask import flash, url_for, redirect
from flask_login import current_user, login_user
from loginpass import create_flask_blueprint
from sqlalchemy.orm.exc import NoResultFound

from lifemonitor.auth.models import User
from lifemonitor.utils import pop_request_from_session
from .models import OAuthUserProfile, OAuthIdentity
from .services import oauth2_registry

# Config a module level logger
logger = logging.getLogger(__name__)


def create_blueprint(merge_identity_view):
    authorization_handler = AuthorizatonHandler(merge_identity_view)

    def _handle_authorize(provider: RemoteApp, token, user_info):
        return authorization_handler.handle_authorize(provider, token, OAuthUserProfile.from_dict(user_info))

    return create_flask_blueprint([], oauth2_registry, _handle_authorize)


class AuthorizatonHandler:

    def __init__(self, merge_view="auth.merge") -> None:
        self.merge_view = merge_view

    def handle_authorize(self, provider: RemoteApp, token, user_info: OAuthUserProfile):
        logger.debug("Remote: %r", provider.name)
        logger.debug("Acquired token: %r", token)
        logger.debug("Acquired user_info: %r", user_info)

        try:
            identity = OAuthIdentity.find_by_provider(provider.name, user_info.sub)
            logger.debug("Found OAuth identity <%r,%r>: %r",
                         provider.name, user_info.sub, identity)
            # update identity with the last token and userinfo
            identity.user_info = user_info.to_dict()
            identity.token = token
        except NoResultFound:
            logger.debug("Not found OAuth identity <%r,%r>", provider.name, user_info.sub)
            identity = OAuthIdentity(
                provider_user_id=user_info.sub,
                provider=provider.name,
                user_info=user_info.to_dict(),
                token=token,
            )

        # Now, figure out what to do with this token. There are 2x2 options:
        # user login state and token link state.
        if current_user.is_anonymous:
            # If the user is not logged in and the token is linked,
            # log the identity user
            if identity.user:
                login_user(identity.user)
            else:
                # If the user is not logged in and the token is unlinked,
                # create a new local user account and log that account in.
                # This means that one person can make multiple accounts, but it's
                # OK because they can merge those accounts later.
                user = User.find_by_username(user_info.preferred_username)
                if not user:
                    user = User(username=user_info.preferred_username)
                identity.user = user
                identity.save()
                login_user(user)
                flash("OAuth identity linked to the current user account.")
        else:
            if identity.user:
                # If the user is logged in and the token is linked, check if these
                # accounts are the same!
                if current_user != identity.user:
                    # Account collision! Ask user if they want to merge accounts.
                    return redirect(url_for(self.merge_view,
                                            provider=identity.provider,
                                            username=identity.user.username))
            # If the user is logged in and the token is unlinked or linked yet,
            # link the token to the current user
            identity.user = current_user
            identity.save()
            flash("Successfully linked GitHub account.")

        logger.debug(user_info)
        next_url = flask.request.args.get('next')
        if not next_url:
            data = pop_request_from_session(provider.name)
            if data:
                next_url = url_for(data["endpoint"], **data["args"])
        return redirect(next_url or '/')
