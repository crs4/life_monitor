from __future__ import unicode_literals
import os
from flask_dance.consumer import OAuth2ConsumerBlueprint, oauth_error
from functools import partial
from flask import flash, url_for, redirect, current_app
from flask_login import current_user, login_user
from flask.globals import LocalProxy, _lookup_app_object
from flask_dance.consumer import oauth_authorized, oauth_error
from flask_dance.consumer.storage.sqla import SQLAlchemyStorage
from sqlalchemy.orm.exc import NoResultFound
from lifemonitor.auth.models import db, User
from lifemonitor.auth.oauth2.client.models import OAuth

try:
    from flask import _app_ctx_stack as stack
except ImportError:
    from flask import _request_ctx_stack as stack


class SeekOAuth2ConsumerBlueprint(OAuth2ConsumerBlueprint):

    def __init__(self,
                 client_id=None, client_secret=None, client=None,
                 auto_refresh_url=None, auto_refresh_kwargs=None,
                 scope="read", state=None, static_folder=None, static_url_path=None,
                 template_folder=None, url_prefix=None, subdomain=None,
                 url_defaults=None, root_path=None, login_url=None, authorized_url=None,
                 base_url=None,
                 authorization_url=None, authorization_url_params=None,
                 token_url=None, token_url_params=None,
                 redirect_url=None, redirect_to=None,
                 session_class=None, storage=None, **kwargs):
        super().__init__("seek", __name__,
                         client_id, client_secret, client,
                         auto_refresh_url, auto_refresh_kwargs,
                         scope, state,
                         static_folder, static_url_path,
                         template_folder,
                         url_prefix, subdomain, url_defaults, root_path, login_url,
                         authorized_url, base_url,
                         authorization_url, authorization_url_params,
                         token_url, token_url_params,
                         redirect_url, redirect_to,
                         session_class, storage, **kwargs)

        self.from_config["client_id"] = "SEEK_OAUTH_CLIENT_ID"
        self.from_config["client_secret"] = "SEEK_OAUTH_CLIENT_SECRET"

    def load_config(self):
        base_url = current_app.config.get("SEEK_OAUTH_API_BASE_URL")
        self.base_url = base_url
        self.authorization_url = os.path.join(base_url, "oauth/authorize")
        self.token_url = os.path.join(base_url, "oauth/token")
        super().load_config()


seek = LocalProxy(partial(_lookup_app_object, "seek_oauth"))

blueprint = SeekOAuth2ConsumerBlueprint(
    storage=SQLAlchemyStorage(OAuth, db.session, user=current_user)
)


@blueprint.before_app_request
def set_applocal_session():
    ctx = stack.top
    ctx.seek_oauth = blueprint.session


# create/login local user on successful OAuth login
@oauth_authorized.connect_via(blueprint)
def seek_logged_in(blueprint, token):
    if not token:
        flash("Failed to log in with Seek.", category="error")
        return

    resp = blueprint.session.get("/people/current?format=json")
    if not resp.ok:
        msg = "Failed to fetch user info from Seek."
        flash(msg, category="error")
        return

    seek_info = resp.json()["data"]
    seek_user_id = str(seek_info["id"])

    # TODO: check if it is possible to get the username
    provider_username = seek_info["attributes"]["title"]

    # Find this OAuth token in the database, or create it
    query = OAuth.query.filter_by(
        provider=blueprint.name, provider_user_id=seek_user_id
    )
    try:
        oauth = query.one()
    except NoResultFound:
        seek_user_login = str(provider_username)
        oauth = OAuth(
            provider=blueprint.name,
            provider_user_id=seek_user_id,
            provider_user_login=seek_user_login,
            token=token,
        )

    # Now, figure out what to do with this token. There are 2x2 options:
    # user login state and token link state.
    if current_user.is_anonymous:
        if oauth.user:
            # If the user is not logged in and the token is linked,
            # log the user into the linked user account
            login_user(oauth.user)
            flash("Successfully signed in with Seek.")
        else:
            # If the user is not logged in and the token is unlinked,
            # create a new local user account and log that account in.
            # This means that one person can make multiple accounts, but it's
            # OK because they can merge those accounts later.
            user = User(username=provider_username)
            oauth.user = user
            db.session.add_all([user, oauth])
            db.session.commit()
            login_user(user)
            flash("Successfully signed in with Seek.")
    else:
        if oauth.user:
            # If the user is logged in and the token is linked, check if these
            # accounts are the same!
            if current_user != oauth.user:
                # Account collision! Ask user if they want to merge accounts.
                url = url_for("auth.merge", username=oauth.user.username)
                return redirect(url)
        else:
            # If the user is logged in and the token is unlinked,
            # link the token to the current user
            oauth.user = current_user
            db.session.add(oauth)
            db.session.commit()
            flash("Successfully linked Seek account.")

    # Indicate that the backend shouldn't manage creating the OAuth object
    # in the database, since we've already done so!
    return False


# notify on OAuth provider error
@oauth_error.connect_via(blueprint)
def seek_error(blueprint, message, response):
    msg = ("OAuth error from {name}! " "message={message} response={response}").format(
        name=blueprint.name, message=message, response=response
    )
    flash(msg, category="error")
