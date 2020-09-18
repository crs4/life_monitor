import logging
from flask import g
from connexion.exceptions import OAuthProblem
from flask_login import login_user

from lifemonitor.auth.oauth2.server.models import Token
from lifemonitor.auth.oauth2.server.models import AuthorizationServer

# Set the module level logger
logger = logging.getLogger(__name__)

# Instantiate the OAuth server
server = AuthorizationServer()


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

    # only if the token has been issued to a user
    # the user has to be automatically logged in
    logger.debug("The token user: %r", token.user)
    if token.user:
        login_user(token.user)
    # store the current client
    g.oauth2client = token.client
    # if the client is a Registry, store it on the current session
    from lifemonitor.api.models import WorkflowRegistry
    registry = WorkflowRegistry.find_by_client_id(token.client.client_id)
    logger.debug("Token issued to a WorkflowRegistry: %r", registry is not None)
    if registry:
        g.workflow_registry = registry
    return {
        "scope": token.scope
    }
