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


import logging
from unittest.mock import MagicMock, patch

import pytest


import lifemonitor.api.controllers as controllers
import lifemonitor.api.models as models
import lifemonitor.api.serializers as serializers
import lifemonitor.auth as auth
import lifemonitor.exceptions as lm_exceptions
from lifemonitor.auth.oauth2.client.models import \
    OAuthIdentityNotFoundException
from lifemonitor.lang import messages
from tests.utils import assert_status_code

logger = logging.getLogger(__name__)


@patch("lifemonitor.api.controllers.lm")
def test_get_workflows_with_user(m, request_context, mock_user, fake_uri):
    # add one user to the current session
    assert not auth.current_user.is_anonymous, "Unexpected user in session"
    assert auth.current_user == mock_user, "Unexpected user in session"
    logger.debug("Current registry: %r", auth.current_registry)
    assert not auth.current_registry, "Unexpected registry in session"
    # make empty the list of public workflows
    m.get_public_workflows.return_value = []
    # add one fake workflow
    data = {"uuid": "123456", "version": "1.0", "name": "Fake workflow", "uri": fake_uri}
    w = models.Workflow(uuid=data['uuid'])
    w.add_version(data["version"], data['uri'], MagicMock(), name="Prova")
    m.get_user_workflows.return_value = [w]
    response = controllers.workflows_get(status=True)
    m.get_public_workflows.assert_called_once()
    m.get_user_workflows.assert_called_once()
    assert isinstance(response, dict), "Unexpected result type"
    logger.debug("Response: %r", response)
    assert response == serializers.ListOfWorkflows(workflow_status=True).dump([w])


@patch("lifemonitor.api.controllers.lm")
def test_get_public_workflows_rate_limit_exceeded(lm, rate_limit_exceeded_workflow):
    # set workflow as public
    lm.get_public_workflows.return_value = [rate_limit_exceeded_workflow]
    # get workflows
    data = controllers.workflows_get(status=True)
    logger.info(data)
    # check number of items
    assert len(data['items']) == 1, "Unexpected number of items"
    # inspect item
    item = data['items'][0]
    assert 'status' in item, "Workflow status should be set"
    assert 'aggregate_test_status' in item['status'], "AggregateStatus Workflow status should be set"
    assert item['status']['aggregate_test_status'] == 'not_available'
    assert "Rate Limit Exceeded" in item['status']['reason'], "Unexpected reason for unavailability"


@patch("lifemonitor.api.controllers.lm")
def test_get_workflows_with_user_rate_limit_exceeded(lm, mock_user, no_cache, rate_limit_exceeded_workflow):
    # add one user to the current session
    assert not auth.current_user.is_anonymous, "Unexpected user in session"
    assert auth.current_user == mock_user, "Unexpected user in session"
    logger.debug("Current registry: %r", auth.current_registry)
    assert not auth.current_registry, "Unexpected registry in session"
    # set workflows
    lm.get_public_workflows.return_value = []
    lm.get_user_workflows.return_value = [rate_limit_exceeded_workflow]
    # get workflows
    data = controllers.workflows_get(status=True)
    logger.info(data)
    # check number of items
    assert len(data['items']) == 1, "Unexpected number of items"
    # inspect item
    item = data['items'][0]
    assert 'status' in item, "Workflow status should be set"
    assert 'aggregate_test_status' in item['status'], "AggregateStatus Workflow status should be set"
    assert item['status']['aggregate_test_status'] == 'not_available'
    assert "Rate Limit Exceeded" in item['status']['reason'], "Unexpected reason for unavailability"


