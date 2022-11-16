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

import json
import logging

import pytest
from lifemonitor.api import models
from tests import utils
from tests.conftest_types import ClientAuthenticationMethod

logger = logging.getLogger()


@pytest.mark.parametrize("client_auth_method", [
    ClientAuthenticationMethod.CLIENT_CREDENTIALS
], indirect=True)
def test_get_user_registries(app_client, client_auth_method, user1, user1_auth):
    response = app_client.get(utils.build_registry_users_path(), headers=user1_auth)
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
    response = app_client.get(utils.build_registry_users_path(), headers=user1_auth)
    if client_auth_method == ClientAuthenticationMethod.API_KEY:
        utils.assert_status_code(401, response.status_code)
    else:
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
    ClientAuthenticationMethod.API_KEY,
    ClientAuthenticationMethod.AUTHORIZATION_CODE
], indirect=True)
def test_get_registry_user_no_authorized(app_client, client_auth_method, user1, user1_auth):
    response = app_client.get(utils.build_registry_users_path(), headers=user1_auth)
    if client_auth_method == ClientAuthenticationMethod.API_KEY:
        utils.assert_status_code(401, response.status_code)
    else:
        utils.assert_status_code(403, response.status_code)


@pytest.mark.parametrize("client_auth_method", [
    #    ClientAuthenticationMethod.BASIC,
    ClientAuthenticationMethod.API_KEY,
    ClientAuthenticationMethod.AUTHORIZATION_CODE,
], indirect=True)
def test_empty_workflows(app_client, client_auth_method, user1, user1_auth):
    response = app_client.get(utils.build_workflow_path(), headers=user1_auth)
    utils.assert_status_code(200, response.status_code)
    assert response.data, "Empty response"
    data = json.loads(response.data)
    logger.debug("Response %r", data)
    assert len(data['items']) == 0, "Invalid number of workflows"


@pytest.mark.parametrize("client_auth_method", [
    ClientAuthenticationMethod.API_KEY,
    ClientAuthenticationMethod.AUTHORIZATION_CODE,
], indirect=True)
def test_generic_workflow_registration(app_client, client_auth_method,
                                       user1, user1_auth, client_credentials_registry, generic_workflow):
    logger.debug("User: %r", user1)
    logger.debug("headers: %r", user1_auth)
    workflow = generic_workflow
    logger.debug("Selected workflow: %r", workflow)
    logger.debug("Using oauth2 user: %r", user1)
    # prepare body
    body = {'roc_link': workflow['roc_link'],
            'version': workflow['version'],
            'uuid': workflow['uuid'],
            'authorization': workflow['authorization']}
    logger.debug("The BODY: %r", body)
    response = app_client.post('/users/current/workflows', json=body, headers=user1_auth)
    logger.debug("The actual response: %r", response.data)
    utils.assert_status_code(201, response.status_code)
    data = json.loads(response.data)
    logger.debug("Response data: %r", data)
    assert data['uuid'] == workflow['uuid'] and data['wf_version'] == workflow['version'], \
        "Response should be equal to the workflow UUID"


@pytest.mark.parametrize("client_auth_method", [
    ClientAuthenticationMethod.API_KEY,
], indirect=True)
def test_generic_workflow_registration_with_encoded_rocrate(
        app_client, client_auth_method, user1, user1_auth,
        client_credentials_registry, encoded_rocrate_workflow):
    logger.debug("User: %r", user1)
    logger.debug("headers: %r", user1_auth)
    workflow = encoded_rocrate_workflow
    logger.debug("Selected workflow: %r", workflow)
    logger.debug("Using oauth2 user: %r", user1)
    # prepare body
    body = {'rocrate': workflow['rocrate'],
            'version': workflow['version'],
            'uuid': workflow['uuid'],
            'authorization': workflow['authorization']}
    logger.debug("The BODY: %r", body)
    response = app_client.post('/users/current/workflows', json=body, headers=user1_auth)
    logger.debug("The actual response: %r", response.data)
    utils.assert_status_code(201, response.status_code)
    data = json.loads(response.data)
    logger.debug("Response data: %r", data)
    assert data['uuid'] == workflow['uuid'] and data['wf_version'] == workflow['version'], \
        "Response should be equal to the workflow UUID"


@pytest.mark.parametrize("client_auth_method", [
    ClientAuthenticationMethod.API_KEY,
    ClientAuthenticationMethod.AUTHORIZATION_CODE,
], indirect=True)
def test_generic_workflow_registration_wo_uuid(app_client, client_auth_method,
                                               user1, user1_auth, client_credentials_registry, generic_workflow):
    logger.debug("User: %r", user1)
    logger.debug("headers: %r", user1_auth)
    workflow = generic_workflow
    logger.debug("Selected workflow: %r", workflow)
    logger.debug("Using oauth2 user: %r", user1)
    # prepare body
    body = {'roc_link': workflow['roc_link'],
            'version': workflow['version'],
            'authorization': workflow['authorization']}
    logger.debug("The BODY: %r", body)
    response = app_client.post('/users/current/workflows', json=body, headers=user1_auth)
    logger.debug("The actual response: %r", response.data)
    utils.assert_status_code(201, response.status_code)
    data = json.loads(response.data)
    logger.debug("Response data: %r", data)
    assert data['wf_version'] == workflow['version'], \
        "Response should be equal to the workflow UUID"
    assert data['uuid'], "Workflow UUID was not generated or returned"


