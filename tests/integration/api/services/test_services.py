import os
import pytest
import logging
import pathlib
from tests import utils
from lifemonitor.api.services import LifeMonitor
import lifemonitor.api.models as models
import lifemonitor.exceptions as lm_exceptions

this_dir = os.path.dirname(os.path.abspath(__file__))
tests_root_dir = pathlib.Path(this_dir).parent

logger = logging.getLogger()


def test_valid_workflows(valid_workflow):
    logger.debug(valid_workflow)


def test_workflow_registration(app_client, user1, valid_workflow):
    # pick the test with a valid specification and one test instance
    w, workflow = utils.pick_and_register_workflow(user1, valid_workflow)
    assert workflow is not None, "workflow must be not None"
    assert isinstance(workflow, models.WorkflowVersion), "Object is not an instance of WorkflowVersion"
    assert (workflow.uuid, workflow.version) == (w['uuid'], w['version']),\
        "Unexpected workflow ID"
    # assert workflow.external_id is not None, "External ID must be computed if not provided"
    # assert workflow.external_id == w["external_id"], "Invalid external ID"
    assert workflow.submitter == user1["user"], "Inavalid submitter user"
    # inspect the suite/test type
    assert len(workflow.test_suites) == 1, "Expected number of test suites 1"
    suite = workflow.test_suites[0]
    assert len(suite.test_instances) == 1, "Expected number of test instances 1"
    conf = suite.test_instances[0]
    service = conf.testing_service
    testing_service_type = getattr(models, "{}TestingService".format(w['testing_service_type'].capitalize()))
    assert isinstance(service, testing_service_type), "Unexpected type for service"


def test_preserve_registry_workflow_identity(app_client, user1, user2, valid_workflow):
    workflow = utils.pick_workflow(user1, "sort-and-change-case")
    wv1 = workflow.copy()
    wv2 = workflow.copy()

    wv1['version'] = "1"
    wv2['version'] = "2"
    utils.register_workflow(user1, wv1)
    utils.register_workflow(user2, wv2)

    workflows = models.Workflow.all()
    assert len(workflows) == 1, "Invalid number of workflows"
    w = workflows[0]
    assert len(w.versions) == 2, "Invalid number of workflow versions"


@pytest.mark.parametrize("user1", [True], indirect=True)
def test_get_workflows_scope(user1, user2):

    logger.debug("The first user: %r", user1['user'])
    logger.debug("Number of workflows user1: %r", len(user1['workflows']))

    logger.debug("The second user: %r", user2['user'])
    logger.debug("Number of workflows user1: %r", len(user2['workflows']))

    assert len(user1['workflows']) > len(user2['workflows'])

    registry = models.WorkflowRegistry.all()[0]
    assert registry is not None, "Registry not found"

    lm = LifeMonitor.get_instance()
    user1_workflows = lm.get_user_workflows(user1["user"])
    user2_workflows = lm.get_user_workflows(user2["user"])

    assert len(user2_workflows) == 2, "Unexpected number of workflows"
    assert len(user2_workflows) < len(user1_workflows), "Unexpected number of workflows"


def test_suite_invalid_service_type(app_client, user1):
    with pytest.raises(lm_exceptions.TestingServiceNotSupportedException):
        utils.pick_and_register_workflow(user1, "sort-and-change-case-invalid-service-type")


def test_suite_invalid_service_url(app_client, user1):
    with pytest.raises(lm_exceptions.TestingServiceException):
        w, workflow = utils.pick_and_register_workflow(user1, "sort-and-change-case-invalid-service-url")
        assert len(workflow.test_suites) == 1, "Expected number of test suites 1"
        suite = workflow.test_suites[0]
        assert len(suite.test_instances) == 1, "Expected number of test instances 1"
        conf = suite.test_instances[0]
        conf.testing_service.check_connection()  # this should raise the exception


def test_suite_without_instances(app_client, user1):
    # pick the test with a valid specification and one test instance
    w, workflow = utils.pick_and_register_workflow(user1, "basefreqsum")
    assert workflow is not None, "workflow must be not None"
    assert len(workflow.test_suites) == 1, "Expected number of test suites 1"
    assert len(workflow.test_suites[0].test_instances) == 0, \
        "Unexpected number of test instances"


def test_workflow_registration_not_allowed_user(app_client, user1, user2):

    # not shared workflows
    logger.info("SET 1: %r", user1["workflows"])
    logger.info("SET 2: %r", user2["workflows"])
    # pick one workflow of user1 which is not visible to user2
    workflow = utils.pick_workflow(user1, 'sort-and-change-case-invalid-service-url')
    assert workflow, "Workflow not found"
    assert workflow['name'] not in [_['name'] for _ in user2['workflows']], \
        f"The workflow '{workflow['name']}' should not be visible to user2"
    # user2 should not be allowed to register the workflow
    with pytest.raises(lm_exceptions.NotAuthorizedException):
        w, workflow = utils.register_workflow(user2, workflow)


def test_workflow_serialization(app_client, user1):
    _, workflow = utils.pick_and_register_workflow(user1)
    assert isinstance(workflow, models.WorkflowVersion), "Workflow not properly initialized"
    data = workflow.to_dict(test_suite=True, test_build=True, test_output=True)
    assert isinstance(data, dict), "Invalid serialization output type"
    logger.debug(data)


