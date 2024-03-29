# Copyright (c) 2020-2024 CRS4
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

from flask import (Blueprint, jsonify, redirect, render_template, request,
                   url_for)
from flask_login import current_user, login_required
from lifemonitor.utils import NextRouteRegistry, OpenApiSpecs, bool_from_string

from .forms import AuthorizeClient
from .models import Token
from .services import server
from .utils import split_by_crlf

blueprint = Blueprint("oauth2_server", __name__,
                      template_folder='templates',
                      static_folder="static", static_url_path='/static/auth2')

logger = logging.getLogger(__name__)


@blueprint.route('/authorize', methods=['GET', 'POST'])
def authorize():
    # Login is required since we need to know the current resource owner.
    # The decorator ensures the redirection to the login page when the current
    # user is not authenticated.
    if not current_user.is_authenticated:
        NextRouteRegistry.save(route=request.url)
        return redirect(url_for('auth.login'))
    return _process_authorization()


@blueprint.route('/authorize/<name>', methods=['GET', 'POST'])
def authorize_provider(name):
    # Login is required since we need to know the current resource owner.
    # This authorizataion request comes from a registry (identified by 'name')
    # and registries act as identity providers. Thus, we handle the authentication
    # by redirecting the user to the registry. This ensures the authorization
    # will be granted by a user which has an identity on that registry.
    authenticate_to_provider = False
    if current_user.is_anonymous:
        logger.debug("Current user is anonymous")
        authenticate_to_provider = True
    elif name not in current_user.oauth_identity:
        logger.debug(f"Current user doesn't have an identity issued by the provider '{name}'")
        authenticate_to_provider = True
    elif Token.check_token_expiration(current_user.oauth_identity[name].token['expires_at']):
        logger.debug(f"The current user has expired token issued by the provider '{name}'")
        authenticate_to_provider = True
    logger.debug(f"Authenticate to provider '{name}': {authenticate_to_provider}")
    if authenticate_to_provider:
        return redirect(url_for("oauth2provider.login", name=name,
                                next=url_for(".authorize_provider",
                                             name=name, **request.args.to_dict())))
    return _process_authorization()


def _process_authorization():
    confirmed = None
    if request.method == 'GET':
        grant = server.validate_consent_request(end_user=current_user)
        if not server.request_authorization(grant.client, current_user):
            # granted by resource owner
            return server.create_authorization_response(grant_user=current_user)
        confirmed = bool_from_string(request.values.get('confirm', ''))
        logger.debug("Confirm authorization [GET]: %r", confirmed)
        if not confirmed:
            return render_template(
                'authorize.html',
                grant=grant,
                user=current_user,
                scope_info=OpenApiSpecs.get_instance().all_scopes
            )
    elif request.method == 'POST':
        form = AuthorizeClient()
        logger.debug(form.confirm.data)
        confirmed = form.confirm.data
        logger.debug("Confirm authorization [POST]: %r", confirmed)
    # handle client response
    if confirmed:
        logger.debug("Authorization confirmed")
        # granted by resource owner
        return server.create_authorization_response(grant_user=current_user)
    # denied by resource owner
    return server.create_authorization_response(grant_user=None)


@blueprint.route('/token', methods=['POST'])
def issue_token():
    return server.create_token_response()


# @blueprint.route('/create_client', methods=('GET', 'POST'))
@login_required
def create_client():
    user = current_user
    if not user:
        return redirect('/login')
    if request.method == 'GET':
        return render_template('create_client.html')

    form = request.form
    client = server.create_client(user,
                                  form["client_name"], form["client_uri"],
                                  split_by_crlf(form["grant_type"]),
                                  split_by_crlf(form["response_type"]),
                                  form["scope"],
                                  split_by_crlf(form["redirect_uri"]),
                                  form["token_endpoint_auth_method"]
                                  )
    return jsonify({
        "client_id": client.client_id,
        "client_secret": client.client_secret
    })
