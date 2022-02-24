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
import os
from unittest.mock import MagicMock, Mock, patch

import pytest

import lifemonitor.api.controllers as controllers
import lifemonitor.api.models as models
import lifemonitor.auth as auth
import lifemonitor.exceptions as lm_exceptions
import lifemonitor.lang.messages as messages
from flask import Response
from tests.utils import assert_status_code

logger = logging.getLogger(__name__)


@patch("lifemonitor.api.controllers.lm")
def test_get_instance_error_not_found(m, request_context, mock_user):
    assert not auth.current_user.is_anonymous, "Unexpected user in session"
    assert auth.current_registry is not None, "Unexpected registry in session"
    m.get_test_instance.return_value = None
    response = controllers.instances_get_by_id("123456")
    m.get_test_instance.assert_called_once()
    assert_status_code(404, response.status_code)


@patch("lifemonitor.api.controllers.lm")
def test_get_instance_by_user_error_forbidden(m, request_context, mock_user):
    assert not auth.current_user.is_anonymous, "Unexpected user in session"
    assert auth.current_registry is not None, "Unexpected registry in session"
    # Mock instance
    workflow = MagicMock()
    workflow.uuid = "1111-222"
    instance = MagicMock()
    instance.uuid = '12345'
    instance.suite = MagicMock()
    instance.suite.uuid = '1111'
    instance.test_suite.workflow = workflow
    m.get_test_instance.return_value = instance
    m.get_user_workflows.return_value = []
    m.get_suite.return_value = instance.suite
    m.get_public_workflow_version.return_value = None
    m.get_user_workflow_version = Mock(side_effect=lm_exceptions.NotAuthorizedException)
    # m.get_registry_workflow_version = workflow
    with pytest.raises(lm_exceptions.Forbidden):
        controllers.instances_get_by_id(instance['uuid'])
    m.get_test_instance.assert_called_once()
    m.get_suite.assert_called_once()
    m.get_user_workflow_version.assert_called_once()


@patch("lifemonitor.api.controllers.lm")
def test_get_instance_by_user(m, request_context, no_cache, mock_user):
    assert not auth.current_user.is_anonymous, "Unexpected user in session"
    assert auth.current_registry is not None, "Unexpected registry in session"
    workflow = MagicMock()
    workflow.uuid = "1111-222"
    instance = MagicMock()
    instance.uuid = '12345'
    instance.suite = MagicMock()
    instance.suite.uuid = '1111'
    instance.test_suite.workflow = workflow
    m.get_test_instance.return_value = instance
    m.get_user_workflows.return_value = []
    m.get_suite.return_value = instance.suite
    m.get_public_workflow_version.return_value = None
    m.get_user_workflow_version = workflow
    response = controllers.instances_get_by_id(instance['uuid'])
    m.get_test_instance.assert_called_once()
    m.get_suite.assert_called_once()
    m.get_user_workflow_version.assert_called_once()
    assert not isinstance(response, Response), "Unexpected response type"
    assert isinstance(response, dict), "Unexpected response type"


@patch("lifemonitor.api.controllers.lm")
def test_get_instance_build_by_user_error_not_found(m, request_context, no_cache, mock_user):
    assert not auth.current_user.is_anonymous, "Unexpected user in session"
    assert auth.current_registry is not None, "Unexpected registry in session"
    instance = MagicMock()
    instance.get_test_build.side_effect = \
        lm_exceptions.EntityNotFoundException(models.TestBuild)
    m.get_test_instance.return_value = instance
    response = controllers.instances_builds_get_by_id('111', '12345')
    logger.debug("Response: %r", response)
    m.get_test_instance.assert_called_once()
    assert isinstance(response, Response), "Unexpected response type"
    assert_status_code(404, response.status_code)


