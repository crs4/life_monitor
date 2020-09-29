import logging

# Config a module level logger
import secrets
import flask_login
from flask import g

from werkzeug.local import LocalProxy
from lifemonitor.common import LifeMonitorException
from lifemonitor.auth.models import ApiKey, User, Anonymous

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


def authorized(func):
    def wrapper(*args, **kwargs):
        if not current_registry and current_user.is_anonymous:
            raise NotAuthorizedException(detail="No user nor registry found in the current session")
        return func(*args, **kwargs)
    return wrapper


def generate_new_api_key(user, scope, length=40) -> ApiKey:
    api_key = ApiKey(key=secrets.token_urlsafe(length), user=user, scope=scope)
    api_key.save()
    return api_key


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
