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
import uuid

import pytest
from lifemonitor.api.models import WorkflowVersion
from lifemonitor.auth import current_user
from lifemonitor.auth.models import ApiKey
from lifemonitor.auth.oauth2.server.models import Token
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
def test_config_params(app_client, client_auth_method, user1, user1_auth):
    logger.info("Testing AuthMethod: %r", client_auth_method)
    logger.info("Testing with Client: %r", app_client)
    logger.info("Testing User: %r", user1['user'])

    app_client_headers = user1_auth
    with app_client.application.test_request_context():
        app_client.application.preprocess_request()
        logger.info("Test Request Headers: %r", app_client_headers)
        logger.info("Test Request User: %r", current_user)
        auth_header = app_client_headers.get("Authorization", None)
        if client_auth_method == ClientAuthenticationMethod.BASIC:
            assert not current_user.is_anonymous, "Current user must not be anonymous"
            assert not auth_header or "Bearer" not in auth_header, "Authorization token must not be in HEADER"
        else:
            assert current_user.is_anonymous, "Current user must be anonymous"
            if client_auth_method == ClientAuthenticationMethod.API_KEY:
                assert "ApiKey" in app_client_headers, "Authorization ApiKey must be in HEADER"
                token = ApiKey.find(app_client_headers["ApiKey"])
            else:
                assert "Bearer" in app_client_headers['Authorization'], "Authorization Bearer must be in HEADER"
                token = Token.find(app_client_headers['Authorization'].replace("Bearer ", ""))
            logger.info("Token: %r [user: %r]", token, token.user_id)
            if client_auth_method == ClientAuthenticationMethod.CLIENT_CREDENTIALS:
                assert token.user_id is None, f"Token MUST be not related with the current user {user1}"
            else:
                assert token.user_id == user1['user'].id, f"Token MUST be issued to the current user {user1}"

        logger.debug("WORKFLOWS: %r", user1["workflows"])