@patch("lifemonitor.api.controllers.lm")
def test_get_instance_build_by_user(m, request_context, mock_user):
    assert not auth.current_user.is_anonymous, "Unexpected user in session"
    assert auth.current_registry is not None, "Unexpected registry in session"
    build = MagicMock()
    build.id = "1"
    workflow = MagicMock()
    workflow.uuid = "1111-222"
    instance = MagicMock()
    instance.uuid = '12345'
    instance.suite = MagicMock()
    instance.suite.uuid = '1111'
    instance.get_test_build.return_value = build
    instance.test_suite.workflow = workflow
    m.get_test_instance.return_value = instance
    m.get_user_workflows.return_value = []
    m.get_suite.return_value = instance.suite
    m.get_public_workflow_version.return_value = None
    m.get_user_workflow_version = workflow
    response = controllers.instances_builds_get_by_id(instance['uuid'], build.id)
    m.get_test_instance.assert_called_once()
    m.get_suite.assert_called_once()
    m.get_user_workflow_version.assert_called_once()
    assert isinstance(response, dict), "Unexpected response type"


@patch("lifemonitor.api.controllers.lm")
def test_get_instance_build_by_user_rate_limit_exceeded(lm, request_context, mock_user, rate_limit_exceeded_workflow: models.Workflow):
    assert not auth.current_user.is_anonymous, "Unexpected user in session"
    assert auth.current_registry is not None, "Unexpected registry in session"
    # set workflow
    workflow = rate_limit_exceeded_workflow
    lm.get_public_workflows.return_value = []
    lm.get_user_workflows.return_value = [rate_limit_exceeded_workflow]
    # set suite
    suite: models.TestSuite = workflow.latest_version.test_suites[0]
    lm.get_suite.return_value = suite
    # set instance
    instance: models.TestInstance = suite.test_instances[0]
    lm.get_test_instance.return_value = instance
    # get and check suite status
    response = controllers.instances_builds_get_by_id(instance.uuid, "123")
    logger.debug(response.data)
    lm.get_test_instance.assert_called_once()
    lm.get_suite.assert_called_once()
    data = json.loads(response.data)
    assert isinstance(data, dict), "Unexpected response type"
    assert 403 == int(data["status"]), "Unexpected status code"
    assert "Rate Limit Exceeded" == data["title"], "Unexpected error title"


@patch("lifemonitor.api.controllers.lm")
def test_get_instance_build_last_logs_by_user(m, request_context, no_cache, mock_user):
    assert not auth.current_user.is_anonymous, "Unexpected user in session"
    assert auth.current_registry is not None, "Unexpected registry in session"
    workflow = {"uuid": "1111-222"}
    build = MagicMock()
    build.id = "1"
    build.output = os.urandom(2048)
    workflow = MagicMock()
    workflow.uuid = "1111-222"
    instance = MagicMock()
    instance.uuid = '12345'
    instance.suite = MagicMock()
    instance.suite.uuid = '1111'
    instance.get_test_build.return_value = build
    instance.test_suite.workflow = workflow
    m.get_public_workflow_version.return_value = None
    response = controllers.instances_builds_get_by_id(instance['uuid'], build.id)
    m.get_test_instance.assert_called_once()
    m.get_suite.assert_called_once()
    m.get_user_workflow_version.assert_called_once()
    assert isinstance(response, dict), "Unexpected response type"
    logger.debug("The loaded instance: %r", response)


@patch("lifemonitor.api.controllers.lm")
def test_get_instance_build_logs_by_user_invalid_offset(m, request_context, mock_user):
    assert not auth.current_user.is_anonymous, "Unexpected user in session"
    assert auth.current_registry is not None, "Unexpected registry in session"
    workflow = {"uuid": "1111-222"}
    build = MagicMock()
    build.id = "1"
    default_limit = 131072
    build.output = str(os.urandom(default_limit))
    workflow = MagicMock()
    workflow.uuid = "1111-222"
    instance = MagicMock()
    instance.uuid = '12345'
    instance.suite = MagicMock()
    instance.suite.uuid = '1111'
    instance.get_test_build.return_value = build
    instance.test_suite.workflow = workflow
    # test get logs defaults offset and limit
    response = controllers.instances_builds_get_logs(instance['uuid'], build.id, offset_bytes=-1000)
    logger.debug("Response: %r", response)
    assert response.status_code == 400, "Unexpected response"
    error = json.loads(response.data)
    logger.debug("Error object: %r", error)
    assert isinstance(error, dict), "Unexpected response type"
    assert messages.invalid_log_offset in error["detail"], "Unexpected error message"


