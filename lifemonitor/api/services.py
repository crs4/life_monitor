from __future__ import annotations
import logging
import tempfile
from lifemonitor.auth.models import User
from lifemonitor.common import EntityNotFoundException, NotAuthorizedException
from lifemonitor.api.models import (
    WorkflowRegistry, Workflow, TestSuite, TestInstance
)
from lifemonitor.utils import extract_zip, load_ro_crate_metadata, search_for_test_definition
from lifemonitor.auth.oauth2.client.models import OAuthIdentity

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
    def register_workflow(cls, workflow_registry: WorkflowRegistry, workflow_submitter: User,
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
                w = workflow_registry.add_workflow(
                    workflow_uuid, workflow_version, workflow_submitter,
                    roc_link=roc_link, roc_metadata=metadata,
                    external_id=external_id, name=name
                )
                # load test_definition_file and if it exists associate a test_suite the workflow
                test_definition_file = search_for_test_definition(roc_path, metadata)
                logger.debug("The test definition file: %r", test_definition_file)
                if test_definition_file:
                    logger.debug("Loaded test definition file: %r", test_definition_file)
                    w.add_test_suite(workflow_submitter, test_definition_file)
                w.save()
                return w

    @classmethod
    def deregister_workflow(cls, workflow_uuid, workflow_version, user: User):
        workflow = cls._find_and_check_workflow(workflow_uuid, workflow_version, user)
        logger.debug("Workflow to delete: %r", workflow)
        if not workflow:
            raise EntityNotFoundException(Workflow, (workflow_uuid, workflow_version))
        if workflow.submitter != user:
            raise NotAuthorizedException("Only the workflow submitter can add test suites")
        workflow.delete()
        logger.debug("Deleted workflow wf_uuid: %r - version: %r", workflow_uuid, workflow_version)
        return workflow_uuid, workflow_version

    @classmethod
    def register_test_suite(cls, workflow_uuid, workflow_version,
                            submitter: User, test_suite_metadata) -> TestSuite:
        workflow = Workflow.find_by_id(workflow_uuid, workflow_version)
        if not workflow:
            raise EntityNotFoundException(Workflow, (workflow_uuid, workflow_version))
        # For now only the workflow submitter can add test suites
        if workflow.submitter != submitter:
            raise NotAuthorizedException("Only the workflow submitter can add test suites")
        suite = workflow.add_test_suite(submitter, test_suite_metadata)
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
    def get_workflow_registry_by_uri(cls, registry_uri) -> WorkflowRegistry:
        try:
            r = WorkflowRegistry.find_by_uri(registry_uri)
            if not r:
                raise EntityNotFoundException(WorkflowRegistry, registry_uri)
            return r
        except Exception:
            raise EntityNotFoundException(WorkflowRegistry, registry_uri)

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

    @classmethod
    def get_suite(cls, suite_uuid) -> TestSuite:
        return TestSuite.find_by_id(suite_uuid)

    @classmethod
    def get_test_instance(cls, instance_uuid) -> TestInstance:
        return TestInstance.find_by_id(instance_uuid)

    @classmethod
    def find_registry_user_identity(cls, registry: WorkflowRegistry,
                                    internal_id=None, external_id=None) -> OAuthIdentity:
        if not internal_id and not external_id:
            raise ValueError("external_id and internal_id cannot be both None")
        if internal_id:
            return OAuthIdentity.find_by_user_id(internal_id, registry.name)
        return OAuthIdentity.find_by_provider_user_id(external_id, registry.name)
