import pytest
import logging

import lifemonitor.auth as auth
import lifemonitor.api.controllers as controllers

from lifemonitor.lang import messages
from lifemonitor.auth.models import User
from unittest.mock import MagicMock, patch
from tests.conftest import assert_status_code


logger = logging.getLogger(__name__)


@pytest.fixture
def user():
    u = User()
    u.username = "lifemonitor_user"
    auth.login_user(u)
    yield u
    auth.logout_user()


@pytest.fixture
def registry():
    r = MagicMock()
    r.name = "WorkflowRegistry"
    auth.login_registry(r)
    yield r
    auth.logout_registry()


@patch("lifemonitor.api.controllers.lm")
def test_get_suites_no_authorization(m, base_request_context):
    assert auth.current_user.is_anonymous, "Unexpected user in session"
    assert auth.current_registry is not None, "Unexpected registry in session"
    with pytest.raises(auth.NotAuthorizedException):
        controllers.suites_get_by_uuid()


@patch("lifemonitor.api.controllers.lm")
def test_get_suite_error_not_found(m, base_request_context, user):
    assert not auth.current_user.is_anonymous, "Unexpected user in session"
    assert auth.current_registry is not None, "Unexpected registry in session"
    m.get_suite.return_value = None
    response = controllers.suites_get_by_uuid("123456")
    m.get_suite.assert_called_once()
    assert_status_code(response.status_code, 404), "Unexpected status code"


@patch("lifemonitor.api.controllers.lm")
def test_get_suite_by_user_without_auth_access_to_workflow(m, base_request_context, user):
    # add one user to the current session
    assert not auth.current_user.is_anonymous, "Unexpected user in session"
    assert auth.current_user == user, "Unexpected user in session"
    logger.debug("Current registry: %r", auth.current_registry)
    assert not auth.current_registry, "Unexpected registry in session"
    # add one fake workflow
    data = {"uuid": "123456"}
    suite = MagicMock()
    w = {'uuid': '11111'}
    suite.workflow = w
    m.get_user_workflows.return_value = []
    m.get_suite.return_value = suite
    response = controllers.suites_get_by_uuid(data["uuid"])
    m.get_user_workflows.assert_called_once()
    m.get_suite.assert_called_once()
    assert response.status_code == 403, "The user should not be able to access"
    assert messages.unauthorized_user_suite_access.format(user.username, data['uuid']) in response.data.decode()


@patch("lifemonitor.api.controllers.lm")
def test_get_suite_by_registry_without_auth_access_to_workflow(m, base_request_context, registry):
    # add one user to the current session
    assert auth.current_user.is_anonymous, "Unexpected user in session"
    logger.debug("Current registry: %r", auth.current_registry)
    assert auth.current_registry, "Unexpected registry in session"
    # add one fake workflow
    data = {"uuid": "123456"}
    suite = MagicMock()
    w = {'uuid': '11111'}
    suite.workflow = w
    registry.registered_workflows = []
    m.get_suite.return_value = suite
    response = controllers.suites_get_by_uuid(data["uuid"])
    m.get_suite.assert_called_once()
    assert response.status_code == 403, "The registry should not be able to access"
    assert messages.unauthorized_registry_suite_access.format(registry.name, data['uuid']) in response.data.decode()


@patch("lifemonitor.api.controllers.lm")
def test_get_suite_by_user(m, base_request_context, user):
    # add one user to the current session
    assert not auth.current_user.is_anonymous, "Unexpected user in session"
    assert auth.current_user == user, "Unexpected user in session"
    logger.debug("Current registry: %r", auth.current_registry)
    assert not auth.current_registry, "Unexpected registry in session"
    # add one fake workflow
    data = {"uuid": "123456"}
    suite = MagicMock()
    w = {'uuid': '11111'}
    suite.workflow = w
    m.get_user_workflows.return_value = [w]
    m.get_suite.return_value = suite
    response = controllers.suites_get_by_uuid(data["uuid"])
    m.get_suite.assert_called_once()
    assert isinstance(response, dict), "Unexpected result type"


