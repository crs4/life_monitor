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
def test_get_suite(app_client, client_auth_method, user1, user1_auth):
    w, workflow = utils.pick_and_register_workflow(user1, "sort-and-change-case")
    assert len(workflow.test_suites) > 0, "Unexpected number of test suites"
    suite = workflow.test_suites[0]
    logger.debug("The test suite: %r", suite)

    response = app_client.get(f"{utils.build_suites_path(suite.uuid)}", headers=user1_auth)
    logger.debug(response)
    utils.assert_status_code(200, response.status_code)
    data = json.loads(response.data)
    logger.debug("Response data: %r", data)
    # redundant check: the validation is performed by the connexion framework
    assert data['uuid'] == str(suite.uuid), "Invalid UUID"
    for p in ["test_suite_metadata", "instances"]:
        assert p in data, f"Missing required property {p}"


@pytest.mark.parametrize("client_auth_method", [
    #    ClientAuthenticationMethod.BASIC,
    ClientAuthenticationMethod.API_KEY,
    ClientAuthenticationMethod.AUTHORIZATION_CODE,
    ClientAuthenticationMethod.CLIENT_CREDENTIALS,
    ClientAuthenticationMethod.REGISTRY_CODE_FLOW
], indirect=True)
def test_get_suite_status(app_client, client_auth_method, user1, user1_auth):
    w, workflow = utils.pick_and_register_workflow(user1, "sort-and-change-case")
    assert len(workflow.test_suites) > 0, "Unexpected number of test suites"
    suite = workflow.test_suites[0]
    logger.debug("The test suite: %r", suite)

    response = app_client.get(f"{utils.build_suites_path(suite.uuid)}/status", headers=user1_auth)
    logger.debug(response)
    utils.assert_status_code(200, response.status_code)
    data = json.loads(response.data)
    logger.debug("Response data: %r", data)
    # redundant check: the validation is performed by the connexion framework
    assert data['suite_uuid'] == str(suite.uuid), "Invalid UUID"
    for p in ["status", "latest_builds"]:
        assert p in data, f"Missing required property {p}"


@pytest.mark.parametrize("client_auth_method", [
    #    ClientAuthenticationMethod.BASIC,
    ClientAuthenticationMethod.API_KEY,
    ClientAuthenticationMethod.AUTHORIZATION_CODE,
    ClientAuthenticationMethod.CLIENT_CREDENTIALS,
    ClientAuthenticationMethod.REGISTRY_CODE_FLOW
], indirect=True)
def test_get_suite_instances(app_client, client_auth_method, user1, user1_auth):
    w, workflow = utils.pick_and_register_workflow(user1, "sort-and-change-case")
    assert len(workflow.test_suites) > 0, "Unexpected number of test suites"
    suite = workflow.test_suites[0]
    logger.debug("The test suite: %r", suite)

    response = app_client.get(f"{utils.build_suites_path(suite.uuid)}/instances",
                              headers=user1_auth)
    logger.debug(response)
    utils.assert_status_code(200, response.status_code)
    data = json.loads(response.data)
    logger.debug("Response data: %r", data)
    # redundant check: the validation is performed by the connexion framework
    for p in ["items"]:
        assert p in data, f"Missing required property {p}"
