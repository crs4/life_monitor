import json
import logging

import pytest
from tests import utils
from tests.conftest_types import ClientAuthenticationMethod

from lifemonitor.auth.models import ApiKey
from lifemonitor.auth.oauth2.server.models import Token
from lifemonitor.api.models import Workflow
from lifemonitor.auth import current_user


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
    #    ClientAuthenticationMethod.BASIC,
    ClientAuthenticationMethod.API_KEY,
    ClientAuthenticationMethod.AUTHORIZATION_CODE,
    ClientAuthenticationMethod.CLIENT_CREDENTIALS,
    ClientAuthenticationMethod.REGISTRY_CODE_FLOW
], indirect=True)
def test_empty_workflows(app_client, client_auth_method, user1, user1_auth):
    response = app_client.get(utils.build_workflow_path(), headers=user1_auth)
    utils.assert_status_code(200, response.status_code)
    assert response.data, "Empty response"
    data = json.loads(response.data)
    logger.debug("Response %r", data)
    assert len(data['items']) == 0, "Invalid number of workflows"


@pytest.mark.parametrize("client_auth_method", [
    #    ClientAuthenticationMethod.BASIC,
    ClientAuthenticationMethod.API_KEY,
    ClientAuthenticationMethod.AUTHORIZATION_CODE,
    ClientAuthenticationMethod.CLIENT_CREDENTIALS,
    ClientAuthenticationMethod.REGISTRY_CODE_FLOW
], indirect=True)
def test_workflow_registration(app_client, client_auth_method,
                               user1, user1_auth, client_credentials_registry, valid_workflow):
    logger.debug("User: %r", user1)
    logger.debug("headers: %r", user1_auth)
    #workflow = utils.pick_workflow(user1, "sort-and-change-case")
    workflow = utils.pick_workflow(user1, valid_workflow)
    logger.debug("Selected workflow: %r", workflow)
    logger.debug("Using oauth2 user: %r", user1)
    if client_auth_method == ClientAuthenticationMethod.CLIENT_CREDENTIALS:  # ClientCredentials case
        del workflow['registry_uri']
        workflow['submitter_id'] = \
            list(user1["user"].oauth_identity.values())[0].provider_user_id
    elif client_auth_method == ClientAuthenticationMethod.AUTHORIZATION_CODE:
        workflow['registry_uri'] = client_credentials_registry.uri
    elif client_auth_method == ClientAuthenticationMethod.REGISTRY_CODE_FLOW:
        del workflow['registry_uri']
        # del workflow['submitter_id'] # already deleted
    assert workflow['name'] is not None, "MMMMM"
    logger.debug("The BODY: %r", workflow)
    response = app_client.post(utils.build_workflow_path(),
                               json=workflow, headers=user1_auth)

    logger.debug("The actual response: %r", response.data)
    utils.assert_status_code(201, response.status_code)
    data = json.loads(response.data)
    logger.debug("Response data: %r", data)
    assert data['wf_uuid'] == workflow['uuid'] and data['wf_version'] == workflow['version'], \
        "Response should be equal to the workflow UUID"


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
    workflows = Workflow.all()
    assert len(workflows) > 0, "Unexpected number of workflows"
    for w in [x for x in user1['workflows'] if x['name'] in [_.name for _ in workflows]]:
        logger.debug("User1 Auth Headers: %r", user1_auth)
        r = app_client.delete(utils.build_workflow_path(w), headers=user1_auth)
        logger.debug("Delete Response: %r", r.data)
        assert r.status_code == 204, f"Error when deleting the workflow {w}"
    assert len(Workflow.all()) == 0, "Unexpected number of workflow after delete"


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
    utils.assert_status_code(response.status_code, 200)
    workflows = json.loads(response.data)
    logger.debug("Workflows: %r", workflows)

    url = f"{utils.build_workflow_path()}/{workflow['uuid']}"
    logger.debug("URL: %r", url)
    response = app_client.get(url, headers=user1_auth)
    logger.debug(response)
    utils.assert_status_code(response.status_code, 200)
    data = json.loads(response.data)
    logger.debug("Response data: %r", data)
    assert data['uuid'] == workflow['uuid'], "Unexpected workflow ID"
    assert data['version'] == "2", "Unexpected workflow version number: it should the latest (=2)"
    assert "1" in data['previous_versions'], "Previous version not defined"


@pytest.mark.parametrize("client_auth_method", [
    #    ClientAuthenticationMethod.BASIC,
    ClientAuthenticationMethod.API_KEY,
    ClientAuthenticationMethod.AUTHORIZATION_CODE,
    ClientAuthenticationMethod.CLIENT_CREDENTIALS,
    ClientAuthenticationMethod.REGISTRY_CODE_FLOW
], indirect=True)
def test_get_workflow_status(app_client, client_auth_method, user1, user1_auth, valid_workflow):
    w, workflow = utils.pick_and_register_workflow(user1, valid_workflow)
    response = app_client.get(f"{utils.build_workflow_path(w)}/status", headers=user1_auth)
    logger.debug(response)
    utils.assert_status_code(response.status_code, 200)
    data = json.loads(response.data)
    logger.debug("Response data: %r", data)
    assert data['workflow']['uuid'] == w['uuid'], "Unexpected workflow ID"
    assert data['workflow']['version'] == w['version'], "Unexpected workflow version number: it should the latest (=2)"
    assert "aggregate_test_status" in data, "Missing required aggregate_test_status"
    assert "latest_builds" in data, "Missing required latest_builds"


@pytest.mark.parametrize("client_auth_method", [
    #    ClientAuthenticationMethod.BASIC,
    ClientAuthenticationMethod.API_KEY,
    ClientAuthenticationMethod.AUTHORIZATION_CODE,
    ClientAuthenticationMethod.CLIENT_CREDENTIALS,
    ClientAuthenticationMethod.REGISTRY_CODE_FLOW
], indirect=True)
def test_get_workflow_suite(app_client, client_auth_method, user1, user1_auth, valid_workflow):
    w, workflow = utils.pick_and_register_workflow(user1, valid_workflow)
    response = app_client.get(f"{utils.build_workflow_path(w)}/suites", headers=user1_auth)
    logger.debug(response)
    utils.assert_status_code(response.status_code, 200)
    data = json.loads(response.data)
    logger.debug("Response data: %r", data)
    assert "items" in data, "Missing items property"
    assert len(data['items']) == 1, "Unexpected number of suites"
    # redundant check: the validation is performed by the connexion framework
    suite = data['items'][0]
    assert suite['uuid'], "Invalid UUID"
    assert "test_suite_metadata" in suite, "Missing required test_suite_metadata"
    assert "instances" in suite, "Missing required instances"