@pytest.mark.parametrize("client_auth_method", [
    ClientAuthenticationMethod.API_KEY,
    ClientAuthenticationMethod.AUTHORIZATION_CODE,
], indirect=True)
def test_generic_workflow_registration_no_name_exception(app_client, client_auth_method,
                                                         user1, user1_auth, client_credentials_registry, workflow_no_name):
    logger.debug("User: %r", user1)
    logger.debug("headers: %r", user1_auth)
    workflow = workflow_no_name
    logger.debug("Selected workflow: %r", workflow)
    logger.debug("Using oauth2 user: %r", user1)
    # prepare body
    body = {'roc_link': workflow['roc_link'],
            'version': workflow['version'],
            'authorization': workflow['authorization']}
    logger.debug("The BODY: %r", body)
    response = app_client.post('/users/current/workflows', json=body, headers=user1_auth)
    logger.debug("The actual response: %r", response.data)

    utils.assert_status_code(400, response.status_code)
    data = json.loads(response.data)
    logger.debug("Response data: %r", data)
    assert data['title'] == 'Missing attribute \'name\'', "Unexpected error"


@pytest.mark.parametrize("client_auth_method", [
    ClientAuthenticationMethod.API_KEY,
    ClientAuthenticationMethod.AUTHORIZATION_CODE,
], indirect=True)
def test_generic_workflow_registration_no_name(app_client, client_auth_method,
                                               user1, user1_auth, client_credentials_registry, generic_workflow):
    logger.debug("User: %r", user1)
    logger.debug("headers: %r", user1_auth)
    workflow = generic_workflow
    logger.debug("Selected workflow: %r", workflow)
    logger.debug("Using oauth2 user: %r", user1)
    # prepare body
    body = {'roc_link': workflow['roc_link'],
            'version': workflow['version'],
            'authorization': workflow['authorization']}
    logger.debug("The BODY: %r", body)
    response = app_client.post('/users/current/workflows', json=body, headers=user1_auth)
    logger.debug("The actual response: %r", response.data)
    utils.assert_status_code(201, response.status_code)
    data = json.loads(response.data)
    logger.debug("Response data: %r", data)
    assert data['wf_version'] == workflow['version'], \
        "Response should be equal to the workflow UUID"
    assert data['uuid'], "Workflow UUID was not generated or returned"

    response = app_client.get(f'/workflows/{data["uuid"]}', headers=user1_auth)
    logger.debug("The actual response: %r", response.data)
    utils.assert_status_code(200, response.status_code)
    data = json.loads(response.data)
    logger.debug("Response data: %r", data)
    assert data['name'] == workflow['name'], "Unexpected workflow name"


@pytest.mark.parametrize("client_auth_method", [
    ClientAuthenticationMethod.API_KEY,
    ClientAuthenticationMethod.AUTHORIZATION_CODE,
], indirect=True)
def test_registry_workflow_registration(app_client, client_auth_method,
                                        user1, user1_auth, client_credentials_registry, valid_workflow):
    logger.debug("User: %r", user1)
    logger.debug("headers: %r", user1_auth)
    workflow = utils.pick_workflow(user1, valid_workflow)
    logger.debug("Selected workflow: %r", workflow)
    logger.debug("Using oauth2 user: %r", user1)
    # prepare body
    body = {'identifier': workflow['external_id'], 'version': workflow['version']}
    logger.debug("The BODY: %r", body)
    response = app_client.post(f'/registries/{client_credentials_registry.uuid}/workflows', json=body, headers=user1_auth)
    logger.debug("The actual response: %r", response.data)
    utils.assert_status_code(201, response.status_code)
    data = json.loads(response.data)
    logger.debug("Response data: %r", data)
    assert data['uuid'] == workflow['uuid'] and data['wf_version'] == workflow['version'], \
        "Response should be equal to the workflow UUID"


@pytest.mark.parametrize("client_auth_method", [
    #    ClientAuthenticationMethod.BASIC,
    ClientAuthenticationMethod.API_KEY,
    ClientAuthenticationMethod.AUTHORIZATION_CODE,
], indirect=True)
def test_registry_workflow_registration_same_workflow_by_different_users(app_client, client_auth_method,
                                                                         user1, user1_auth, user2, user2_auth,
                                                                         client_credentials_registry):
    original_workflow = utils.pick_workflow(user1, name='sort-and-change-case')
    assert len(models.Workflow.all()) == 0, "Unexpected number of workflows"
    for user, user_auth in [(user1, user1_auth), (user2, user2_auth)]:
        workflow = original_workflow.copy()
        logger.debug("Selected workflow: %r", workflow)
        logger.debug("User: %r", user)
        logger.debug("headers: %r", user_auth)
        logger.debug("Using oauth2 user: %r", user)
        # When the client is a registry and it uses the ClientCredentials auth flow,
        # it must provide the submitter ID
        body = {'identifier': workflow['external_id'], 'version': workflow['version']}
        logger.debug("The BODY: %r", body)
        response = app_client.post(f'/registries/{client_credentials_registry.uuid}/workflows', json=body, headers=user_auth)
        logger.debug("The actual response: %r", response.data)
        if user == user1:
            utils.assert_status_code(201, response.status_code)
            data = json.loads(response.data)
            logger.debug("Response data: %r", data)
            assert data['uuid'] == workflow['uuid'] and data['wf_version'] == workflow['version'], \
                "Response should be equal to the workflow UUID"
        else:
            utils.assert_status_code(409, response.status_code)
