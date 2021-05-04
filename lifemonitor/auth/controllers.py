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

import flask
from flask import flash, redirect, render_template, request, url_for
from flask_login import login_required, login_user, logout_user
from lifemonitor.utils import (NextRouteRegistry, next_route_aware,
                               split_by_crlf)

from .. import exceptions
from ..utils import OpenApiSpecs
from . import serializers
from .forms import LoginForm, Oauth2ClientForm, RegisterForm, SetPasswordForm
from .models import db
from .oauth2.client.services import (get_current_user_identity, get_providers,
                                     merge_users, save_current_user_identity)
from .oauth2.server.services import server
from .services import (authorized, current_registry, current_user,
                       delete_api_key, generate_new_api_key, login_manager)

# Config a module level logger
logger = logging.getLogger(__name__)

blueprint = flask.Blueprint("auth", __name__,
                            template_folder='templates',
                            static_folder="static", static_url_path='/static')

# Set the login view
login_manager.login_view = "auth.login"


@authorized
def show_current_user_profile():
    try:
        if current_user and not current_user.is_anonymous:
            return serializers.UserSchema().dump(current_user)
        raise exceptions.Forbidden(detail="Client type unknown")
    except Exception as e:
        return exceptions.report_problem_from_exception(e)


@authorized
def get_registry_users():
    try:
        if current_registry and current_user.is_anonymous:
            try:
                return serializers.ListOfUsers().dump(current_registry.users)
            except Exception as e:
                logger.exception(e)
                return {'items': []}
        raise exceptions.Forbidden(detail="Client type unknown")
    except Exception as e:
        return exceptions.report_problem_from_exception(e)


@authorized
def get_registry_user(user_id):
    try:
        if current_registry:
            return serializers.UserSchema().dump(current_registry.get_user(user_id))
        raise exceptions.Forbidden(detail="Client type unknown")
    except Exception as e:
        return exceptions.report_problem_from_exception(e)


@blueprint.route("/", methods=("GET",))
def index():
    return redirect(url_for('auth.profile'))


@blueprint.route("/profile", methods=("GET",))
def profile(form=None, passwordForm=None, currentView=None):
    currentView = currentView or request.args.get("currentView", 'accountsTab')
    logger.debug(OpenApiSpecs.get_instance().authorization_code_scopes)
    return render_template("auth/profile.j2",
                           passwordForm=passwordForm or SetPasswordForm(),
                           oauth2ClientForm=form or Oauth2ClientForm(),
                           providers=get_providers(), currentView=currentView,
                           oauth2_generic_client_scopes=OpenApiSpecs.get_instance().authorization_code_scopes)


@blueprint.route("/register", methods=("GET", "POST"))
def register():
    if flask.request.method == "GET":
        # properly intialize/clear the session before the registration
        flask.session["confirm_user_details"] = True
        save_current_user_identity(None)
    with db.session.no_autoflush:
        form = RegisterForm()
        if form.validate_on_submit():
            user = form.create_user()
            if user:
                login_user(user)
                flash("Account created", category="success")
                return redirect(url_for("auth.index"))
        return render_template("auth/register.j2", form=form,
                               action='/register', providers=get_providers())


@blueprint.route("/register_identity", methods=("GET", "POST"))
def register_identity():
    with db.session.no_autoflush:
        identity = get_current_user_identity()
        logger.debug("Current provider identity: %r", identity)
        if not identity:
            flash("Unable to register the user")
            flask.abort(400)
        logger.debug("Provider identity on session: %r", identity)
        logger.debug("User Info: %r", identity.user_info)
        user = identity.user
        form = RegisterForm()
        if form.validate_on_submit():
            user = form.create_user(identity)
            if user:
                login_user(user)
                flash("Account created", category="success")
                return redirect(url_for("auth.index"))
        return render_template("auth/register.j2", form=form, action='/register_identity',
                               identity=identity, user=user, providers=get_providers())


@blueprint.route("/login", methods=("GET", "POST"))
@next_route_aware
def login():
    form = LoginForm()
    flask.session["confirm_user_details"] = True
    if form.validate_on_submit():
        user = form.get_user()
        if user:
            login_user(user)
            flash("You have logged in", category="success")
            return redirect(NextRouteRegistry.pop(url_for("auth.index")))
    return render_template("auth/login.j2", form=form, providers=get_providers())


@blueprint.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have logged out", category="success")
    NextRouteRegistry.clear()
    return redirect(url_for("auth.index"))


@blueprint.route("/set_password", methods=("GET", "POST"))
@login_required
def set_password():
    form = SetPasswordForm()
    if form.validate_on_submit():
        current_user.password = form.password.data
        db.session.add(current_user)
        db.session.commit()
        flash("Password set successfully")
        return redirect(url_for("auth.profile"))
    return profile(passwordForm=form)