@patch("lifemonitor.api.controllers.lm")
def test_get_suite_by_registry(m, base_request_context, registry):
    # add one user to the current session
    assert auth.current_user.is_anonymous, "Unexpected user in session"
    logger.debug("Current registry: %r", auth.current_registry)
    assert auth.current_registry, "Unexpected registry in session"
    # add one fake workflow
    data = {"uuid": "123456"}
    suite = MagicMock()
    w = {'uuid': '11111'}
    suite.workflow = w
    registry.registered_workflows = [w]
    m.get_suite.return_value = suite
    response = controllers.suites_get_by_uuid(data["uuid"])
    m.get_suite.assert_called_once()
    assert isinstance(response, dict), "Unexpected result type"


@patch("lifemonitor.api.controllers.lm")
def test_get_suite_status_by_user(m, base_request_context, user):
    # add one user to the current session
    assert not auth.current_user.is_anonymous, "Unexpected user in session"
    assert auth.current_user == user, "Unexpected user in session"
    logger.debug("Current registry: %r", auth.current_registry)
    assert not auth.current_registry, "Unexpected registry in session"
    # add one fake workflow
    data = {"uuid": "123456"}
    suite = MagicMock()
    w = {'uuid': '11111'}
    suite.workflow = w
    m.get_user_workflows.return_value = [w]
    m.get_suite.return_value = suite
    response = controllers.suites_get_status(data["uuid"])
    m.get_suite.assert_called_once()
    assert isinstance(response, dict), "Unexpected result type"
    logger.debug("The response: %r", response)
    for p in ["latest_builds", "suite_uuid", "status"]:
        assert p in response, f"Property {p} not found on response"


@patch("lifemonitor.api.controllers.lm")
def test_get_suite_status_by_registry(m, base_request_context, registry):
    # add one user to the current session
    assert auth.current_user.is_anonymous, "Unexpected user in session"
    logger.debug("Current registry: %r", auth.current_registry)
    assert auth.current_registry, "Unexpected registry in session"
    # add one fake workflow
    data = {"uuid": "123456"}
    suite = MagicMock()
    w = {'uuid': '11111'}
    suite.workflow = w
    registry.registered_workflows = [w]
    m.get_suite.return_value = suite
    response = controllers.suites_get_status(data["uuid"])
    m.get_suite.assert_called_once()
    assert isinstance(response, dict), "Unexpected result type"
    logger.debug("The response: %r", response)
    for p in ["latest_builds", "suite_uuid", "status"]:
        assert p in response, f"Property {p} not found on response"


@patch("lifemonitor.api.controllers.lm")
def test_get_suite_instances_by_user(m, base_request_context, user):
    # add one user to the current session
    assert not auth.current_user.is_anonymous, "Unexpected user in session"
    assert auth.current_user == user, "Unexpected user in session"
    logger.debug("Current registry: %r", auth.current_registry)
    assert not auth.current_registry, "Unexpected registry in session"
    # add one fake workflow
    data = {"uuid": "123456"}
    suite = MagicMock()
    w = {'uuid': '11111'}
    suite.workflow = w
    m.get_user_workflows.return_value = [w]
    m.get_suite.return_value = suite
    response = controllers.suites_get_instances(data["uuid"])
    m.get_suite.assert_called_once()
    assert isinstance(response, dict), "Unexpected result type"
    logger.debug("The response: %r", response)
    assert "items" in response, "Missing items property"


@patch("lifemonitor.api.controllers.lm")
def test_get_suite_instances_by_registry(m, base_request_context, registry):
    # add one user to the current session
    assert auth.current_user.is_anonymous, "Unexpected user in session"
    logger.debug("Current registry: %r", auth.current_registry)
    assert auth.current_registry, "Unexpected registry in session"
    # add one fake workflow
    data = {"uuid": "123456"}
    suite = MagicMock()
    w = {'uuid': '11111'}
    suite.workflow = w
    registry.registered_workflows = [w]
    m.get_suite.return_value = suite
    response = controllers.suites_get_instances(data["uuid"])
    m.get_suite.assert_called_once()
    assert isinstance(response, dict), "Unexpected result type"
    logger.debug("The response: %r", response)
    assert "items" in response, "Missing items property"
