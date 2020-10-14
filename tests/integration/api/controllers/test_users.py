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
