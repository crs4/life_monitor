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
from lifemonitor.utils import NextRouteRegistry, next_route_aware

from .. import exceptions
from . import serializers
from .forms import LoginForm, RegisterForm, SetPasswordForm
from .models import db
from .oauth2.client.services import (get_current_user_identity, get_providers,
                                     merge_users)
from .services import (authorized, current_registry, current_user,
                       delete_api_key, generate_new_api_key, login_manager)

# Config a module level logger
logger = logging.getLogger(__name__)

blueprint = flask.Blueprint("auth", __name__,
                            template_folder='templates',
                            static_folder="static", static_url_path='/static/auth')

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
            return serializers.UserSchema().dump(current_registry.users, many=True)
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
    return render_template("auth/profile.j2", providers=get_providers())


@blueprint.route("/profile", methods=("GET",))
def profile():
    return render_template("auth/profile.j2", providers=get_providers())


@blueprint.route("/register", methods=("GET", "POST"))
def register():
    with db.session.no_autoflush:
        identity = get_current_user_identity()
        logger.debug("Current provider identity: %r", identity)
        user = current_user
        if identity:
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
        return render_template("auth/register.j2", form=form,
                               identity=identity, user=user, providers=get_providers())


@blueprint.route("/login", methods=("GET", "POST"))
@next_route_aware
def login():
    form = LoginForm()
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
        return redirect(url_for("auth.index"))
    return render_template("auth/set_password.j2", form=form)


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
    apikey = generate_new_api_key(current_user, 'read write')
    if apikey:
        logger.debug("Created a new API key: %r", apikey)
        flash("API key created!", category="success")
    else:
        flash("API key not created!", category="error")
    return redirect(url_for('auth.profile'))


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
    return redirect(url_for('auth.profile'))
