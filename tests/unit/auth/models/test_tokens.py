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
import time
from unittest.mock import PropertyMock, patch

import pytest
from lifemonitor.auth.oauth2.client.models import OAuth2Token

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger()


@pytest.fixture
def user_identity(app_client, user1, provider_type):
    logger.debug(user1.keys())
    logger.debug(user1['user_info'].keys())
    user = user1['user']
    logger.debug(user)
    logger.debug(provider_type.value)
    identity = user.oauth_identity[provider_type.value]
    assert identity, f"Unable to find user identity on provider {provider_type.value}"
    logger.debug(identity)
    return identity


@patch("lifemonitor.auth.oauth2.client.models.OAuthIdentity.fetch_token")
def test_fetch_token_call_on_user_info(fetch_token_method, user_identity):
    logger.debug(user_identity)
    # reset user_info on the current identity instance
    user_identity._user_info = None
    user_info = user_identity.user_info
    logger.debug("user_info: %r", user_info)
    assert user_info, "Unable to get user info"
    fetch_token_method.assert_called_once()


@patch("lifemonitor.auth.oauth2.client.models.OAuthIdentity.fetch_token")
def test_fetch_token_call_on_as_http_header(fetch_token_method, user_identity):
    logger.debug(user_identity)
    # reset user_info on the current identity instance
    user_identity._user_info = None
    header = user_identity.as_http_header()
    logger.debug("as header: %r", header)
    assert header, "Unable to convert identity to HTTP header"
    fetch_token_method.assert_called_once()


@patch("lifemonitor.auth.oauth2.client.models.OAuth2Token.to_be_refreshed")
def test_fetch_token_on_token_not_expired(check_token, user_identity):
    logger.debug(user_identity)
    current_token = user_identity.token
    logger.debug("Current token: %r", current_token)
    check_token.return_value = False
    fetched_token = user_identity.fetch_token()
    logger.debug("Fetched token: %r", fetched_token)
    check_token.assert_called_once()
    assert fetched_token == current_token, "DB and fetched tokens should be equal"


@patch("lifemonitor.auth.oauth2.client.models.OAuth2Token.to_be_refreshed")
def test_fetch_token_on_token_expired(check_token, user_identity):
    logger.debug(user_identity)
    current_token = user_identity.token
    logger.debug("Current token: %r", current_token)
    check_token.return_value = True
    time.sleep(1)
    fetched_token = user_identity.fetch_token()
    logger.debug("Fetched token: %r", fetched_token)
    assert check_token.call_count == 3, "Unexpected number of call for method 'to_be_refreshed'"
    assert fetched_token != current_token, "DB and fetched tokens should not be equal"
    assert fetched_token['created_at'] > current_token['created_at'], \
        "Refreshed token should be more recent"


@patch("lifemonitor.auth.oauth2.client.models.OAuthIdentity.token", new_callable=PropertyMock)
def test_fetch_token_on_not_refreshable_token_expired(token_property, user_identity):
    logger.debug(user_identity)
    # remove the refresh token from the current token
    token = user_identity._token
    token['expires_at'] = token['created_at']
    del token['refresh_token']
    token = OAuth2Token(token)
    token_property.return_value = token
    current_token = user_identity.token
    logger.debug("Current token: %r -- to be refreshed: %r", current_token, current_token.to_be_refreshed())
    fetched_token = user_identity.fetch_token()
    logger.debug("Fetched token: %r", fetched_token)
    assert fetched_token == current_token, "DB and fetched tokens should be equal"
