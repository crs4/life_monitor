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
from flask import g
from lifemonitor.auth.oauth2.server.models import Token, AuthorizationServer
import lifemonitor.auth.services as auth_services


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
        raise auth_services.NotAuthorizedException(detail="Invalid token")
    logger.debug("Found a token: %r", token)

    # only if the token has been issued to a user
    # the user has to be automatically logged in
    logger.debug("The token user: %r", token.user)
    if token.user:
        auth_services.login_user(token.user)
    # store the current client
    g.oauth2client = token.client
    # if the client is a Registry, store it on the current session
    from lifemonitor.api.models import WorkflowRegistry
    registry = WorkflowRegistry.find_by_client_id(token.client.client_id)
    logger.debug("Token issued to a WorkflowRegistry: %r", registry is not None)
    if registry:
        auth_services.login_registry(registry)
    return {
        "scope": token.scope
    }
