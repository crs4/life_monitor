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

from __future__ import annotations

import logging

from authlib.integrations.base_client.errors import OAuthError
from authlib.integrations.flask_client import FlaskRemoteApp
from flask import (Blueprint, abort, current_app, flash, redirect, request,
                   session, url_for)
from flask_login import current_user, login_user

from lifemonitor import exceptions, utils
from lifemonitor.auth.models import User
from lifemonitor.auth.oauth2.client.models import (
    OAuth2IdentityProvider, OAuthIdentityNotFoundException)
from lifemonitor.db import db
from lifemonitor.utils import (NextRouteRegistry, is_service_alive,
                               next_route_aware)

from .models import OAuthIdentity, OAuthUserProfile
from .services import (config_oauth2_registry, oauth2_registry,
                       save_current_user_identity)
from .utils import RequestHelper

# Config a module level logger
logger = logging.getLogger(__name__)


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
            # if 'id_token' in token:
            #     user_info = remote.parse_id_token(token)
            # else:
            remote.token = token
            user_info = remote.userinfo(token=token)
            return _handle_authorize(remote, token, user_info)
        except OAuthError as e:
            logger.debug(e)
            return e.description, 401

    @blueprint.route('/login/<name>')
    @next_route_aware
    def login(name, scope: str = None):
        # we allow dynamic reconfiguration of the oauth2registry
        # when app is configured in dev or testing mode
        if current_app.config['ENV'] in ("testing", "testingSupport", "development"):
            config_oauth2_registry(current_app)
        remote = oauth2_registry.create_client(name)
        if remote is None:
            abort(404)
        logger.debug("config: %r", remote.OAUTH_APP_CONFIG)
        if not is_service_alive(remote.OAUTH_APP_CONFIG['api_base_url']):
            abort(503)
        action = request.args.get('action', False)
        if action and action == 'sign-in':
            session['sign_in'] = True
        redirect_uri = url_for('.authorize', name=name, _external=True)
        conf_key = '{}_AUTHORIZE_PARAMS'.format(name.upper())
        params = current_app.config.get(conf_key, {})
        scope = scope or request.args.get('scope')
        if scope:
            params.update({'scope': scope})
        return remote.authorize_redirect(redirect_uri, **params)

    @blueprint.route('/logout/<name>')
    @next_route_aware
    def logout(name: str):
        try:
            # we allow dynamic reconfiguration of the oauth2registry
            # when app is configured in dev or testing mode
            provider = OAuth2IdentityProvider.find_by_client_name(name)
            if provider is None:
                abort(404)
            # unlink identity
            del current_user.oauth_identity[provider.client_name]
            current_user.save()
            flash(f"\"{provider.name}\" identity unlinked from you account.", category="success")
        except Exception as e:
            message = f"Unable to unlink identity '{provider.name}' of user {current_user}"
            logger.error(message)
            flash(message, category="error")
            if logger.isEnabledFor(logging.DEBUG):
                logger.exception(e)

        # Determine the right next hop
        next_url = NextRouteRegistry.pop()
        if next_url:
            try:
                NextRouteRegistry.validate_next_route_url(next_url)
                return redirect(next_url, code=307)
            except ValidationError as e:
                logger.error(e)
        # redirect to the account page if the next url is not defined or invalid
        return RequestHelper.response() or redirect('/account', code=302)

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
                p = OAuth2IdentityProvider.find_by_client_name(provider.name)
                logger.debug("Provider found: %r", p)
            except exceptions.EntityNotFoundException:
                try:
                    logger.debug(f"Provider '{provider.name}' not found!")
                    p = OAuth2IdentityProvider(provider.name, **provider.OAUTH_APP_CONFIG)
                    p.save()
                    logger.info(f"Provider '{provider.name}' registered")
                except Exception as e:
                    return exceptions.report_problem_from_exception(e)

            try:
                identity = p.find_identity_by_provider_user_id(user_info.sub)
                logger.debug("Found OAuth identity <%r,%r>: %r",
                             provider.name, user_info.sub, identity)
                # update identity with the last token and userinfo
                identity.user_info = user_info.to_dict()
                identity.token = token
                logger.debug("Update identity token: %r -> %r", identity.token, token)
            except OAuthIdentityNotFoundException:
                logger.debug("Not found OAuth identity <%r,%r>", provider.name, user_info.sub)
                logger.debug("SignIn: %r", session.get('sign_in', False))
                # with db.session.no_autoflush:
                identity = OAuthIdentity(
                    provider=p,
                    user_info=user_info.to_dict(),
                    provider_user_id=user_info.sub,
                    token=token,
                )
                save_current_user_identity(identity)
                try:
                    if session['sign_in']:
                        return redirect(url_for("auth.identity_not_found"))
                except KeyError as e:
                    logger.error(e)

            try:
                session.pop('sign_in', False)
            except KeyError as e:
                logger.debug(e)

            # Now, figure out what to do with this token. There are 2x2 options:
            # user login state and token link state.
            if current_user.is_anonymous:
                # If the user is not logged in and the token is linked,
                # log the identity user
                if identity.user:
                    identity.save()
                    login_user(identity.user)
                    # # update the registry token if registry integration has been enabled by the user
                    # if identity.user and identity.user.registry_settings:
                    #     r_token = identity.user.registry_settings.get_token(provider.name)
                    #     logger.error("User registry token: %r", r_token)
                    #     if r_token and r_token['scope'] != token['scope']:
                    #         logger.debug("Trying to update the registry token...")
                    #         return redirect(f'/oauth2/login/{provider.name}?scope=read+write')
                    #     else:
                    #         logger.debug("We don't need to update the registry token...")
                else:
                    # If the user is not logged in and the token is unlinked,
                    # create a new local user account and log that account in.
                    # This means that one person can make multiple accounts, but it's
                    # OK because they can merge those accounts later.
                    user = User()
                    identity.user = user
                    # Check whether to review user details
                    review_details = session.get("confirm_user_details", None)
                    # Initialize username.
                    # if the user will be automatically registered (without review)
                    # we append a random string to the his identity username
                    identity.user.username = \
                        utils.generate_username(
                            user_info,
                            salt_length=4 if not review_details else 0)
                    if not review_details:
                        identity.save()
                        login_user(user)
                        flash("OAuth identity linked to the current user account.")
                    else:
                        # save the user identity on the current session
                        save_current_user_identity(identity)
                        # and redirect the user
                        # to finalize the registration
                        return redirect(url_for('auth.register_identity'))
            else:
                logger.debug("User not anonymous!")
                if identity.user:
                    # If the user is logged in and the token is linked, check if these
                    # accounts are the same!
                    if current_user != identity.user:
                        # Account collision! Ask user if they want to merge accounts.
                        return redirect(url_for(self.merge_view,
                                                provider=identity.provider.client_name,
                                                username=identity.user.username))
                # If the user is logged in and the token is unlinked or linked yet,
                # link the token to the current user
                else:
                    identity.user = current_user
                identity.save()
                flash(f"Your account has successfully been linked to your <b>{identity.provider.name}</b> identity.")

            # flush db session
            db.session.commit()
            db.session.flush()
            logger.debug("Identity flushed")
            flash(f"Logged with your <b>\"{identity.provider.name}\"</b> identity.", category="success")

            # Determine the right next hop
            next_url = NextRouteRegistry.pop()
            if next_url:
                try:
                    NextRouteRegistry.validate_next_route_url(next_url)
                    return redirect(next_url, code=307)
                except ValidationError as e:
                    logger.error(e)
            # redirect to the account page if the next url is not defined or invalid
            return RequestHelper.response() or redirect('/account', code=302)

    @staticmethod
    def validate_identity_token(identity: OAuthIdentity):
        # If the token is expired it should be refreshed.
        # The refresh should be handle by using the 'refresh_token' grant
        # if supported by the OAuth2 server; otherwise a new authorization flow
        # should be started.
        token = identity.token
        # if the current token has a refresh token
        # it will be automatically refreshed
        if 'refresh_token' in token:
            logger.debug("The current token has a refresh token")
            logger.debug("The current token is %s", "expired" if token.is_expired() else "not expired")
            # try to update the token using the refresh token grant
            identity.fetch_token(auth=True)
            return True
        # if the current token doesn't have a refresh token
        # automatically redirect the client to start a new authorization flow
        if "redirection" not in request.args:
            logger.debug("Trying to restart the authorization code flow")
            RequestHelper.push_request(params={'redirection': 'true'})
            return redirect(url_for('oauth2provider.login',
                                    headers=request.headers, name=identity.provider.name), code=307)
        return False
