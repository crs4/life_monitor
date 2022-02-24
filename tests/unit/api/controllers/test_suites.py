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

import logging
from unittest.mock import MagicMock, patch

import lifemonitor.api.controllers as controllers
import lifemonitor.api.models as models
import lifemonitor.auth as auth
import lifemonitor.exceptions as lm_exceptions
import pytest
from tests.utils import assert_status_code

logger = logging.getLogger(__name__)


@patch("lifemonitor.api.controllers.lm")
def test_get_suite_error_not_found(m, request_context, mock_user):
    assert not auth.current_user.is_anonymous, "Unexpected user in session"
    assert auth.current_registry is not None, "Unexpected registry in session"
    m.get_suite.return_value = None
    response = controllers.suites_get_by_uuid("123456")
    m.get_suite.assert_called_once()
    assert_status_code(404, response.status_code), "Unexpected status code"


@patch("lifemonitor.api.controllers.lm")
def test_get_suite_by_user_without_auth_access_to_workflow(m, request_context, no_cache, mock_user):
    # add one user to the current session
    assert not auth.current_user.is_anonymous, "Unexpected user in session"
    assert auth.current_user == mock_user, "Unexpected user in session"
    logger.debug("Current registry: %r", auth.current_registry)
    assert not auth.current_registry, "Unexpected registry in session"
    workflow = MagicMock()
    workflow.uuid = "1111-222"
    suite = MagicMock()
    suite.uuid = '1111'
    suite.workflow = workflow
    m.get_suite.return_value = suite
    m.get_public_workflow_version.return_value = None
    m.get_user_workflow_version.side_effect = lm_exceptions.NotAuthorizedException
    with pytest.raises(lm_exceptions.Forbidden):
        controllers.suites_get_by_uuid(suite.uuid)
    m.get_suite.assert_called_once()
    m.get_user_workflow_version.assert_called_once()


@patch("lifemonitor.api.controllers.lm")
def test_get_suite_by_registry_without_auth_access_to_workflow(m, request_context, no_cache, mock_registry):
    # add one user to the current session
    assert auth.current_user.is_anonymous, "Unexpected user in session"
    logger.debug("Current registry: %r", auth.current_registry)
    assert auth.current_registry, "Unexpected registry in session"
    # add one fake workflow
    mock_registry.name = "MockRegsitry"
    workflow = MagicMock()
    workflow.uuid = "1111-222"
    workflow.version = "1"
    suite = MagicMock()
    suite.uuid = '111111'
    suite.workflow = workflow
    m.get_suite.return_value = suite
    # the worklow exists but it is not linked to the registry
    m.get_public_workflow_version.return_value = None
    m.get_registry_workflow_version.side_effect = lm_exceptions.NotAuthorizedException
    with pytest.raises(lm_exceptions.Forbidden):
        controllers.suites_get_by_uuid(suite.uuid)
    m.get_suite.assert_called_once()
    m.get_registry_workflow_version.assert_called_once()


@patch("lifemonitor.api.controllers.lm")
def test_get_suite_by_user(m, request_context, mock_user):
    # add one user to the current session
    assert not auth.current_user.is_anonymous, "Unexpected user in session"
    assert auth.current_user == mock_user, "Unexpected user in session"
    logger.debug("Current registry: %r", auth.current_registry)
    assert not auth.current_registry, "Unexpected registry in session"
    # add one fake workflow
    workflow = MagicMock()
    workflow.uuid = "1111-222"
    workflow.version = "1"
    suite = MagicMock()
    suite.uuid = '111111'
    suite.workflow = workflow
    m.get_suite.return_value = suite
    response = controllers.suites_get_by_uuid(suite.uuid)
    m.get_suite.assert_called_once()
    assert isinstance(response, dict), "Unexpected result type"


@patch("lifemonitor.api.controllers.lm")
def test_get_suite_by_registry(m, request_context, mock_registry):
    # add one user to the current session
    assert auth.current_user.is_anonymous, "Unexpected user in session"
    logger.debug("Current registry: %r", auth.current_registry)
    assert auth.current_registry, "Unexpected registry in session"
    # add one fake workflow
    mock_registry.name = "MockRegsitry"
    workflow = MagicMock()
    workflow.uuid = "1111-222"
    workflow.version = "1"
    suite = MagicMock()
    suite.uuid = '111111'
    suite.workflow = workflow
    m.get_suite.return_value = suite
    m.get_registry_workflow_version.return_value = workflow
    response = controllers.suites_get_by_uuid(suite.uuid)
    m.get_suite.assert_called_once()
    assert isinstance(response, dict), "Unexpected result type"


