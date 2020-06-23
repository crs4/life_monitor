import os
import json
import logging
from .fixtures import (
    client, clean_db, headers,
    workflow_uuid, workflow_version, workflow_roc_link, workflow_name,
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
        'roc_link': workflow_roc_link,
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


def test_workflow_health_status(client):
    response = client.get(
        os.path.join("/workflows", workflow_uuid, workflow_version, "health_status"))
    assert response.status_code == 200, "Status code different from 200"
    data = json.loads(response.data)
    logger.debug("Workflow health report: %r", data)


def test_suite_deregistration(client, suite_uuid):
    response = client.delete(os.path.join("/suites", suite_uuid))
    assert response.status_code == 204, "Status code different from 204"


def test_workflow_deregistration(client):
    response = client.delete(os.path.join("/workflows", workflow_uuid, workflow_version))
    assert response.status_code == 204, "Status code different from 204"
