import os
import json
import logging
from .fixtures import (
    client, clean_db, headers,
    workflow_uuid, workflow_version, workflow_name,
    test_suite_metadata, suite_uuid
)

logger = logging.getLogger()


def test_empty_workflows(client, clean_db):
    response = client.get('/workflows')
    assert response.status_code == 200, "Status code different from 200"
    assert response.data, "Empty response"
    data = json.loads(response.data)
    logger.debug("Response %r", data)
    assert len(data) == 0, "Invalid number of workflows"


def test_workflow_registration(client):
    response = client.post("/workflows", json={
        'uuid': workflow_uuid,
        'version': workflow_version,
        'name': workflow_name,
        'roc_link': os.getenv("WORKFLOW_ROC_LINK"),
    })
    assert response.status_code == 201, "Status code different from 200"
    data = json.loads(response.data)
    logger.debug("Response data: %r", data)
    assert data['wf_uuid'] == workflow_uuid and data['version'] == workflow_version, \
        "Response should be equal to the workflow UUID"


def test_get_workflow(client):
    response = client.get(os.path.join("/workflows", workflow_uuid, workflow_version))
    logger.debug(response.data)
    assert response.status_code == 200, "Status code different from 200"
    data = json.loads(response.data)
    logger.debug("Response data: %r", data)


def test_suite_registration(client, test_suite_metadata):
    response = client.post(
        os.path.join("/workflows", workflow_uuid, workflow_version, 'suites'), json={
            'test_suite_metadata': test_suite_metadata
        })
    assert response.status_code == 201, "Status code different from 201"


def test_workflow_with_test_builds(client):
    response = client.get(
        os.path.join("/workflows", workflow_uuid, workflow_version),
        query_string={'test_suite': True, 'test_build': True, 'test_output': True}
    )
    assert response.status_code == 200, "Status code different from 200"
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


def test_suite_deregistration(client, suite_uuid):
    response = client.delete(os.path.join("/suites", suite_uuid))
    assert response.status_code == 204, "Status code different from 204"


def test_workflow_deregistration(client):
    response = client.delete(os.path.join("/workflows", workflow_uuid, workflow_version))
    assert response.status_code == 204, "Status code different from 204"