@patch("lifemonitor.api.controllers.lm")
def test_get_workflows_with_registry(m, request_context, mock_registry, fake_uri):
    assert auth.current_user.is_anonymous, "Unexpected user in session"
    assert auth.current_registry, "Unexpected registry in session"
    # make empty the list of public workflows
    m.get_public_workflows.return_value = []
    # add one fake workflow
    data = {"uuid": "123456", "version": "1.0", "uri": fake_uri}
    w = models.Workflow(uuid=data['uuid'])
    w.add_version(data["version"], data['uri'], MagicMock())
    m.get_registry_workflows.return_value = [w]
    response = controllers.workflows_get(status=True)
    m.get_registry_workflows.assert_called_once()
    assert isinstance(response, dict), "Unexpected result type"
    assert response == serializers.ListOfWorkflows(workflow_status=True).dump([w])


@patch("lifemonitor.api.controllers.lm")
def test_get_workflows_with_registry_rate_limit_exceeded(m, request_context, mock_registry, fake_uri, rate_limit_exceeded_workflow):
    assert auth.current_user.is_anonymous, "Unexpected user in session"
    assert auth.current_registry, "Unexpected registry in session"
    # make empty the list of public workflows
    m.get_public_workflows.return_value = []
    m.get_registry_workflows.return_value = [rate_limit_exceeded_workflow]
    response = controllers.workflows_get(status=True)
    m.get_registry_workflows.assert_called_once()
    assert isinstance(response, dict), "Unexpected result type"
    assert response == serializers.ListOfWorkflows(workflow_status=True).dump([rate_limit_exceeded_workflow])
    # check number of items
    assert len(response['items']) == 1, "Unexpected number of items"
    # inspect item
    item = response['items'][0]
    assert 'status' in item, "Workflow status should be set"
    assert 'aggregate_test_status' in item['status'], "AggregateStatus Workflow status should be set"
    assert item['status']['aggregate_test_status'] == 'not_available'
    assert 'status' in item, "Workflow status should be set"
    assert 'aggregate_test_status' in item['status'], "AggregateStatus Workflow status should be set"
    assert item['status']['aggregate_test_status'] == 'not_available'
    assert "Rate Limit Exceeded" in item['status']['reason'], "Unexpected reason for unavailability"


@patch("lifemonitor.api.controllers.lm")
def test_post_workflows_no_authorization(m, request_context):
    assert auth.current_user.is_anonymous, "Unexpected user in session"
    assert not auth.current_registry, "Unexpected registry in session"
    with pytest.raises(auth.NotAuthorizedException):
        controllers.workflows_post(body={})


@patch("lifemonitor.api.controllers.lm")
def test_post_workflow_by_user_empty_request_body(request_context, mock_user):
    assert not auth.current_user.is_anonymous, "Unexpected user in session"
    assert auth.current_user == mock_user, "Unexpected user in session"
    assert not auth.current_registry, "Unexpected registry in session"
    # Post a request with an empty body.  Must result in validation error and a
    # BadRequest status (400)
    response = controllers.workflows_post(body={})
    logger.debug("Response: %r, %r", response, str(response.data))
    assert response.status_code == 400


@patch("lifemonitor.api.controllers.lm")
def test_post_workflow_by_user_error_invalid_registry_uri(m, request_context, mock_user):
    assert not auth.current_user.is_anonymous, "Unexpected user in session"
    assert auth.current_user == mock_user, "Unexpected user in session"
    assert not auth.current_registry, "Unexpected registry in session"
    # add one fake workflow
    data = {"registry": "123456"}
    m.get_workflow_registry_by_generic_reference.side_effect = lm_exceptions.EntityNotFoundException(models.WorkflowRegistry)
    with pytest.raises(lm_exceptions.EntityNotFoundException):
        controllers.workflows_post(body=data)
    m.get_workflow_registry_by_generic_reference.assert_called_once_with(data["registry"]), \
        "get_workflow_registry_by_uri should be used"


