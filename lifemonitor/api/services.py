from __future__ import annotations
import logging
import tempfile
from lifemonitor.auth.models import User
from lifemonitor.common import EntityNotFoundException, NotAuthorizedException
from lifemonitor.api.models import (
    WorkflowRegistry, Workflow, TestSuite,
    TestConfiguration, TestingService,
)
from lifemonitor.utils import extract_zip, load_ro_crate_metadata, search_for_test_definition


logger = logging.getLogger()


class LifeMonitor:
    __instance = None

    @classmethod
    def get_instance(cls) -> LifeMonitor:
        if not cls.__instance:
            cls.__instance = cls()
        return cls.__instance

    def __init__(self):
        if self.__instance:
            raise RuntimeError("LifeMonitor instance already exists!")
        self.__instance = self

    @classmethod
    def _find_and_check_workflow(cls, uuid, version, user: User):
        w = Workflow.find_by_id(uuid, version)
        if w is None:
            raise EntityNotFoundException(Workflow, f"{uuid}_{version}")
        allowed = w.workflow_registry.get_user_workflows(user)
        if w not in allowed:
            raise NotAuthorizedException(f"User {user.username} is not allowed to access workflow")
        return w

    @classmethod
    def register_workflow(cls, workflow_registry, workflow_submitter,
                          workflow_uuid, workflow_version, roc_link, external_id=None, name=None):
        with tempfile.NamedTemporaryFile(dir="/tmp") as archive_path:
            logger.info("Downloading RO Crate @ %s", archive_path.name)
            zip_archive = workflow_registry.download_url(roc_link, workflow_submitter, target_path=archive_path.name)
            logger.debug("ZIP Archive: %s", zip_archive)
            with tempfile.TemporaryDirectory() as roc_path:
                logger.info("Extracting RO Crate @ %s", roc_path)
                extract_zip(archive_path.name, target_path=roc_path)
                metadata = load_ro_crate_metadata(roc_path)
                # create a new Workflow instance with the loaded metadata
                w = Workflow(workflow_registry, workflow_uuid, workflow_version, roc_link,
                             roc_metadata=metadata, external_id=external_id, name=name)
                # load test_definition_file and if it exists associate a test_suite the workflow
                test_definition_file = search_for_test_definition(roc_path, metadata)
                logger.debug("The test definition file: %r", test_definition_file)
                if test_definition_file:
                    logger.debug("Loaded test definition file: %r", test_definition_file)
                    cls.add_test_suite(w, test_definition_file)
                w.save()
                return w

    @classmethod
    def deregister_workflow(cls, workflow_uuid, workflow_version):
        workflow = Workflow.find_by_id(workflow_uuid, workflow_version)
        if not workflow:
            raise EntityNotFoundException(Workflow, (workflow_uuid, workflow_version))
        workflow.delete()
        logger.debug("Deleted workflow wf_uuid: %r - version: %r", workflow_uuid, workflow_version)
        return workflow_uuid, workflow_version

    @classmethod
    def deregister_user_workflow(cls, workflow_uuid, workflow_version, user: User):
        workflow = cls._find_and_check_workflow(workflow_uuid, workflow_version, user)
        logger.debug("Workflow to delete: %r", workflow)
        if not workflow:
            raise EntityNotFoundException(Workflow, (workflow_uuid, workflow_version))
        workflow.delete()
        logger.debug("Deleted workflow wf_uuid: %r - version: %r", workflow_uuid, workflow_version)
        return workflow_uuid, workflow_version

    @classmethod
    def register_test_suite(cls, workflow_uuid, workflow_version, test_suite_metadata) -> TestSuite:
        workflow = Workflow.find_by_id(workflow_uuid, workflow_version)
        if not workflow:
            raise EntityNotFoundException(Workflow, (workflow_uuid, workflow_version))
        suite = cls.add_test_suite(workflow, test_suite_metadata)
        suite.save()
        return suite

    @classmethod
    def add_test_suite(cls, workflow, test_suite_metadata) -> TestSuite:
        suite = TestSuite(workflow, test_suite_metadata)
        for test in test_suite_metadata["test"]:
            for instance_data in test["instance"]:
                logger.debug("Instance_data: %r", instance_data)
                test_configuration = TestConfiguration(suite, test["name"],
                                                       instance_data["name"], instance_data["url"])
                testing_service_data = instance_data["service"]
                testing_service = TestingService.new_instance(test_configuration,
                                                              testing_service_data["type"],
                                                              testing_service_data["url"])
                logger.debug("Created TestService: %r", testing_service)
        return suite

    @classmethod
    def deregister_test_suite(cls, test_suite_uuid) -> str:
        project = TestSuite.find_by_id(test_suite_uuid)
        if not project:
            raise EntityNotFoundException(TestSuite, test_suite_uuid)
        project.delete()
        logger.debug("Deleted TestSuite: %r", project.uuid)
        return test_suite_uuid

    @classmethod
    def get_workflow(cls, uuid, version) -> Workflow:
        return Workflow.find_by_id(uuid, version)

    @classmethod
    def get_workflows(cls) -> list:
        return Workflow.all()

    @classmethod
    def get_registry_workflow(cls, uuid, version, registry: WorkflowRegistry) -> Workflow:
        return registry.get_workflow(uuid, version)

    @classmethod
    def get_registry_workflows(cls, registry: WorkflowRegistry) -> list:
        return registry.registered_workflows

    @classmethod
    def get_user_workflow(cls, uuid, version, user: User) -> Workflow:
        return cls._find_and_check_workflow(uuid, version, user)

    @classmethod
    def get_user_workflows(cls, user: User) -> list:
        workflows = []
        registries = WorkflowRegistry.all()
        for registry in registries:
            workflows.extend(registry.get_user_workflows(user))
        return workflows