@blueprint.route("/merge", methods=("GET", "POST"))
@login_required
def merge():
    form = LoginForm(data={
        "username": request.args.get("username"),
        "provider": request.args.get("provider")})
    if form.validate_on_submit():
        user = form.get_user()
        if user:
            if user != current_user:
                merge_users(current_user, user, request.args.get("provider"))
                flash(
                    "User {username} has been merged into your account".format(
                        username=user.username
                    )
                )
                return redirect(url_for("auth.index"))
            else:
                form.username.errors.append("Cannot merge with yourself")
    return render_template("auth/merge.j2", form=form)


@blueprint.route("/create_apikey", methods=("POST",))
@login_required
def create_apikey():
    apikey = generate_new_api_key(
        current_user, " ".join(OpenApiSpecs.get_instance().apikey_scopes.keys()))
    if apikey:
        logger.debug("Created a new API key: %r", apikey)
        flash("API key created!", category="success")
    else:
        flash("API key not created!", category="error")
    return redirect(url_for('auth.profile', currentView='apiKeysTab'))


@blueprint.route("/delete_apikey", methods=("POST",))
@login_required
def delete_apikey():
    apikey = request.values.get('apikey', None)
    logger.debug(request.values)
    if not apikey:
        flash("Unable to find the API key")
    else:
        delete_api_key(current_user, apikey)
        flash("API key removed!", category="success")
    return redirect(url_for('auth.profile', currentView='apiKeysTab'))


@blueprint.route('/oauth2/clients/save', methods=('POST',))
@login_required
def save_generic_code_flow_client():
    if request.method == "GET":
        return redirect(url_for('auth.profile', currentView='oauth2ClientsTab'))

    form = Oauth2ClientForm(auth_method="client_secret_post")
    if request.method == "POST":
        logger.debug("ClientId: %r", form.clientId.data)
        logger.debug("Name: %r", form.name.data)
        logger.debug("URI: %r", form.uri.data)
        logger.debug("Redirect URI: %r", form.redirect_uris.data)
        logger.debug("Scopes: %r", form.scopes.data)
        logger.debug("Confidential: %r", form.confidential.data)
        logger.debug("AuthMethod: %r", form.auth_method.data)

        for scope in form.scopes:
            logger.debug("A scope: %r", scope.data)
        if form.validate_on_submit():
            data = form.get_client_data()
            if not form.clientId.data:
                client = server.create_client(current_user,
                                              data['name'], data['uri'],
                                              'authorization_code', 'code',
                                              data['scopes'],
                                              " ".join(split_by_crlf(data["redirect_uris"])),
                                              data['auth_method'])
                logger.debug("lient created: %r", client)
                flash("App Created", category="success")
            else:
                clientId = request.values.get('clientId', None)
                client = server.get_client(current_user, clientId)
                if not clientId or not client:
                    flash("Invalid ClientID!", category="error")
                    return profile(form=form, currentView="oauth2ClientsTab")
                server.update_client(current_user, client,
                                     data['name'], data['uri'],
                                     'authorization_code', 'code',
                                     data['scopes'],
                                     " ".join(split_by_crlf(data["redirect_uris"])),
                                     data['auth_method'])
                logger.debug("Client updated: %r", client)
                flash("App Updated", category="success")
        else:
            logger.debug("Ops... validation failed")
            return profile(form=form, currentView="oauth2ClientEditorPane")
    return redirect(url_for('auth.profile', currentView='oauth2ClientsTab'))


@blueprint.route('/oauth2/clients/edit', methods=('GET', 'POST'))
@login_required
def edit_generic_code_flow_client():
    if request.method == "GET":
        return redirect(url_for('auth.profile', currentView='oauth2ClientsTab'))

    clientId = request.values.get('clientId', None)
    client = server.get_client(current_user, clientId)
    if not clientId or not client:
        flash("Invalid ClientID!", category="error")
        return profile(form=Oauth2ClientForm(), currentView="oauth2ClientsTab")

    form = Oauth2ClientForm.from_object(client)
    logger.debug("Name: %r", form.name.data)
    logger.debug("URI: %r", form.uri.data)
    logger.debug("Redirect URI: %r", form.redirect_uris.data)
    logger.debug("Scopes: %r", form.scopes.data)
    logger.debug("Confidential: %r", form.confidential.data)
    logger.debug("AuthMethod: %r", form.auth_method.data)
    for scope in form.scopes:
        logger.debug("A scope: %r", scope.data)
    return profile(form=form, currentView="oauth2ClientEditorPane")


@blueprint.route('/oauth2/clients/delete', methods=('GET', 'POST'))
@login_required
def delete_generic_code_flow_client():
    if request.method == "GET":
        return redirect(url_for('auth.profile', currentView='oauth2ClientsTab'))

    clientId = request.values.get('clientId', None)
    if not clientId:
        flash("Invalid ClientID!", category="error")
    result = server.delete_client(current_user, clientId)
    if not result:
        flash("Unable to delete the OAuth App", category="error")
    else:
        flash("App removed!", category="success")
    return redirect(url_for('auth.profile', currentView='oauth2ClientsTab'))
