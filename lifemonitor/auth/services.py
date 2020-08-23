import logging

# Config a module level logger
import secrets

from connexion.exceptions import OAuthProblem
from flask_login import login_user, LoginManager

from lifemonitor.auth.models import ApiKey, User, Anonymous

logger = logging.getLogger(__name__)

# setup login manager
login_manager = LoginManager()
login_manager.anonymous_user = Anonymous


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


def generate_new_api(user, scope, length=40) -> ApiKey:
    api_key = ApiKey(key=secrets.token_urlsafe(length), user=user, scope=scope)
    api_key.save()
    return api_key


def check_api_key(api_key, required_scopes):
    logger.debug("The API Key: %r; scopes required: %r", api_key, required_scopes)
    api_key = ApiKey.find(api_key)
    # start an UnAuthorized exception if the ApiKey is not registered
    if not api_key:
        raise OAuthProblem('Invalid ApiKey')
    # check whether all the required scopes are allowed
    logger.debug("%r -- required scopes: %r", api_key, required_scopes)
    if not api_key.check_scopes(required_scopes):
        raise OAuthProblem('Invalid scopes')
    # set ApiKey user as the current user
    login_user(api_key.user)
    # return the user_id
    return {'uid': api_key.user.id}
