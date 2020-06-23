from __future__ import annotations
import os
import json
import logging
import tempfile
import connexion
from lifemonitor import config
from lifemonitor.common import EntityNotFoundException
from lifemonitor.model import (
    config_db_access,
    WorkflowRegistry, Workflow, TestSuite,
    TestConfiguration, TestingService,
)
from lifemonitor.utils import extract_zip, load_ro_crate_metadata

logger = logging.getLogger()


class LifeMonitor(connexion.App):
    __instance = None

    @classmethod
    def get_instance(cls) -> LifeMonitor:
        if not cls.__instance:
            logger.debug("Creating application instance")
            base_dir = os.path.abspath(os.path.dirname(__file__))
            cls.__instance = cls('LM', specification_dir=base_dir)
        return cls.__instance

    def __init__(self, import_name, server='flask', **kwargs):
        if self.__instance:
            raise LifeMonitor("LifeMonitor instance already exists!")
        # Initializing app
        super().__init__(import_name, server, **kwargs)
        with self.app.app_context():
            config.configure_logging(self.app)
            logger.debug("Initializing DB...")
            config_db_access(self.app)
        logger.debug("Starting application")
        self.__instance = self

    @classmethod
    def register_workflow(cls, workflow_uuid, workflow_version, roc_link, name=None):
        # archive_path = tempfile.NamedTemporaryFile(dir="/tmp", suffix=".zip")
        with tempfile.NamedTemporaryFile(dir="/tmp") as archive_path:
            logger.info("Downloading RO Crate @ %s", archive_path.name)
            wr = WorkflowRegistry.get_instance()
            wr.download_url(roc_link, target_path=archive_path.name)
            with tempfile.TemporaryDirectory() as roc_path:
                logger.info("Extracting RO Crate @ %s", roc_path)
                extract_zip(archive_path.name, target_path=roc_path)
                metadata = load_ro_crate_metadata(roc_path)
                logger.info(metadata)
                w = Workflow(workflow_uuid, workflow_version, roc_metadata=metadata, name=name)
                w.save()

                # TODO: check RO Crate to find TestProject Definitions
                #       and associate them to the workflow
                # i.e., for every tp in test_projects_files:
                #           json_data = load the tdf
                #           register_test_project(w, json_data)
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
    def register_test_suite(cls, workflow_uuid, workflow_version, test_suite_metadata) -> TestSuite:
        workflow = Workflow.find_by_id(workflow_uuid, workflow_version)
        if not workflow:
            raise EntityNotFoundException(Workflow, (workflow_uuid, workflow_version))
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
        suite.save()
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

    @classmethod
    def get_workflow_health_status(cls, workflow_uuid, workflow_version, test_outputs=False):
        workflow = Workflow.find_by_id(workflow_uuid, workflow_version)
        if not workflow:
            raise EntityNotFoundException(Workflow, (workflow_uuid, workflow_version))
        return workflow.to_dict(test_suite=True, test_output=True)