@patch("lifemonitor.api.controllers.lm")
def test_post_workflow_by_user_error_missing_input_data(m, request_context, mock_user):
    assert not auth.current_user.is_anonymous, "Unexpected user in session"
    assert auth.current_user == mock_user, "Unexpected user in session"
    assert not auth.current_registry, "Unexpected registry in session"
    # add one fake workflow
    data = {"registry": "123456"}
    m.get_workflow_registry_by_generic_reference.return_value = MagicMock()
    with pytest.raises(lm_exceptions.BadRequestException):
        controllers.workflows_post(body=data)
    m.get_workflow_registry_by_generic_reference.assert_called_once_with(data["registry"]), \
        "get_workflow_registry_by_uri should be used"


@patch("lifemonitor.api.controllers.notify_workflow_version_updates")
@patch("lifemonitor.api.controllers.lm")
def test_post_workflow_by_user(m, notify_updates, request_context, mock_user):
    assert not auth.current_user.is_anonymous, "Unexpected user in session"
    assert auth.current_user == mock_user, "Unexpected user in session"
    assert not auth.current_registry, "Unexpected registry in session"
    # add one fake workflow
    data = {
        "registry": "123456",
        "uuid": "1212121212121212",
        "version": "1.0",
        "roc_link": "https://registry.org/roc_crate/download"
    }
    m.get_workflow_registry_by_generic_reference.return_value = MagicMock()
    notify_updates.return_value = None
    w = MagicMock()
    w.uuid = data['uuid']
    w.version = data['version']
    w.workflow = MagicMock()
    w.workflow.uuid = data['uuid']
    m.register_workflow.return_value = w
    response = controllers.workflows_post(body=data)
    m.get_workflow_registry_by_generic_reference.assert_called_once_with(data["registry"]), \
        "get_workflow_registry_by_uri should be used"
    assert_status_code(201, response[1])
    assert response[0]["uuid"] == data['uuid'] and \
        response[0]["wf_version"] == data['version']


@patch("lifemonitor.api.controllers.lm")
def test_post_workflow_by_registry_error_registry_uri(m, request_context, mock_registry):
    assert auth.current_user.is_anonymous, "Unexpected user in session"
    assert auth.current_registry, "Unexpected registry in session"
    # add one fake workflow
    data = {"registry": "123456"}
    with pytest.raises(lm_exceptions.BadRequestException) as ex:
        controllers.workflows_post(body=data)
    assert messages.unexpected_registry_uri in ex.exconly(True), "Unexpected error message"


@patch("lifemonitor.api.controllers.lm")
def test_post_workflow_by_registry_error_submitter_not_found(m, request_context, mock_registry):
    assert auth.current_user.is_anonymous, "Unexpected user in session"
    assert auth.current_registry, "Unexpected registry in session"
    # add one fake workflow
    data = {"submitter_id": 1, "identifier": 1}
    m.find_registry_user_identity.side_effect = OAuthIdentityNotFoundException()
    with pytest.raises(lm_exceptions.NotAuthorizedException) as ex:
        controllers.workflows_post(body=data)
    assert messages.no_user_oauth_identity_on_registry \
        .format(data["submitter_id"], mock_registry.name) in ex.exconly(True),\
        "Unexpected error message"


@patch("lifemonitor.api.controllers.notify_workflow_version_updates")
@patch("lifemonitor.api.controllers.lm")
def test_post_workflow_by_registry(m, notify_udpates, request_context, mock_registry):
    assert auth.current_user.is_anonymous, "Unexpected user in session"
    assert auth.current_registry, "Unexpected registry in session"
    notify_udpates.return_value = None
    # add one fake workflow
    data = {
        "uuid": "1212121212121212",
        "version": "1.0",
        "submitter_id": "1",
        "roc_link": "https://registry.org/roc_crate/download"
    }
    w = MagicMock()
    w.uuid = data['uuid']
    w.version = data['version']
    w.workflow = MagicMock()
    w.workflow.uuid = data['uuid']
    m.register_workflow.return_value = w
    response = controllers.workflows_post(body=data)
    logger.debug("Response: %r", response)
    assert_status_code(201, response[1])
    assert response[0]["uuid"] == data['uuid'] and \
        response[0]["wf_version"] == data['version']


