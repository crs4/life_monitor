import logging

from connexion.exceptions import OAuthProblem
from flask_login import login_user

from lifemonitor.auth.oauth2.server import Token

# Set the module level logger
logger = logging.getLogger(__name__)


def get_token_scopes(access_token):
    """
    The referenced function accepts a token string as argument and
    should return a dict containing a scope field that is either a space-separated list of scopes
    belonging to the supplied token.

    :param access_token:
    :return: a dict containing a scope field that is either a space-separated list of scopes
    belonging to the supplied token.
    """
    token = Token.find(access_token)
    if not token:
        logger.debug("Access token %r not found", access_token)
        raise OAuthProblem("Invalid token")
    logger.debug("Found a token: %r", token)
    # set token user as current logged user
    login_user(token.user)
    return {
        "scope": token.scope
    }
