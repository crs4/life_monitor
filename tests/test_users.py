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

import logging
import pytest
from flask import g

from .conftest import ClientAuthenticationMethod
from .utils import assert_properties_exist

logger = logging.getLogger()


def test_user1(user1):
    assert "user" not in g, "Ops"
    logger.debug("USER 1: %r", user1)
    assert_properties_exist(['user', 'user_info', 'workflows'], user1)
    assert len(user1['workflows']) == 5, "Unexpected number of workflows for user1"
    wfs = [w['name'] for w in user1['workflows']]
    for p in ['basefreqsum', 'sort-and-change-case',
              'sort-and-change-case-invalid-service-url',
              'sort-and-change-case-invalid-service-type']:
        assert p in wfs, f"Expected workflow '{p}'not found"


def test_user2(user2):
    assert "user" not in g, "Ops"
    logger.debug("USER 2: %r", user2)
    assert_properties_exist(['user', 'user_info', 'workflows'], user2)
    assert len(user2['workflows']) == 2, "Unexpected number of workflows for user2"


@pytest.mark.parametrize("client_auth_method", [
    ClientAuthenticationMethod.NOAUTH,
    ClientAuthenticationMethod.BASIC,
    ClientAuthenticationMethod.API_KEY,
    ClientAuthenticationMethod.AUTHORIZATION_CODE,
    ClientAuthenticationMethod.CLIENT_CREDENTIALS,
    ClientAuthenticationMethod.REGISTRY_CODE_FLOW
], indirect=True)
def test_user1_auth(user1, client_auth_method, user1_auth):
    logger.debug("Auth: %r, %r, %r", user1_auth, client_auth_method, ClientAuthenticationMethod.BASIC.value)
    if client_auth_method in [ClientAuthenticationMethod.NOAUTH,
                              ClientAuthenticationMethod.BASIC]:
        assert "ApiKey" not in user1_auth
        assert "Authorization" not in user1_auth
    elif client_auth_method == ClientAuthenticationMethod.API_KEY:
        assert "ApiKey" in user1_auth
    else:
        assert "Bearer" in user1_auth['Authorization']


@pytest.mark.parametrize("client_auth_method", [
    ClientAuthenticationMethod.NOAUTH,
    ClientAuthenticationMethod.BASIC,
    ClientAuthenticationMethod.API_KEY,
    ClientAuthenticationMethod.AUTHORIZATION_CODE
], indirect=True)
def test_user_auto_logout(app_client, user1, client_auth_method, user1_auth):
    logger.debug("Auth: %r, %r, %r", user1_auth, client_auth_method, ClientAuthenticationMethod.BASIC.value)

    r1 = app_client.get('/users/current', headers=user1_auth)
    if client_auth_method in [ClientAuthenticationMethod.NOAUTH, ClientAuthenticationMethod.BASIC]:
        assert r1.status_code == 401, "Expected 401 status code"
    else:
        assert r1.status_code == 200, "Expected 200 status code"
        logger.debug("Response R1: %r", r1.json)

    r2 = app_client.get('/users/current')
    assert r2.status_code == 401, "Expected 401 status code"
