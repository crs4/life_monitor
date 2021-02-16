from functools import wraps
import logging

# Config a module level logger
import secrets
import flask_login
from flask import g, request, url_for

from werkzeug.local import LocalProxy
from werkzeug.wrappers import Response
from lifemonitor.lang import messages
from lifemonitor.exceptions import LifeMonitorException
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
    @wraps(func)
    def wrapper(*args, **kwargs):
        logger.debug(f"The current user: {current_user}")
        logger.debug(f"The current registry: {current_registry}")
        logger.debug(f"Request args: {request.args}")
        validation = False
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
                                              name="seek", next=request.url))
            # check if the token issued by the registry is valid
            identity = current_user.oauth_identity[current_registry.name]
            from .oauth2.client.controllers import AuthorizatonHandler
            validation = AuthorizatonHandler.handle_validation(identity)
            if isinstance(validation, Response):
                return validation
            elif validation is False:
                raise NotAuthorizedException(
                    detail=messages.unauthorized_user_with_expired_registry_token.format(
                        current_registry.name, current_registry.name),
                    authorization_url=url_for('oauth2provider.authorize',
                                              name="seek", next=request.url))
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
