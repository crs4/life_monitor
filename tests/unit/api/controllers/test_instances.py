import pytest
import logging
from flask import Response
import lifemonitor.auth as auth
import lifemonitor.api.models as models
import lifemonitor.api.controllers as controllers
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
