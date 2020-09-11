import os
import pytest
import logging
import pathlib

from lifemonitor.common import EntityNotFoundException
from tests.conftest import RegistryType, SecurityType
from lifemonitor.api.models import WorkflowRegistry, Workflow, JenkinsTestingService
from lifemonitor.api.services import LifeMonitor

this_dir = os.path.dirname(os.path.abspath(__file__))
tests_root_dir = pathlib.Path(this_dir).parent

logger = logging.getLogger()


def test_workflow_registration(app_context, clean_db, user, workflow):
    r = WorkflowRegistry.get_instance()
    logger.debug(r._client.api_base_url)
    logger.debug("Workflows: %r", r.get_workflows())
    lm = LifeMonitor.get_instance()
    lm.register_workflow(workflow['uuid'], workflow['version'],
                         workflow['roc_link'], workflow['name'])


def test_jenkins_service_type(app_context, user, workflow):
    w = Workflow.find_by_id(workflow['uuid'], workflow['version'])
    suite = w.test_suites[0]
    conf = suite.test_configurations[0]
    service = conf.testing_service
    assert isinstance(service, JenkinsTestingService), "Unexpected type for service"
    assert service.server is not None, "Not found _server property"


def test_workflow_info(app_context, user, workflow):
    lm = LifeMonitor.get_instance()
    w = lm.get_registered_workflow(workflow['uuid'], workflow['version'])
    assert isinstance(w, Workflow), "Object is not an instance of Workflow"


def test_suite_registration(app_context, user, workflow, test_suite_metadata):
    lm = LifeMonitor.get_instance()
    w = lm.get_registered_workflow(workflow['uuid'], workflow['version'])
    assert isinstance(w, Workflow), "Object is not an instance of Workflow"
    logger.debug("TestDefinition: %r", test_suite_metadata)
    current_number_of_suites = len(w.test_suites)
    suite = lm.register_test_suite(workflow['uuid'], workflow['version'], test_suite_metadata)
    logger.debug("Number of suites: %r", len(suite.workflow.test_suites))
    assert len(suite.workflow.test_suites) == current_number_of_suites + 1, \
        "Unexpected number of test_suites for the workflow {}".format(suite.workflow.uuid)
    logger.debug("Project: %r", suite)
    assert len(suite.tests) == 1, "Unexpected number of tests for the testing project {}".format(suite)
    for t in suite.tests:
        logger.debug("- test: %r", t)
    assert len(suite.test_configurations) == 1, "Unexpected number of test_configurations " \
                                                "for the testing project {}".format(suite)
    for t in suite.test_configurations:
        logger.debug("- test instance: %r --> Service: %r,%s", t, t.testing_service, t.testing_service.url)


def test_suite_registration_exception(app_context, user, random_workflow_id, test_suite_metadata):
    with pytest.raises(EntityNotFoundException):
        LifeMonitor.get_instance().register_test_suite(random_workflow_id['uuid'],
                                                       random_workflow_id['version'],
                                                       test_suite_metadata)


def test_suite_deregistration(app_context, user, workflow):
    lm = LifeMonitor.get_instance()
    w = lm.get_registered_workflow(workflow['uuid'], workflow['version'])
    assert isinstance(w, Workflow), "Object is not an instance of Workflow"
    assert len(w.test_suites) > 0, "No test suite found for this workflow"
    current_number_of_suites = len(w.test_suites)
    # pick the first suite
    suite = w.test_suites[0]
    logger.debug("The current TestinProject: %r", suite)
    lm = LifeMonitor.get_instance()
    lm.deregister_test_suite(suite.uuid)
    w = Workflow.find_by_id(workflow['uuid'], workflow['version'])
    assert len(w.test_suites) == current_number_of_suites - 1, \
        "Unexpected number of test_suites for the workflow {}".format(w.uuid)


def test_suite_deregistration_exception(app_context, user, random_valid_uuid):
    with pytest.raises(EntityNotFoundException):
        LifeMonitor.get_instance().deregister_test_suite(random_valid_uuid)


@pytest.mark.parametrize("registry_user", [(RegistryType.SEEK.value, SecurityType.API_KEY.value)], indirect=True)
@pytest.mark.parametrize("registry_workflow", [(RegistryType.SEEK.value, SecurityType.API_KEY.value)], indirect=True)
def test_workflow_deregistration(app_context, registry_user, registry_workflow):
    lm = LifeMonitor.get_instance()
    lm.deregister_workflow(registry_workflow['uuid'], registry_workflow['version'])
    assert len(Workflow.all()) == 0, "Unexpected number of workflows"


def test_workflow_deregistration_exception(app_context, user, random_workflow_id):
    with pytest.raises(EntityNotFoundException):
        LifeMonitor.get_instance().deregister_workflow(random_workflow_id['uuid'],
                                                       random_workflow_id['version'])