@patch("lifemonitor.api.controllers.lm")
def test_get_instance_build_logs_by_user_invalid_limit(m, request_context, mock_user):
    assert not auth.current_user.is_anonymous, "Unexpected user in session"
    assert auth.current_registry is not None, "Unexpected registry in session"
    workflow = {"uuid": "1111-222"}
    build = MagicMock()
    build.id = "1"
    default_limit = 131072
    build.output = str(os.urandom(default_limit))
    instance = MagicMock()
    instance.uuid = '12345'
    instance.get_test_build.return_value = build
    instance.test_suite.workflow = workflow
    m.get_test_instance.return_value = instance
    m.get_user_workflows.return_value = [workflow]
    # test get logs defaults offset and limit
    response = controllers.instances_builds_get_logs(instance['uuid'], build.id, limit_bytes=-1000)
    logger.debug("Response: %r", response)
    assert response.status_code == 400, "Unexpected response"
    error = json.loads(response.data)
    logger.debug("Error object: %r", error)
    assert isinstance(error, dict), "Unexpected response type"
    assert messages.invalid_log_limit in error["detail"], "Unexpected error message"


@patch("lifemonitor.api.controllers.lm")
def test_get_instance_build_logs_by_user(m, request_context, mock_user):
    assert not auth.current_user.is_anonymous, "Unexpected user in session"
    assert auth.current_registry is not None, "Unexpected registry in session"
    # pagination settings
    default_limit = 131072
    parts = 4
    part_size = round(default_limit / parts)
    logger.debug("Number of parts: %d", parts)
    logger.debug("Part size: %d", part_size)
    # set workflow/test_instance/test_build
    workflow = {"uuid": "1111-222"}
    build = MagicMock()
    build.id = "1"
    output_part = str("n" * part_size)
    build.get_output.return_value = output_part
    logger.debug("Part length: %r", len(output_part))
    workflow = MagicMock()
    workflow.uuid = "1111-222"
    instance = MagicMock()
    instance.uuid = '12345'
    instance.suite = MagicMock()
    instance.suite.uuid = '1111'
    instance.get_test_build.return_value = build
    instance.test_suite.workflow = workflow
    m.get_test_instance.return_value = instance
    m.get_public_workflow_version.return_value = None
    m.get_user_workflows.return_value = []
    m.get_suite.return_value = instance.suite
    m.get_user_workflow_version = workflow
    # test get logs defaults offset and limit
    response = controllers.instances_builds_get_logs(instance['uuid'], build.id)
    m.get_test_instance.assert_called_once()
    m.get_suite.assert_called_once()
    m.get_user_workflow_version.assert_called_once()
    assert isinstance(response, str), "Unexpected response type"
    assert len(response) == part_size, f"Unexpected log length: it should be limited to {part_size} bytes"
    # test pagination
    for n in range(0, parts):
        # test get logs defaults offset and limit
        response = controllers.instances_builds_get_logs(
            instance['uuid'], build.id,
            limit_bytes=part_size, offset_bytes=part_size * n)
        assert isinstance(response, str), "Unexpected response type"
        assert len(response) == part_size, f"Unexpected log length: it should be limited to {part_size} bytes"


@patch("lifemonitor.api.controllers.lm")
def test_get_instance_by_registry_error_forbidden(m, request_context, mock_registry):
    assert auth.current_user.is_anonymous, "Unexpected user in session"
    assert auth.current_registry, "Unexpected registry in session"
    workflow = MagicMock()
    workflow.uuid = "1111-222"
    instance = MagicMock()
    instance.uuid = '12345'
    instance.suite = MagicMock()
    instance.suite.uuid = '1111'
    instance.test_suite.workflow = workflow
    m.get_test_instance.return_value = instance
    m.get_user_workflows.return_value = []
    m.get_suite.return_value = instance.suite
    m.get_public_workflow_version.return_value = None
    m.get_registry_workflow_version = Mock(side_effect=lm_exceptions.NotAuthorizedException)
    with pytest.raises(lm_exceptions.Forbidden):
        controllers.instances_get_by_id(instance['uuid'])
    m.get_test_instance.assert_called_once()