@patch("lifemonitor.api.controllers.lm")
def test_get_suite_status_by_user(m, request_context, no_cache, mock_user):
    # add one user to the current session
    assert not auth.current_user.is_anonymous, "Unexpected user in session"
    assert auth.current_user == mock_user, "Unexpected user in session"
    logger.debug("Current registry: %r", auth.current_registry)
    assert not auth.current_registry, "Unexpected registry in session"
    # add one fake workflow
    workflow = MagicMock()
    workflow.uuid = "1111-222"
    workflow.version = "1"
    suite = MagicMock()
    suite.uuid = '111111'
    suite.workflow = workflow
    m.get_suite.return_value = suite
    response = controllers.suites_get_status(suite.uuid)
    m.get_suite.assert_called_once()
    assert isinstance(response, dict), "Unexpected result type"
    logger.debug("The response: %r", response)
    for p in ["latest_builds", "suite_uuid", "status"]:
        assert p in response, f"Property {p} not found on response"


@patch("lifemonitor.api.controllers.lm")
def test_get_suite_status_by_user_rate_limit_exceeded(lm, mock_user, rate_limit_exceeded_workflow: models.Workflow):
    # add one user to the current session
    assert not auth.current_user.is_anonymous, "Unexpected user in session"
    assert auth.current_user == mock_user, "Unexpected user in session"
    logger.debug("Current registry: %r", auth.current_registry)
    assert not auth.current_registry, "Unexpected registry in session"
    # set workflow
    workflow = rate_limit_exceeded_workflow
    lm.get_public_workflows.return_value = []
    lm.get_user_workflows.return_value = [rate_limit_exceeded_workflow]
    # set suite
    suite: models.TestSuite = workflow.latest_version.test_suites[0]
    lm.get_suite.return_value = suite
    # get and check suite status
    response = controllers.suites_get_status(suite.uuid)
    lm.get_suite.assert_called_once()
    logger.info(response)
    for p in ["latest_builds", "suite_uuid", "status"]:
        assert p in response, f"Property {p} not found on response"
    assert response['status'] == 'not_available'


@patch("lifemonitor.api.controllers.lm")
def test_get_suite_status_by_registry(m, request_context, no_cache, mock_registry):
    # add one user to the current session
    assert auth.current_user.is_anonymous, "Unexpected user in session"
    logger.debug("Current registry: %r", auth.current_registry)
    assert auth.current_registry, "Unexpected registry in session"
    # add one fake workflow
    workflow = MagicMock()
    workflow.uuid = "1111-222"
    workflow.version = "1"
    suite = MagicMock()
    suite.uuid = '111111'
    suite.workflow = workflow
    m.get_suite.return_value = suite
    m.get_public_workflow_version.return_value = None
    m.get_registry_workflow_version.return_value = workflow
    response = controllers.suites_get_status(suite.suite)
    m.get_suite.assert_called_once()
    m.get_registry_workflow_version.assert_called_once()
    assert isinstance(response, dict), "Unexpected result type"
    logger.debug("The response: %r", response)
    for p in ["latest_builds", "suite_uuid", "status"]:
        assert p in response, f"Property {p} not found on response"


@patch("lifemonitor.api.controllers.lm")
def test_get_suite_status_by_registry_rate_limit_exceeded(lm, request_context, mock_registry, rate_limit_exceeded_workflow: models.Workflow):
    # add one user to the current session
    assert auth.current_user.is_anonymous, "Unexpected user in session"
    logger.debug("Current registry: %r", auth.current_registry)
    assert auth.current_registry, "Unexpected registry in session"
    # set workflow
    workflow = rate_limit_exceeded_workflow
    lm.get_public_workflows.return_value = []
    # set suite
    suite: models.TestSuite = workflow.latest_version.test_suites[0]
    lm.get_suite.return_value = suite
    lm.get_registry_workflow_version = workflow.latest_version
    # get and check suite status
    response = controllers.suites_get_status(suite.uuid)
    lm.get_suite.assert_called_once()
    logger.info(response)
    for p in ["latest_builds", "suite_uuid", "status"]:
        assert p in response, f"Property {p} not found on response"
    assert response['status'] == 'not_available'


@patch("lifemonitor.api.controllers.lm")
def test_get_suite_instances_by_user(m, request_context, no_cache, mock_user):
    # add one user to the current session
    assert not auth.current_user.is_anonymous, "Unexpected user in session"
    assert auth.current_user == mock_user, "Unexpected user in session"
    logger.debug("Current registry: %r", auth.current_registry)
    assert not auth.current_registry, "Unexpected registry in session"
    # add one fake workflow
    workflow = MagicMock()
    workflow.uuid = "1111-222"
    workflow.version = "1"
    suite = MagicMock()
    suite.uuid = '111111'
    suite.workflow = workflow
    m.get_suite.return_value = suite
    response = controllers.suites_get_instances(suite.uuid)
    m.get_suite.assert_called_once()
    assert isinstance(response, dict), "Unexpected result type"
    logger.debug("The response: %r", response)
    assert "items" in response, "Missing items property"