@pytest.mark.parametrize("client_auth_method", [
    ClientAuthenticationMethod.API_KEY,
], indirect=True)
def test_workflow_registration_check_default_name(app_client, client_auth_method,
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
    assert data['wf_uuid'] == workflow['uuid'] and data['wf_version'] == workflow['version'], \
        "Response should be equal to the workflow UUID"

    wf = utils.get_workflow_data(data['wf_uuid'])
    assert wf, "Unable to load workflow data"
    assert str(wf.uuid) == data['wf_uuid'], "Unexpected workflow uuid"
    assert wf.latest_version.version == data['wf_version'], "Unexpected workflow uuid"
    assert wf.name == workflow['name'], "Unexpected workflow name"


@pytest.mark.parametrize("client_auth_method", [
    ClientAuthenticationMethod.API_KEY,
], indirect=True)
def test_workflow_registration_check_custom_name(app_client, client_auth_method,
                                                 user1, user1_auth, client_credentials_registry, valid_workflow):
    logger.debug("User: %r", user1)
    logger.debug("headers: %r", user1_auth)
    workflow = utils.pick_workflow(user1, valid_workflow)
    logger.debug("Selected workflow: %r", workflow)
    logger.debug("Using oauth2 user: %r", user1)
    # prepare body
    body = {'identifier': workflow['external_id'], 'version': workflow['version'], 'name': "MyWorkflow"}
    logger.debug("The BODY: %r", body)
    response = app_client.post(f'/registries/{client_credentials_registry.uuid}/workflows', json=body, headers=user1_auth)
    logger.debug("The actual response: %r", response.data)
    utils.assert_status_code(201, response.status_code)
    data = json.loads(response.data)
    logger.debug("Response data: %r", data)
    assert data['wf_uuid'] == workflow['uuid'] and data['wf_version'] == workflow['version'], \
        "Response should be equal to the workflow UUID"

    wf = utils.get_workflow_data(data['wf_uuid'])
    assert wf, "Unable to load workflow data"
    assert str(wf.uuid) == data['wf_uuid'], "Unexpected workflow uuid"
    assert wf.latest_version.version == data['wf_version'], "Unexpected workflow uuid"
    assert wf.name == body['name'], "Unexpected workflow name"


@pytest.mark.parametrize("client_auth_method", [
    #    ClientAuthenticationMethod.BASIC,
    ClientAuthenticationMethod.API_KEY,
    ClientAuthenticationMethod.AUTHORIZATION_CODE,
    ClientAuthenticationMethod.CLIENT_CREDENTIALS,
    ClientAuthenticationMethod.REGISTRY_CODE_FLOW
], indirect=True)
@pytest.mark.parametrize("user1", [True], indirect=True)
def test_get_workflows_scope(app_client, client_auth_method,
                             user1, user1_auth, user2, user2_auth):

    logger.debug("The first user: %r", user1['user'])
    logger.debug("Number of workflows user1: %r", len(user1['workflows']))

    logger.debug("The second user: %r", user2['user'])
    logger.debug("Number of workflows user1: %r", len(user2['workflows']))

    assert user1_auth != user2_auth, "Invalid credentials"
    assert len(user1['workflows']) > len(user2['workflows'])

    # get workflows registered by user1
    response = app_client.get(utils.build_workflow_path(), headers=user1_auth)
    assert response.status_code == 200, "Error getting workflows user 1"
    user1_workflows = json.loads(response.data)['items']
    logger.info(user1_workflows)

    # get registered workflows by reader
    response = app_client.get(utils.build_workflow_path(), headers=user2_auth)
    assert response.status_code == 200, "Error getting workflows user 2"
    user2_workflows = json.loads(response.data)['items']
    logger.info(user2_workflows)

    # when the query is performed by the registry, we get all workflows in the registry
    if client_auth_method == ClientAuthenticationMethod.CLIENT_CREDENTIALS:
        assert len(user2_workflows) == len(user1_workflows), "Unexpected number of workflows"
    else:
        assert len(user2_workflows) == 2, "Unexpected number of workflows"
        assert len(user2_workflows) < len(user1_workflows), "Unexpected number of workflows"


@pytest.mark.parametrize("client_auth_method", [
    #    ClientAuthenticationMethod.BASIC,
    ClientAuthenticationMethod.API_KEY,
    ClientAuthenticationMethod.AUTHORIZATION_CODE,
    ClientAuthenticationMethod.CLIENT_CREDENTIALS,
    ClientAuthenticationMethod.REGISTRY_CODE_FLOW
], indirect=True)
@pytest.mark.parametrize("user1", [True], indirect=True)
def test_delete_workflows(app_client, client_auth_method, user1, user1_auth):
    workflows = WorkflowVersion.all()
    assert len(workflows) > 0, "Unexpected number of workflows"
    for w in [x for x in user1['workflows'] if x['name'] in [_.name for _ in workflows]]:
        logger.debug("User1 Auth Headers: %r", user1_auth)
        r = app_client.delete(utils.build_workflow_path(w, version_as_subpath=True), headers=user1_auth)
        logger.debug("Delete Response: %r", r.data)
        assert r.status_code == 204, f"Error when deleting the workflow {w}"
    assert len(WorkflowVersion.all()) == 0, "Unexpected number of workflow after delete"


@pytest.mark.parametrize("client_auth_method", [
    #    ClientAuthenticationMethod.BASIC,
    ClientAuthenticationMethod.API_KEY,
    ClientAuthenticationMethod.AUTHORIZATION_CODE,
    ClientAuthenticationMethod.CLIENT_CREDENTIALS,
    ClientAuthenticationMethod.REGISTRY_CODE_FLOW
], indirect=True)
# @pytest.mark.parametrize("user1", [True], indirect=True)
def test_get_workflow_not_authorized(app_client, client_auth_method, user1, user1_auth):
    workflow = utils.pick_workflow(user1)
    response = app_client.get(utils.build_workflow_path(workflow))
    logger.debug(response.data)
    utils.assert_status_code(401, response.status_code)


@pytest.mark.parametrize("client_auth_method", [
    #    ClientAuthenticationMethod.BASIC,
    ClientAuthenticationMethod.API_KEY,
    ClientAuthenticationMethod.AUTHORIZATION_CODE,
    ClientAuthenticationMethod.CLIENT_CREDENTIALS,
    ClientAuthenticationMethod.REGISTRY_CODE_FLOW
], indirect=True)
def test_get_workflow_latest_version(app_client, client_auth_method, user1, user1_auth, valid_workflow):
    workflow = utils.pick_workflow(user1, valid_workflow)
    wv1 = workflow.copy()
    wv2 = workflow.copy()

    wv1['version'] = "1"
    wv2['version'] = "2"
    utils.register_workflow(user1, wv1)
    utils.register_workflow(user1, wv2)

    response = app_client.get(utils.build_workflow_path(), headers=user1_auth)
    utils.assert_status_code(200, response.status_code)
    workflows = json.loads(response.data)
    logger.debug("Workflows: %r", workflows)

    url = f"{utils.build_workflow_path()}/{workflow['uuid']}?previous_versions=true"
    logger.debug("URL: %r", url)
    response = app_client.get(url, headers=user1_auth)
    logger.debug(response)
    utils.assert_status_code(200, response.status_code)
    data = json.loads(response.data)
    logger.debug("Response data: %r", data)
    assert data['uuid'] == workflow['uuid'], "Unexpected workflow ID"
    assert data['version']['version'] == "2", "Unexpected workflow version number: it should the latest (=2)"
    assert "previous_versions" in data, "Unable to find the versions field"
    assert "1" in [_['version'] for _ in data['previous_versions']], "Previous version not defined"


@pytest.mark.parametrize("client_auth_method", [
    #    ClientAuthenticationMethod.BASIC,
    ClientAuthenticationMethod.API_KEY,
    ClientAuthenticationMethod.AUTHORIZATION_CODE,
    ClientAuthenticationMethod.CLIENT_CREDENTIALS,
    ClientAuthenticationMethod.REGISTRY_CODE_FLOW
], indirect=True)
def test_get_workflow_versions(app_client, client_auth_method, user1, user1_auth, valid_workflow):
    workflow = utils.pick_workflow(user1, valid_workflow)
    wv1 = workflow.copy()
    wv2 = workflow.copy()

    wv1['version'] = "1"
    wv2['version'] = "2"
    utils.register_workflow(user1, wv1)
    utils.register_workflow(user1, wv2)

    url = f"{utils.build_workflow_path()}/{workflow['uuid']}/versions"
    logger.debug("URL: %r", url)
    response = app_client.get(url, headers=user1_auth)
    logger.debug(response)
    utils.assert_status_code(200, response.status_code)
    data = json.loads(response.data)
    logger.debug("Response data: %r", data)

    assert data['workflow']['uuid'] == workflow['uuid'], "Unexpected workflow ID"
    assert 'versions' in data, "Unable to find versions field"
    # Check versions
    assert len(data['versions']) == 2, "Unexpected number of versions"
    assert data['versions'][0]['is_latest'] is (data['versions'][0]['version'] == "2"), \
        "It shouldn't be the latest version"


@pytest.mark.parametrize("client_auth_method", [
    #    ClientAuthenticationMethod.BASIC,
    ClientAuthenticationMethod.API_KEY,
    ClientAuthenticationMethod.AUTHORIZATION_CODE,
    ClientAuthenticationMethod.CLIENT_CREDENTIALS,
    ClientAuthenticationMethod.REGISTRY_CODE_FLOW
], indirect=True)
def test_get_workflow_status(app_client, client_auth_method, user1, user1_auth, valid_workflow):
    w, workflow = utils.pick_and_register_workflow(user1, valid_workflow)
    response = app_client.get(f"{utils.build_workflow_path(w, subpath='status')}", headers=user1_auth)
    logger.debug(response)
    utils.assert_status_code(200, response.status_code)
    data = json.loads(response.data)
    logger.debug("Response data: %r", data)
    assert data['uuid'] == w['uuid'], "Unexpected workflow ID"
    assert data['version']['version'] == w['version'], "Unexpected workflow version number: it should the latest (=2)"
    assert "aggregate_test_status" in data, "Missing required aggregate_test_status"
    assert "latest_builds" in data, "Missing required latest_builds"


@pytest.mark.parametrize("client_auth_method", [
    #    ClientAuthenticationMethod.BASIC,
    ClientAuthenticationMethod.API_KEY,
    ClientAuthenticationMethod.AUTHORIZATION_CODE,
    ClientAuthenticationMethod.CLIENT_CREDENTIALS,
    ClientAuthenticationMethod.REGISTRY_CODE_FLOW
], indirect=True)
def test_get_workflow_suites(app_client, client_auth_method, user1, user1_auth, valid_workflow):
    w, workflow = utils.pick_and_register_workflow(user1, valid_workflow)
    response = app_client.get(f"{utils.build_workflow_path(w, subpath='suites')}", headers=user1_auth)
    logger.debug(response)
    utils.assert_status_code(200, response.status_code)
    data = json.loads(response.data)
    logger.debug("Response data: %r", data)
    assert "items" in data, "Missing items property"
    assert len(data['items']) == 1, "Unexpected number of suites"
    # redundant check: the validation is performed by the connexion framework
    suite = data['items'][0]
    assert suite['uuid'], "Invalid UUID"
    assert "roc_suite" in suite, "Missing required roc_suite"
    assert "definition" in suite, "Missing required definition"
    assert "instances" in suite, "Missing required instances"


@pytest.mark.parametrize("client_auth_method", [ClientAuthenticationMethod.API_KEY])
def test_workflow_registry_roc_not_found(app_client, client_auth_method, user1_auth):  # , valid_workflow)
    wf = {
        'uuid': uuid.uuid4(),
        'version': '1',
        'roc_link': "http://webserver:5000/download?file=I-do-not-exist.crate.zip",
        'name': 'Not a workflow',
        'authorization': app_client.application.config['WEB_SERVER_AUTH_TOKEN']
    }
    response = app_client.post('/users/current/workflows', json=wf, headers=user1_auth)
    utils.assert_status_code(400, response.status_code)