@patch("lifemonitor.api.controllers.lm")
def test_post_workflow_by_registry_invalid_rocrate(m, request_context, mock_registry):
    assert auth.current_user.is_anonymous, "Unexpected user in session"
    assert auth.current_registry, "Unexpected registry in session"
    # add one fake workflow
    data = {
        "uuid": "1212121212121212",
        "version": "1.0",
        "submitter_id": "1",
        "roc_link": "https://registry.org/roc_crate/download"
    }
    w = MagicMock()
    w.uuid = data['uuid']
    w.version = data['version']
    m.register_workflow.side_effect = lm_exceptions.NotValidROCrateException()
    response = controllers.workflows_post(body=data)
    logger.debug("Response: %r", response)
    assert_status_code(400, response.status_code)
    assert messages.invalid_ro_crate in response.data.decode()


@patch("lifemonitor.api.controllers.lm")
def test_post_workflow_by_registry_not_authorized(m, request_context, mock_registry):
    assert auth.current_user.is_anonymous, "Unexpected user in session"
    assert auth.current_registry, "Unexpected registry in session"
    # add one fake workflow
    data = {
        "uuid": "1212121212121212",
        "version": "1.0",
        "submitter_id": "1",
        "roc_link": "https://registry.org/roc_crate/download"
    }
    w = MagicMock()
    w.uuid = data['uuid']
    w.version = data['version']
    m.register_workflow.side_effect = lm_exceptions.NotAuthorizedException()
    response = controllers.workflows_post(body=data)
    logger.debug("Response: %r", response)
    assert_status_code(403, response.status_code)
    assert messages.not_authorized_registry_access\
        .format(mock_registry.name) in response.data.decode()


@patch("lifemonitor.api.controllers.lm")
def test_get_workflow_by_id_error_not_found(m, request_context, mock_registry):
    assert auth.current_user.is_anonymous, "Unexpected user in session"
    assert auth.current_registry, "Unexpected registry in session"
    m.get_public_workflow_version.return_value = None
    m.get_registry_workflow_version.side_effect = lm_exceptions.EntityNotFoundException(models.WorkflowVersion)
    with pytest.raises(lm_exceptions.EntityNotFoundException) as ex:
        controllers.workflows_get_by_id(wf_uuid="12345", wf_version="1")
    assert messages.workflow_version_not_found\
        .format("12345", "1") in ex.exconly(True)
    # test when the service return None
    m.get_registry_workflow_version.return_value = None
    with pytest.raises(lm_exceptions.EntityNotFoundException) as ex:
        controllers.workflows_get_by_id(wf_uuid="12345", wf_version="1")
    assert messages.workflow_version_not_found\
        .format("12345", "1") in ex.exconly(True)


@patch("lifemonitor.api.controllers.lm")
def test_get_workflow_by_id(m, request_context, mock_registry):
    assert auth.current_user.is_anonymous, "Unexpected user in session"
    assert auth.current_registry, "Unexpected registry in session"
    data = {"uuid": "12345", "version": "2", "roc_link": "https://somelink"}
    w = models.Workflow(uuid=data["uuid"])
    wv = w.add_version(data["version"], data["roc_link"], MagicMock())
    wv._repository = MagicMock()
    wv._repository.metadata = MagicMock()
    wv._repository.metadata.isBasedOn = "https://somelink"
    wv._metadata_loaded = True
    m.get_public_workflow_version.return_value = None
    m.get_registry_workflow_version.return_value = wv
    response = controllers.workflows_get_by_id(data['uuid'], data['version'])
    m.get_registry_workflow_version.assert_called_once_with(mock_registry, data['uuid'], data['version'])
    logger.debug("Response: %r", response)
    assert isinstance(response, dict), "Unexpected response"
    assert response['uuid'] == data['uuid'], "Unexpected workflow UUID"
    assert response['version']['version'] == data['version'], "Unexpected workflow version"
    assert 'previous_versions' not in response, "Unexpected list of previous versions"
