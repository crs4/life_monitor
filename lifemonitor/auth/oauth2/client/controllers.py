from __future__ import annotations

import logging
from .utils import RequestHelper
from .models import OAuthUserProfile, OAuthIdentity
from .services import oauth2_registry, config_oauth2_registry
from authlib.integrations.flask_client import FlaskRemoteApp
from flask import flash, url_for, redirect, request, session, Blueprint, current_app, abort
from flask_login import current_user, login_user
from lifemonitor import common, utils
from lifemonitor.db import db
from lifemonitor.auth.models import User
from authlib.integrations.base_client.errors import OAuthError
from lifemonitor.auth.oauth2.client.models import OAuth2IdentityProvider, OAuthIdentityNotFoundException
from authlib.oauth2.rfc6749 import OAuth2Token

# Config a module level logger
logger = logging.getLogger(__name__)

_OAUTH2_NEXT_URL = "oauth2.next"


def create_blueprint(merge_identity_view):
    authorization_handler = AuthorizatonHandler(merge_identity_view)

    def _handle_authorize(provider: FlaskRemoteApp, token, user_info):
        return authorization_handler\
            .handle_authorize(provider, token, OAuthUserProfile.from_dict(user_info))

    blueprint = Blueprint('oauth2provider', __name__)

    @blueprint.route('/authorized/<name>', methods=('GET', 'POST'))
    def authorize(name):
        remote = oauth2_registry.create_client(name)
        if remote is None:
            abort(404)

        next_url = request.args.get('next')
        if next_url or not request.args.get("state", False):
            return redirect(url_for(".login", name=name, next=next_url or remote.api_base_url))

        try:
            id_token = request.values.get('id_token')
            if request.values.get('code'):
                token = remote.authorize_access_token()
                if id_token:
                    token['id_token'] = id_token
            elif id_token:
                token = {'id_token': id_token}
            elif request.values.get('oauth_verifier'):
                # OAuth 1
                token = remote.authorize_access_token()
            else:
                # handle failed
                return _handle_authorize(remote, None, None)
            if 'id_token' in token:
                user_info = remote.parse_id_token(token)
            else:
                remote.token = token
                user_info = remote.userinfo(token=token)
            return _handle_authorize(remote, token, user_info)
        except OAuthError as e:
            logger.debug(e)
            return e.description, 401

    @blueprint.route('/login/<name>')
    def login(name):
        # we allow dynamic reconfiguration of the oauth2registry
        # when app is configured in dev or testing mode
        if current_app.config['ENV'] in ("testing", "development"):
            config_oauth2_registry(current_app)
        remote = oauth2_registry.create_client(name)
        if remote is None:
            abort(404)
        # save the 'next' parameter to allow automatic redirect after OAuth2 authorization
        next_url = request.args.get('next', False)
        if next_url:
            session[_OAUTH2_NEXT_URL] = next_url
        redirect_uri = url_for('.authorize', name=name, _external=True)
        conf_key = '{}_AUTHORIZE_PARAMS'.format(name.upper())
        params = current_app.config.get(conf_key, {})
        return remote.authorize_redirect(redirect_uri, **params)

    return blueprint


class AuthorizatonHandler:

    def __init__(self, merge_view="auth.merge") -> None:
        self.merge_view = merge_view

    def handle_authorize(self, provider: FlaskRemoteApp, token, user_info: OAuthUserProfile):
        logger.debug("Remote: %r", provider.name)
        logger.debug("Acquired token: %r", token)
        logger.debug("Acquired user_info: %r", user_info)
        # avoid autoflush in this session
        with db.session.no_autoflush:
            try:
                p = OAuth2IdentityProvider.find(provider.name)
                logger.debug("Provider found: %r", p)
            except common.EntityNotFoundException:
                try:
                    logger.debug(f"Provider '{provider.name}' not found!")
                    p = OAuth2IdentityProvider(provider.name, **provider.OAUTH_APP_CONFIG)
                    p.save()
                    logger.info(f"Provider '{provider.name}' registered")
                except Exception as e:
                    return common.report_problem_from_exception(e)

            try:
                identity = p.find_identity_by_provider_user_id(user_info.sub)
                logger.debug("Found OAuth identity <%r,%r>: %r",
                             provider.name, user_info.sub, identity)
                # update identity with the last token and userinfo
                identity.user_info = user_info.to_dict()
                identity.set_token(token)
                logger.debug("Update identity token: %r -> %r", identity.token, token)
            except OAuthIdentityNotFoundException:
                logger.debug("Not found OAuth identity <%r,%r>", provider.name, user_info.sub)
                with db.session.no_autoflush:
                    identity = OAuthIdentity(
                        provider=p,
                        user_info=user_info.to_dict(),
                        provider_user_id=user_info.sub,
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
                    user = User(username=utils.generate_username(user_info))
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
                flash(f"Your account has successfully been linked to the identity {identity}.")

            # Determine the right next hop
            next_url = request.args.get('next')
            logger.debug("Request redirect (next URL stored on the 'next' request param: %r)", next_url)
            if not next_url:
                next_url = session.pop(_OAUTH2_NEXT_URL, False)
                logger.debug("Request redirect (next URL stored on session: %r)", next_url)
            return redirect(next_url, code=307) if next_url \
                else RequestHelper.response() or redirect('/', code=302)

    @staticmethod
    def handle_validation(identity: OAuthIdentity):
        # If the token is expired it should be refreshed.
        # The refresh should be handle by using the 'refresh_token' grant
        # if supported by the OAuth2 server; otherwise a new authorization flow
        # should be started.
        token = OAuth2Token(identity.token)
        if not token.is_expired():
            logger.debug(f"The current token is not expired: {token}")
            return True
        # if the current token has a refresh token
        # it will be automatically refreshed
        if 'refresh_token' in token:
            logger.debug("The current token has a refresh token")
            return True
        # if the current token doesn't have a refresh token
        # automatically redirect the client to start a new authorization flow
        if "redirection" not in request.args:
            logger.debug("Trying to restart the authorization code flow")
            RequestHelper.push_request(params={'redirection': 'true'})
            return redirect(url_for('oauth2provider.login',
                                    headers=request.headers, name="seek"), code=307)
        return False
