import json
import logging

import pytest

from tests.conftest import assert_status_code, SecurityType, RegistryType

logger = logging.getLogger()

_WORKFLOWS_ENDPOINT = '/workflows'


def _build_workflow_path(workflow=None):
    if workflow:
        return f"{_WORKFLOWS_ENDPOINT}/{workflow['uuid']}/{workflow['version']}"
    return _WORKFLOWS_ENDPOINT


def test_empty_workflows(app_client, clean_db, user):
    response = app_client.get(_build_workflow_path())
    assert_status_code(200, response.status_code)
    assert response.data, "Empty response"
    data = json.loads(response.data)
    logger.debug("Response %r", data)
    assert len(data) == 0, "Invalid number of workflows"


def test_workflow_registration(app_client, clean_db, user, workflow):
    response = app_client.post(_build_workflow_path(), json=workflow)
    assert_status_code(201, response.status_code)
    data = json.loads(response.data)
    logger.debug("Response data: %r", data)
    assert data['wf_uuid'] == workflow['uuid'] and data['version'] == workflow['version'], \
        "Response should be equal to the workflow UUID"


def test_get_workflow(app_client, user, workflow):
    response = app_client.get(_build_workflow_path(workflow))
    logger.debug(response.data)
    assert_status_code(200, response.status_code)
    data = json.loads(response.data)
    logger.debug("Response data: %r", data)


def test_workflow_with_test_builds(app_client, user, workflow):
    response = app_client.get(_build_workflow_path(workflow),
                              query_string={'test_suite': True, 'test_build': True, 'test_output': True})
    assert_status_code(200, response.status_code)
    data = json.loads(response.data)
    logger.debug("Workflow info: %r", data)
    assert len(data["test_suite"]) == 1, "Test suite should not be empty"
    test_suite = data["test_suite"][0]
    if "test" in test_suite and len(test_suite["test"]) > 0:
        test_conf = test_suite["test"][0]
        if len(test_conf["test_builds"]) > 0:
            test = test_conf["test_builds"][0]
            logger.debug("Test output: %r", test["output"])
            assert test["output"], "No test output found"


@pytest.mark.parametrize("registry_user", [(RegistryType.SEEK.value, SecurityType.API_KEY.value)], indirect=True)
@pytest.mark.parametrize("registry_workflow", [(RegistryType.SEEK.value, SecurityType.API_KEY.value)], indirect=True)
def test_workflow_deregistration(app_client, registry_user, registry_workflow):
    response = app_client.delete(_build_workflow_path(registry_workflow))
    assert response.status_code == 204, "Status code different from 204"
