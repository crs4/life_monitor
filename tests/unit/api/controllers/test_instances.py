import os
import json
import pytest
import logging
from flask import Response
import lifemonitor.auth as auth
import lifemonitor.api.models as models
import lifemonitor.api.controllers as controllers
import lifemonitor.lang.messages as messages
from lifemonitor.common import EntityNotFoundException
from unittest.mock import MagicMock, Mock, patch
from tests.utils import assert_status_code


logger = logging.getLogger(__name__)


@patch("lifemonitor.api.controllers.lm")
def test_get_instances_no_authorization(m, request_context):
    assert auth.current_user.is_anonymous, "Unexpected user in session"
    assert auth.current_registry is not None, "Unexpected registry in session"
    with pytest.raises(auth.NotAuthorizedException):
        controllers.instances_get_by_id("1234")


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
    workflow = {"uuid": "1111-222"}
    instance = MagicMock()
    instance.uuid = '12345'
    instance.test_suite.workflow = workflow
    m.get_test_instance.return_value = instance
    m.get_user_workflows.return_value = []
    response = controllers.instances_get_by_id(instance['uuid'])
    m.get_test_instance.assert_called_once()
    m.get_user_workflows.assert_called_once()
    assert_status_code(403, response.status_code)


@patch("lifemonitor.api.controllers.lm")
def test_get_instance_by_user(m, request_context, mock_user):
    assert not auth.current_user.is_anonymous, "Unexpected user in session"
    assert auth.current_registry is not None, "Unexpected registry in session"
    workflow = {"uuid": "1111-222"}
    instance = MagicMock()
    instance.uuid = '12345'
    instance.test_suite.workflow = workflow
    m.get_test_instance.return_value = instance
    m.get_user_workflows.return_value = [workflow]
    response = controllers.instances_get_by_id(instance['uuid'])
    m.get_test_instance.assert_called_once()
    m.get_user_workflows.assert_called_once()
    assert not isinstance(response, Response), "Unexpected response type"
    assert isinstance(response, dict), "Unexpected response type"


@patch("lifemonitor.api.controllers.lm")
def test_get_instance_build_by_user_error_not_found(m, request_context, mock_user):
    assert not auth.current_user.is_anonymous, "Unexpected user in session"
    assert auth.current_registry is not None, "Unexpected registry in session"
    workflow = {"uuid": "1111-222"}
    instance = MagicMock()
    instance.uuid = '12345'
    instance.get_test_build = Mock(side_effect=EntityNotFoundException(models.TestBuild))
    instance.test_suite.workflow = workflow
    m.get_test_instance.return_value = instance
    m.get_user_workflows.return_value = [workflow]
    response = controllers.instances_builds_get_by_id(instance['uuid'], '12345')
    m.get_test_instance.assert_called_once()
    m.get_user_workflows.assert_called_once()
    assert isinstance(response, Response), "Unexpected response type"
    assert_status_code(404, response.status_code)


@patch("lifemonitor.api.controllers.lm")
def test_get_instance_build_by_user(m, request_context, mock_user):
    assert not auth.current_user.is_anonymous, "Unexpected user in session"
    assert auth.current_registry is not None, "Unexpected registry in session"
    workflow = {"uuid": "1111-222"}
    build = MagicMock()
    build.id = "1"
    instance = MagicMock()
    instance.uuid = '12345'
    instance.test_builds.return_value = [build]
    instance.test_suite.workflow = workflow
    m.get_test_instance.return_value = instance
    m.get_user_workflows.return_value = [workflow]
    response = controllers.instances_builds_get_by_id(instance['uuid'], build.id)
    m.get_test_instance.assert_called_once()
    m.get_user_workflows.assert_called_once()
    assert isinstance(response, dict), "Unexpected response type"


