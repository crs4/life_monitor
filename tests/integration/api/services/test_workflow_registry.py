import os
import pytest
import logging
import pathlib
from lifemonitor.api.services import LifeMonitor
from lifemonitor.api.models import WorkflowRegistry
from sqlalchemy import exc as sql_exceptions
from lifemonitor.common import (
    WorkflowRegistryNotSupportedException
)

this_dir = os.path.dirname(os.path.abspath(__file__))
tests_root_dir = pathlib.Path(this_dir).parent

logger = logging.getLogger()


def test_workflow_registry_registration(app_client, provider_type,
                                        random_string, fake_uri):
    redirect_uris = f"{fake_uri},{fake_uri}"
    registry = LifeMonitor.get_instance().add_workflow_registry(
        provider_type.value, random_string, random_string, random_string, fake_uri, redirect_uris)

    assert isinstance(registry, WorkflowRegistry), "Unexpected object instance"
    logger.debug("Create registry: %r", registry)
    assert registry.uuid is not None, "Invalid registry identifier"
    assert registry.name == random_string, "Unexpected registry name"
    assert registry.uri == fake_uri, "Unexpected registry URI"
    assert registry.client_credentials.redirect_uris == redirect_uris.split(','), \
        "Unexpected redirect_uri URI"


def test_workflow_registry_registration_error_invalid_type(app_client,
                                                           random_string, fake_uri):
    with pytest.raises(WorkflowRegistryNotSupportedException):
        LifeMonitor.get_instance().add_workflow_registry(
            "jenkins", random_string,
            random_string, random_string, fake_uri)


def test_workflow_registry_registration_error_exists(app_client, provider_type,
                                                     random_string, fake_uri):
    registry = LifeMonitor.get_instance().add_workflow_registry(
        provider_type.value, random_string,
        random_string, random_string, fake_uri)

    assert isinstance(registry, WorkflowRegistry), "Unexpected object instance"
    with pytest.raises(sql_exceptions.IntegrityError):
        LifeMonitor.get_instance().add_workflow_registry(
            provider_type.value,
            random_string, random_string, random_string, fake_uri)


def test_workflow_registry_update(app_client, provider_type, random_string, fake_uri):
    try:
        registry = LifeMonitor.get_instance().add_workflow_registry(
            provider_type.value, random_string,
            random_string, random_string, fake_uri)

        assert isinstance(registry, WorkflowRegistry), "Unexpected object instance"
        logger.debug("Create registry: %r", registry)

        new_random_string = f"{random_string}_updated"
        new_fake_uri = f"{fake_uri}_updated"
        new_redirect_uris = f"{fake_uri},{fake_uri}/updated"
        updated_registry = LifeMonitor.get_instance().update_workflow_registry(
            registry.uuid, new_random_string,
            new_random_string, new_random_string, new_fake_uri, new_redirect_uris)

        assert updated_registry.uuid is not None, "Invalid registry identifier"
        assert updated_registry.name == new_random_string, "Unexpected registry name"
        assert updated_registry.uri == new_fake_uri, "Unexpected registry URI"
        assert updated_registry.client_credentials.redirect_uris == new_redirect_uris.split(','), \
            "Unexpected redirect_uri URI"
    except Exception as e:
        logger.exception(e)
