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

import json
import logging
import pytest

from tests import utils
from tests.conftest_types import ClientAuthenticationMethod


logger = logging.getLogger()


@pytest.mark.parametrize("client_auth_method", [
    ClientAuthenticationMethod.CLIENT_CREDENTIALS
], indirect=True)
def test_get_user_registries(app_client, client_auth_method, user1, user1_auth):
    response = app_client.get(utils.build_users_path(), headers=user1_auth)
    utils.assert_status_code(200, response.status_code)
    assert response.data, "Empty response"
    data = json.loads(response.data)
    logger.debug("Response %r", data)
    assert len(data['items']) == 1, "Invalid number of registries"


@pytest.mark.parametrize("client_auth_method", [
    #    ClientAuthenticationMethod.BASIC,
    ClientAuthenticationMethod.API_KEY,
    ClientAuthenticationMethod.AUTHORIZATION_CODE,
    ClientAuthenticationMethod.REGISTRY_CODE_FLOW
], indirect=True)
def test_get_user_registries_no_authorization(app_client, client_auth_method, user1, user1_auth):
    response = app_client.get(utils.build_users_path(), headers=user1_auth)
    utils.assert_status_code(403, response.status_code)


@pytest.mark.parametrize("client_auth_method", [
    ClientAuthenticationMethod.API_KEY,
    ClientAuthenticationMethod.AUTHORIZATION_CODE,
    ClientAuthenticationMethod.REGISTRY_CODE_FLOW
], indirect=True)
def test_get_current_user(app_client, client_auth_method, user1, user1_auth):
    response = app_client.get(utils.build_users_path('current'), headers=user1_auth)
    utils.assert_status_code(200, response.status_code)
    assert response.data, "Empty response"
    data = json.loads(response.data)
    logger.debug("Response %r", data)
    utils.assert_properties_exist(['username', 'id'], data)


@pytest.mark.parametrize("client_auth_method", [
    ClientAuthenticationMethod.CLIENT_CREDENTIALS
], indirect=True)
def test_get_current_user_no_authorized(app_client, client_auth_method, user1, user1_auth):
    response = app_client.get(utils.build_users_path('current'), headers=user1_auth)
    utils.assert_status_code(403, response.status_code)


@pytest.mark.parametrize("client_auth_method", [
    ClientAuthenticationMethod.CLIENT_CREDENTIALS,
    ClientAuthenticationMethod.REGISTRY_CODE_FLOW
], indirect=True)
def test_get_registry_user(app_client, admin_user,
                           user1, user1_auth):
    response = app_client.get(utils.build_users_path(user1['user'].id), headers=user1_auth)
    utils.assert_status_code(200, response.status_code)
    assert response.data, "Empty response"
    data = json.loads(response.data)
    logger.debug("Response %r", data)
    utils.assert_properties_exist(['username', 'id'], data)


@pytest.mark.parametrize("client_auth_method", [
    ClientAuthenticationMethod.API_KEY,
    ClientAuthenticationMethod.AUTHORIZATION_CODE
], indirect=True)
def test_get_registry_user_no_authorized(app_client, client_auth_method, user1, user1_auth):
    response = app_client.get(utils.build_users_path(user1['user'].id), headers=user1_auth)
    utils.assert_status_code(403, response.status_code)
