import logging

import flask
from authlib.integrations.base_client import RemoteApp

from flask import Blueprint, request, redirect, url_for, flash, render_template, jsonify
from flask_login import login_required, login_user, logout_user, current_user
from sqlalchemy.orm.exc import NoResultFound

from .models import db, User, OAuthIdentity
# from .oauth2.client.models import OAuth
from .forms import RegisterForm, LoginForm, SetPasswordForm

# Config a module level logger
from .oauth2.client import oauth2_registry
from .oauth2.client.models import OAuthUserProfile

logger = logging.getLogger(__name__)

blueprint = Blueprint("auth", __name__,
                      template_folder='templates',
                      static_folder="static", static_url_path='/static/auth')


@blueprint.route("/", methods=("GET",))
def index():
    return render_template("auth/profile.j2")


@blueprint.route("/profile", methods=("GET",))
def profile():
    return render_template("auth/profile.j2")


@blueprint.route("/register", methods=("GET", "POST"))
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        user = form.create_user()
        if user:
            login_user(user)
            flash("Account created")
            return redirect(url_for("auth.index"))
    return render_template("auth/register.j2", form=form)


@blueprint.route("/login/", methods=("GET", "POST"))
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = form.get_user()
        if user:
            login_user(user)
            flash("You have logged in")
            return redirect(url_for("auth.index"))
    return render_template("auth/login.j2", form=form)


@blueprint.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have logged out")
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


def handle_authorize(provider: RemoteApp, token, user_info: OAuthUserProfile):
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
                url = url_for("auth.merge", provider=identity.provider, username=identity.user.username)
                return redirect(url)
        # If the user is logged in and the token is unlinked or linked yet,
        # link the token to the current user
        identity.user = current_user
        identity.save()
        flash("Successfully linked GitHub account.")

    logger.debug(user_info)
    next_url = flask.request.args.get('next')
    return redirect(next_url or '/')