@patch("lifemonitor.api.controllers.lm")
def test_get_instance_build_last_logs_by_user(m, request_context, mock_user):
    assert not auth.current_user.is_anonymous, "Unexpected user in session"
    assert auth.current_registry is not None, "Unexpected registry in session"
    workflow = {"uuid": "1111-222"}
    build = MagicMock()
    build.id = "1"
    build.output = os.urandom(2048)
    instance = MagicMock()
    instance.uuid = '12345'
    instance.get_test_build.return_value = build
    instance.test_suite.workflow = workflow
    m.get_test_instance.return_value = instance
    m.get_user_workflows.return_value = [workflow]
    response = controllers.instances_builds_get_by_id(instance['uuid'], build.id)
    m.get_test_instance.assert_called_once()
    m.get_user_workflows.assert_called_once()
    assert isinstance(response, dict), "Unexpected response type"
    logger.debug("The loaded instance: %r", response)
    assert len(response["last_logs"]) == 400, "Unexpected log length: it should be limited to the last 400 chars"


@patch("lifemonitor.api.controllers.lm")
def test_get_instance_build_logs_by_user_invalid_offset(m, request_context, mock_user):
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
    response = controllers.instances_builds_get_logs(instance['uuid'], build.id)
    m.get_test_instance.assert_called_once()
    m.get_user_workflows.assert_called_once()
    logger.debug("Response: %r", response)
    assert isinstance(response, str), "Unexpected response type"
    logger.debug("The loaded logs: %r", response)
    assert len(response) == default_limit, "Unexpected log length: it should be limited to the last 400 chars"
    # test pagination
    parts = 4
    part_size = round(default_limit / parts)
    logger.debug("Number of parts: %d", parts)
    logger.debug("Part size: %d", part_size)
    for n in range(0, parts):
        # test get logs defaults offset and limit
        response = controllers.instances_builds_get_logs(
            instance['uuid'], build.id,
            limit_bytes=part_size, offset_bytes=part_size * n)
        logger.debug("Response: %r", response)
        assert isinstance(response, str), "Unexpected response type"
        logger.debug("The loaded logs: %r", response)
        assert len(response) == part_size, "Unexpected log length: it should be limited to the last 400 chars"


@patch("lifemonitor.api.controllers.lm")
def test_get_instance_by_registry_error_forbidden(m, request_context, mock_registry):
    assert auth.current_user.is_anonymous, "Unexpected user in session"
    assert auth.current_registry, "Unexpected registry in session"
    workflow = {"uuid": "1111-222"}
    instance = MagicMock()
    instance.uuid = '12345'
    instance.test_suite.workflow = workflow
    m.get_test_instance.return_value = instance
    mock_registry.registered_workflows = []
    response = controllers.instances_get_by_id(instance['uuid'])
    m.get_test_instance.assert_called_once()
    assert isinstance(response, Response), "Unexpected response type"
    assert_status_code(403, response.status_code)


@patch("lifemonitor.api.controllers.lm")
def test_get_instance_by_registry_error_not_found(m, request_context, mock_registry):
    assert auth.current_user.is_anonymous, "Unexpected user in session"
    assert auth.current_registry, "Unexpected registry in session"
    workflow = {"uuid": "1111-222"}
    instance = MagicMock()
    instance.uuid = '12345'
    instance.test_suite.workflow = workflow
    m.get_test_instance.return_value = instance
    mock_registry.registered_workflows = [workflow]
    response = controllers.instances_get_by_id(instance['uuid'])
    m.get_test_instance.assert_called_once()
    assert isinstance(response, dict), "Unexpected response type"


@patch("lifemonitor.api.controllers.lm")
def test_get_instance_build_by_registry_error_not_found(m, request_context, mock_registry):
    assert auth.current_user.is_anonymous, "Unexpected user in session"
    assert auth.current_registry, "Unexpected registry in session"
    build = MagicMock()
    build.id = "1"
    workflow = {'uuid': '11111'}
    instance = MagicMock()
    instance.uuid = '12345'
    instance.get_test_build = Mock(side_effect=EntityNotFoundException(models.TestBuild))
    instance.test_suite.workflow = workflow
    m.get_test_instance.return_value = instance
    mock_registry.registered_workflows = [workflow]
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
    mock_registry.registered_workflows = [workflow]
    response = controllers.instances_builds_get_by_id(instance['uuid'], build.id)
    m.get_test_instance.assert_called_once()
    assert isinstance(response, dict), "Unexpected response type"
