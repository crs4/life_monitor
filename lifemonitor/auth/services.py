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

import base64
import logging
import secrets
from functools import wraps

import flask_login
from flask import g, request, url_for
from lifemonitor.auth.models import Anonymous, ApiKey, User
from lifemonitor.exceptions import LifeMonitorException
from lifemonitor.lang import messages
from werkzeug.local import LocalProxy

# Config a module level logger
logger = logging.getLogger(__name__)

# setup login manager
login_manager = flask_login.LoginManager()
login_manager.anonymous_user = Anonymous


class NotAuthorizedException(LifeMonitorException):
    def __init__(self, detail=None,
                 type="about:blank", status=401, instance=None, **kwargs):
        super().__init__(title="Unauthorized",
                         detail=detail, status=status, **kwargs)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


@login_manager.request_loader
def load_user_from_header(_req):
    try:
        header_val = request.headers.get('Authorization', None)
        if "Basic" in header_val:
            header_val = header_val.replace('Basic ', '', 1)
            header_val = base64.b64decode(header_val).decode()
            username, password = header_val.split(':')
            user = User.query.filter_by(username=username).first()
            if user and user.verify_password(password):
                return user
    except TypeError:
        pass
    return None


def login_user(user):
    flask_login.login_user(user)


def logout_user():
    flask_login.logout_user()


def login_registry(registry):
    g.workflow_registry = registry


def logout_registry():
    g.workflow_registry = None


def _current_registry():
    return g.workflow_registry if "workflow_registry" in g else None


current_registry = LocalProxy(lambda: _current_registry())

current_user = flask_login.current_user


def is_user_or_registry_authenticated():
    logger.debug(f"The current user: {current_user}")
    logger.debug(f"The current registry: {current_registry}")
    logger.debug(f"Request args: {request.args}")
    # raise unauthorized if no user nor registry in session
    if not current_registry and current_user.is_anonymous:
        raise NotAuthorizedException(detail=messages.unauthorized_no_user_nor_registry)
    # if there is a registry user in session
    # check whether his token issued by the registry is valid
    if current_registry and not current_user.is_anonymous:
        if current_registry.name not in current_user.oauth_identity:
            raise NotAuthorizedException(
                detail=messages.unauthorized_user_without_registry_identity.format(current_registry.name),
                authorization_url=url_for('oauth2provider.authorize',
                                          name=current_registry.name, next=request.url))


def authorized(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        is_user_or_registry_authenticated()
        return func(*args, **kwargs)
    return wrapper


        return func(*args, **kwargs)
    return wrapper


def generate_new_api_key(user, scope, length=40) -> ApiKey:
    api_key = ApiKey(key=secrets.token_urlsafe(length), user=user, scope=scope)
    api_key.save()
    return api_key


def delete_api_key(user, api_key) -> ApiKey:
    api_key = ApiKey.find(api_key)
    if api_key and api_key.user == user:
        api_key.delete()


def check_api_key(api_key, required_scopes):
    logger.debug("The API Key: %r; scopes required: %r", api_key, required_scopes)
    api_key = ApiKey.find(api_key)
    # start an UnAuthorized exception if the ApiKey is not registered
    if not api_key:
        raise NotAuthorizedException(detail='Invalid ApiKey')
    # check whether all the required scopes are allowed
    logger.debug("%r -- required scopes: %r", api_key, required_scopes)
    if not api_key.check_scopes(required_scopes):
        raise NotAuthorizedException(detail='Invalid scopes')
    # set ApiKey user as the current user
    login_user(api_key.user)
    # return the user_id
    return {'uid': api_key.user.id}
