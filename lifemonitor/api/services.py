from __future__ import annotations
import logging
import tempfile
from lifemonitor.common import EntityNotFoundException
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
    def register_workflow(cls, workflow_uuid, workflow_version, roc_link, name=None):
        try:
            with tempfile.NamedTemporaryFile(dir="/tmp") as archive_path:
                logger.info("Downloading RO Crate @ %s", archive_path.name)
                wr = WorkflowRegistry.get_instance()
                zip_archive = wr.download_url(roc_link, target_path=archive_path.name)
                logger.debug("ZIP Archive: %s", zip_archive)
                with tempfile.TemporaryDirectory() as roc_path:
                    roc_path = tempfile.TemporaryDirectory()
                    logger.info("Extracting RO Crate @ %s", roc_path)
                    extract_zip(archive_path.name, target_path=roc_path.name)
                    metadata = load_ro_crate_metadata(roc_path.name)

                    w = Workflow(workflow_uuid, workflow_version, roc_metadata=metadata, name=name)

                    # TODO: check RO Crate to find TestProject Definitions
                    #       and associate them to the workflow
                    test_definition_file = search_for_test_definition(roc_path.name, metadata)
                    if test_definition_file:
                        logger.debug("Loaded test definition file: %r", test_definition_file)
                        cls.add_test_suite(w, test_definition_file)
                        
                    w.save()
                    return w
        except Exception as e:
            logger.exception(e)

    @classmethod
    def deregister_workflow(cls, workflow_uuid, workflow_version):
        workflow = Workflow.find_by_id(workflow_uuid, workflow_version)
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
    def get_registered_workflow(cls, uuid, version) -> Workflow:
        return Workflow.find_by_id(uuid, version)

    @classmethod
    def get_registered_workflows(cls) -> list:
        return Workflow.all()
