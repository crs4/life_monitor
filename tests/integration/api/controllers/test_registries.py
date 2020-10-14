import json
import logging
import pytest

from tests import utils
from tests.conftest_types import ClientAuthenticationMethod


logger = logging.getLogger()


@pytest.mark.parametrize("client_auth_method", [
    #    ClientAuthenticationMethod.BASIC,
    ClientAuthenticationMethod.API_KEY,
    ClientAuthenticationMethod.AUTHORIZATION_CODE,
    ClientAuthenticationMethod.CLIENT_CREDENTIALS,
    ClientAuthenticationMethod.REGISTRY_CODE_FLOW
], indirect=True)
def test_get_registries(app_client, client_auth_method, user1, user1_auth):
    response = app_client.get(utils.build_registries_path(), headers=user1_auth)
    utils.assert_status_code(200, response.status_code)
    assert response.data, "Empty response"
    data = json.loads(response.data)
    logger.debug("Response %r", data)
    assert len(data['items']) == 1, "Invalid number of registries"


def test_get_registries_no_authorization(app_client, fake_registry):
    response = app_client.get(utils.build_registries_path())
    utils.assert_status_code(200, response.status_code)
    assert response.data, "Empty response"
    data = json.loads(response.data)
    logger.debug("Response %r", data)
    assert len(data['items']) == 2, "Invalid number of registries"


@pytest.mark.parametrize("client_auth_method", [
    ClientAuthenticationMethod.CLIENT_CREDENTIALS,
    ClientAuthenticationMethod.REGISTRY_CODE_FLOW
], indirect=True)
def test_get_registry(app_client, client_credentials_registry,
                      client_auth_method, user1, user1_auth):
    response = app_client.get(utils.build_registries_path('current'), headers=user1_auth)
    utils.assert_status_code(200, response.status_code)
    assert response.data, "Empty response"
    data = json.loads(response.data)
    logger.debug("Response %r", data)
    utils.assert_properties_exist(['uuid', 'name', 'uri'], data)
    assert data['uuid'] == str(client_credentials_registry.uuid), \
        "Unexpected workflow registry"


@pytest.mark.parametrize("client_auth_method", [
    ClientAuthenticationMethod.API_KEY,
    ClientAuthenticationMethod.AUTHORIZATION_CODE,
    ClientAuthenticationMethod.CLIENT_CREDENTIALS,
    ClientAuthenticationMethod.REGISTRY_CODE_FLOW
], indirect=True)
def test_get_registry_by_uuid(app_client, client_credentials_registry,
                              client_auth_method, user1, user1_auth):
    response = app_client.get(utils.build_registries_path(
        client_credentials_registry.uuid), headers=user1_auth)
    utils.assert_status_code(200, response.status_code)
    assert response.data, "Empty response"
    data = json.loads(response.data)
    logger.debug("Response %r", data)
    utils.assert_properties_exist(['uuid', 'name', 'uri'], data)
    assert data['uuid'] == str(client_credentials_registry.uuid), \
        "Unexpected workflow registry"


def test_get_registry_by_uuid_not_authorized(app_client, random_valid_uuid):
    response = app_client.get(utils.build_registries_path(random_valid_uuid))
    utils.assert_status_code(401, response.status_code)


@pytest.mark.parametrize("client_auth_method", [
    ClientAuthenticationMethod.API_KEY,
    ClientAuthenticationMethod.AUTHORIZATION_CODE,
    ClientAuthenticationMethod.CLIENT_CREDENTIALS,
    ClientAuthenticationMethod.REGISTRY_CODE_FLOW
], indirect=True)
def test_get_registry_by_uuid_not_found(app_client, random_valid_uuid,
                                        client_auth_method, user1, user1_auth):
    response = app_client.get(
        utils.build_registries_path(random_valid_uuid), headers=user1_auth)
    utils.assert_status_code(404, response.status_code)


@pytest.mark.parametrize("client_auth_method", [
    ClientAuthenticationMethod.API_KEY,
    ClientAuthenticationMethod.AUTHORIZATION_CODE
], indirect=True)
def test_get_registry_not_authorized(app_client, client_credentials_registry,
                                     client_auth_method, user1, user1_auth):
    response = app_client.get(utils.build_registries_path('current'), headers=user1_auth)
    utils.assert_status_code(401, response.status_code)