@patch("lifemonitor.api.controllers.lm")
def test_get_suite_instances_by_registry(m, request_context, no_cache, mock_registry):
    # add one user to the current session
    assert auth.current_user.is_anonymous, "Unexpected user in session"
    logger.debug("Current registry: %r", auth.current_registry)
    assert auth.current_registry, "Unexpected registry in session"
    # add one fake workflow
    workflow = MagicMock()
    workflow.uuid = "1111-222"
    workflow.version = "1"
    suite = MagicMock()
    suite.uuid = '111111'
    suite.workflow = workflow
    m.get_suite.return_value = suite
    m.get_registry_workflow_version.return_value = suite
    response = controllers.suites_get_instances(suite.uuid)
    m.get_suite.assert_called_once()
    assert isinstance(response, dict), "Unexpected result type"
    logger.debug("The response: %r", response)
    assert "items" in response, "Missing items property"


@patch("lifemonitor.api.controllers.lm")
def test_delete_suite_by_user(m, request_context, mock_user):
    # add one user to the current session
    assert not auth.current_user.is_anonymous, "Unexpected user in session"
    assert auth.current_user == mock_user, "Unexpected user in session"
    logger.debug("Current registry: %r", auth.current_registry)
    assert not auth.current_registry, "Unexpected registry in session"
    # add one fake workflow
    workflow = MagicMock()
    workflow.uuid = "1111-222"
    workflow.version = "1"
    suite = MagicMock()
    suite.uuid = '111111'
    suite.workflow = workflow
    m.get_suite.return_value = suite
    m.deregister_test_suite.return_value = suite.uuid
    response = controllers.suites_delete(suite.uuid)
    logger.debug("Response: %r", response)
    m.get_suite.assert_called_once()
    m.deregister_test_suite.assert_called_once()
    assert_status_code(204, response[1])


@patch("lifemonitor.api.controllers.lm")
def test_delete_suite_by_user_unexpected_error(m, request_context, mock_user):
    # add one user to the current session
    assert not auth.current_user.is_anonymous, "Unexpected user in session"
    assert auth.current_user == mock_user, "Unexpected user in session"
    logger.debug("Current registry: %r", auth.current_registry)
    assert not auth.current_registry, "Unexpected registry in session"
    # add one fake workflow
    workflow = MagicMock()
    workflow.uuid = "1111-222"
    workflow.version = "1"
    suite = MagicMock()
    suite.uuid = '111111'
    suite.workflow = workflow
    m.get_suite.return_value = suite
    m.deregister_test_suite.side_effect = RuntimeError()
    response = controllers.suites_delete(suite.uuid)
    m.get_suite.assert_called_once()
    m.deregister_test_suite.assert_called_once()
    assert_status_code(500, response.status_code)


@patch("lifemonitor.api.controllers.lm")
def test_delete_suite_by_registry(m, request_context, mock_registry):
    # add one user to the current session
    assert auth.current_user.is_anonymous, "Unexpected user in session"
    logger.debug("Current registry: %r", auth.current_registry)
    assert auth.current_registry, "Unexpected registry in session"
    # add one fake workflow
    workflow = MagicMock()
    workflow.uuid = "1111-222"
    workflow.version = "1"
    suite = MagicMock()
    suite.uuid = '111111'
    suite.workflow = workflow
    m.get_suite.return_value = suite
    m.deregister_test_suite.return_value = suite.uuid
    response = controllers.suites_delete(suite.uuid)
    m.get_suite.assert_called_once()
    m.deregister_test_suite.assert_called_once()
    assert_status_code(204, response[1])


@patch("lifemonitor.api.controllers.lm")
def test_delete_suite_by_registry_unexpected_error(m, request_context, mock_registry):
    # add one user to the current session
    assert auth.current_user.is_anonymous, "Unexpected user in session"
    logger.debug("Current registry: %r", auth.current_registry)
    assert auth.current_registry, "Unexpected registry in session"
    # add one fake workflow
    workflow = MagicMock()
    workflow.uuid = "1111-222"
    workflow.version = "1"
    suite = MagicMock()
    suite.uuid = '111111'
    suite.workflow = workflow
    m.get_suite.return_value = suite
    m.deregister_test_suite.return_value = None
    response = controllers.suites_delete(suite.uuid)
    m.get_suite.assert_called_once()
    m.deregister_test_suite.assert_called_once()
    assert_status_code(500, response.status_code)