@patch("lifemonitor.api.controllers.lm")
def test_get_instance_by_registry_error_not_found(m, request_context, no_cache, mock_registry):
    assert auth.current_user.is_anonymous, "Unexpected user in session"
    assert auth.current_registry, "Unexpected registry in session"
    workflow = {"uuid": "1111-222"}
    instance = MagicMock()
    instance.uuid = '12345'
    instance.test_suite.workflow = workflow
    m.get_test_instance.return_value = instance
    mock_registry.registered_workflow_versions = [workflow]
    response = controllers.instances_get_by_id(instance['uuid'])
    m.get_test_instance.assert_called_once()
    assert isinstance(response, dict), "Unexpected response type"


@patch("lifemonitor.api.controllers.lm")
def test_get_instance_build_by_registry_error_not_found(m, request_context, no_cache, mock_registry):
    assert auth.current_user.is_anonymous, "Unexpected user in session"
    assert auth.current_registry, "Unexpected registry in session"
    build = MagicMock()
    build.id = "1"
    workflow = {'uuid': '11111'}
    instance = MagicMock()
    instance.uuid = '12345'
    instance.get_test_build = Mock(side_effect=lm_exceptions.EntityNotFoundException(models.TestBuild))
    instance.test_suite.workflow = workflow
    m.get_test_instance.return_value = instance
    mock_registry.registered_workflow_versions = [workflow]
    response = controllers.instances_builds_get_by_id(instance['uuid'], '2222')
    m.get_test_instance.assert_called_once()
    assert isinstance(response, Response), "Unexpected response type"
    assert_status_code(404, response.status_code)


@patch("lifemonitor.api.controllers.lm")
def test_get_instance_build_by_registry(m, request_context, mock_registry):
    assert auth.current_user.is_anonymous, "Unexpected user in session"
    assert auth.current_registry, "Unexpected registry in session"
    build = MagicMock()
    build.id = "1"
    workflow = {'uuid': '11111'}
    instance = MagicMock()
    instance.uuid = '12345'
    instance.test_builds.return_value = [build]
    instance.test_suite.workflow = workflow
    m.get_test_instance.return_value = instance
    mock_registry.registered_workflow_versions = [workflow]
    response = controllers.instances_builds_get_by_id(instance['uuid'], build.id)
    m.get_test_instance.assert_called_once()
    assert isinstance(response, dict), "Unexpected response type"


@patch("lifemonitor.api.controllers.lm")
def test_get_instance_build_by_registry_rate_limit_exceeded(lm, request_context, mock_registry, rate_limit_exceeded_workflow: models.Workflow):
    assert auth.current_user.is_anonymous, "Unexpected user in session"
    assert auth.current_registry, "Unexpected registry in session"
    # set workflow
    workflow = rate_limit_exceeded_workflow
    lm.get_public_workflows.return_value = []
    lm.get_user_workflows.return_value = [rate_limit_exceeded_workflow]
    # set suite
    suite: models.TestSuite = workflow.latest_version.test_suites[0]
    lm.get_suite.return_value = suite
    # set instance
    instance: models.TestInstance = suite.test_instances[0]
    lm.get_test_instance.return_value = instance
    # get and check suite status
    response = controllers.instances_builds_get_by_id(instance.uuid, "123")
    logger.debug(response.data)
    lm.get_test_instance.assert_called_once()
    lm.get_suite.assert_called_once()
    data = json.loads(response.data)
    assert isinstance(data, dict), "Unexpected response type"
    assert 403 == int(data["status"]), "Unexpected status code"
    assert "Rate Limit Exceeded" == data["title"], "Unexpected error title"