def test_workflow_serialization_no_instances(app_client, user1):
    _, workflow = utils.pick_and_register_workflow(user1, "basefreqsum")
    assert isinstance(workflow, models.WorkflowVersion), "Workflow not properly initialized"
    data = workflow.to_dict(test_suite=True, test_build=True, test_output=True)
    assert isinstance(data, dict), "Invalid serialization output type"
    logger.debug(data)


def test_workflow_deregistration(app_client, user1, valid_workflow):
    lm = LifeMonitor.get_instance()
    # pick and register one workflow
    wf_data, workflow = utils.pick_and_register_workflow(user1, valid_workflow)
    # current number of workflows
    number_of_workflows = len(models.WorkflowVersion.all())
    lm.deregister_user_workflow(wf_data['uuid'], wf_data['version'], user1["user"])
    assert len(models.WorkflowVersion.all()) == number_of_workflows - 1, "Unexpected number of workflows"
    # try to find
    w = models.WorkflowVersion.get_user_workflow(user1["user"], wf_data['uuid'], wf_data['version'])
    assert w is None, "Workflow must not be in the DB"


def test_workflow_deregistration_exception(app_client, user1, random_workflow_id):
    with pytest.raises(lm_exceptions.EntityNotFoundException):
        LifeMonitor.get_instance().deregister_user_workflow(random_workflow_id['uuid'],
                                                            random_workflow_id['version'],
                                                            user1['user'])


def test_suite_registration(app_client, user1, test_suite_metadata, valid_workflow):
    # register a new workflow
    lm = LifeMonitor.get_instance()
    wf_data, workflow = utils.pick_and_register_workflow(user1, valid_workflow)
    # try to add a new test suite instance
    logger.debug("TestDefinition: %r", test_suite_metadata)
    current_number_of_suites = len(workflow.test_suites)
    suite = lm.register_test_suite(workflow.uuid, workflow.version,
                                   user1['user'], test_suite_metadata)
    logger.debug("Number of suites: %r", len(suite.workflow.test_suites))
    assert len(suite.workflow.test_suites) == current_number_of_suites + 1, \
        "Unexpected number of test_suites for the workflow {}".format(suite.workflow.uuid)
    logger.debug("Project: %r", suite)
    assert len(suite.tests) == 1, "Unexpected number of tests for the testing project {}".format(suite)
    for t in suite.tests:
        logger.debug("- test: %r", t)
    assert len(suite.test_instances) == 1, "Unexpected number of test_instances " \
        "for the testing project {}".format(suite)
    for t in suite.test_instances:
        logger.debug("- test instance: %r --> Service: %r,%s", t, t.testing_service, t.testing_service.url)


def test_suite_registration_workflow_not_found_exception(
        app_client, user1, random_workflow_id, test_suite_metadata):
    with pytest.raises(lm_exceptions.EntityNotFoundException):
        LifeMonitor.get_instance().register_test_suite(random_workflow_id['uuid'],
                                                       random_workflow_id['version'],
                                                       user1['user'],
                                                       test_suite_metadata)


def test_suite_registration_unauthorized_user_exception(
        app_client, user1, random_workflow_id, test_suite_metadata):
    with pytest.raises(lm_exceptions.EntityNotFoundException):
        LifeMonitor.get_instance().register_test_suite(random_workflow_id['uuid'],
                                                       random_workflow_id['version'],
                                                       user1['user'],
                                                       test_suite_metadata)


def test_suite_registration_invalid_specification_exception(
        app_client, user1, invalid_test_suite_metadata):
    w, workflow = utils.pick_and_register_workflow(user1)
    assert isinstance(workflow, models.WorkflowVersion), "Workflow not properly initialized"
    with pytest.raises(lm_exceptions.SpecificationNotValidException):
        LifeMonitor.get_instance().register_test_suite(w['uuid'], w['version'],
                                                       user1["user"],
                                                       invalid_test_suite_metadata)


def test_suite_deregistration(app_client, user1, valid_workflow):
    # register a new workflow
    lm = LifeMonitor.get_instance()
    wf_data, workflow = utils.pick_and_register_workflow(user1, valid_workflow)

    # pick the first suite
    current_number_of_suites = len(workflow.test_suites)
    assert current_number_of_suites > 0, "Unexpected number or suites"
    suite = workflow.test_suites[0]
    logger.debug("The test suite to delete: %r", suite)
    # delete test suite
    lm.deregister_test_suite(suite.uuid)
    assert len(workflow.test_suites) == current_number_of_suites - 1, \
        "Unexpected number of test_suites for the workflow {}".format(workflow.uuid)


def test_suite_deregistration_exception(app_client, user1, random_valid_uuid):
    with pytest.raises(lm_exceptions.EntityNotFoundException):
        LifeMonitor.get_instance().deregister_test_suite(random_valid_uuid)


def test_workflow_latest_version(app_client, user1, random_valid_uuid):
    workflow = utils.pick_workflow(user1, "sort-and-change-case")
    wv1 = workflow.copy()
    wv2 = workflow.copy()

    wv1['version'] = "1"
    wv2['version'] = "2"
    utils.register_workflow(user1, wv1)
    utils.register_workflow(user1, wv2)

    u = user1['user']
    logger.debug("The User: %r", u)
    workflows = LifeMonitor.get_instance().get_user_workflows(u)
    w = LifeMonitor.get_instance().get_user_workflow(u, workflow['uuid'])
    logger.debug(w)
    logger.debug(workflows)
    logger.debug("Previous versions: %r", w.previous_versions)
    assert w.version == "2", "Unexpected version number"
    assert "1" in w.previous_versions, "Version '1' not found as previous version"
