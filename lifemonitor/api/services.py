from __future__ import annotations
import json
import logging
import tempfile
from typing import Union, List
from lifemonitor.auth.models import User
from lifemonitor.auth.oauth2.server import server
from lifemonitor.auth.oauth2.client import providers
from lifemonitor.common import (
    EntityNotFoundException, NotAuthorizedException,
    WorkflowRegistryNotSupportedException
)
from lifemonitor.api.models import (
    WorkflowRegistry, Workflow, TestSuite, TestInstance
)
from lifemonitor.utils import extract_zip
from lifemonitor.auth.oauth2.client.models import OAuthIdentity
import lifemonitor.ro_crate as roc

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

    @staticmethod
    def _find_and_check_workflow(uuid, version, user: User):
        if not version:
            w = Workflow.find_latest_by_id(uuid)
        else:
            w = Workflow.find_by_id(uuid, version)
        if w is None:
            raise EntityNotFoundException(Workflow, f"{uuid}_{version}")
        allowed = w.workflow_registry.get_user_workflows(user)
        if w not in allowed:
            raise NotAuthorizedException(f"User {user.username} is not allowed to access workflow")
        return w

    @staticmethod
    def register_workflow(workflow_registry: WorkflowRegistry, workflow_submitter: User,
                          workflow_uuid, workflow_version, roc_link, external_id=None, name=None):
        with tempfile.NamedTemporaryFile(dir="/tmp") as archive_path:
            logger.info("Downloading RO Crate @ %s", archive_path.name)
            zip_archive = workflow_registry.download_url(roc_link, workflow_submitter, target_path=archive_path.name)
            logger.debug("ZIP Archive: %s", zip_archive)
            with tempfile.TemporaryDirectory() as roc_path:
                logger.info("Extracting RO Crate @ %s", roc_path)
                extract_zip(archive_path.name, target_path=roc_path)
                metadata = roc.load_metadata(roc_path)
                # create a new Workflow instance with the loaded metadata
                w = workflow_registry.add_workflow(
                    workflow_uuid, workflow_version, workflow_submitter,
                    roc_link=roc_link, roc_metadata=metadata,
                    external_id=external_id, name=name
                )
                # associate a test suite to the workflow if the crate contains test metadata
                _, test_metadata_path = roc.parse_metadata(roc_path)
                if test_metadata_path:
                    logger.debug("Loading test metadata from %r", test_metadata_path)
                    with open(test_metadata_path) as f:
                        test_metadata = json.load(f)
                    w.add_test_suite(workflow_submitter, test_metadata)
                w.save()
                return w

    @classmethod
    def deregister_user_workflow(cls, workflow_uuid, workflow_version, user: User):
        workflow = cls._find_and_check_workflow(workflow_uuid, workflow_version, user)
        logger.debug("Workflow to delete: %r", workflow)
        if not workflow:
            raise EntityNotFoundException(Workflow, (workflow_uuid, workflow_version))
        if workflow.submitter != user:
            raise NotAuthorizedException("Only the workflow submitter can add test suites")
        workflow.delete()
        logger.debug("Deleted workflow wf_uuid: %r - version: %r", workflow_uuid, workflow_version)
        return workflow_uuid, workflow_version

    @staticmethod
    def deregister_registry_workflow(workflow_uuid, workflow_version, registry: WorkflowRegistry):
        workflow = registry.get_workflow(workflow_uuid, workflow_version)
        logger.debug("Workflow to delete: %r", workflow)
        if not workflow:
            raise EntityNotFoundException(Workflow, (workflow_uuid, workflow_version))
        workflow.delete()
        logger.debug("Deleted workflow wf_uuid: %r - version: %r", workflow_uuid, workflow_version)
        return workflow_uuid, workflow_version

    @staticmethod
    def register_test_suite(workflow_uuid, workflow_version,
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

    @staticmethod
    def deregister_test_suite(test_suite: Union[TestSuite, str]) -> str:
        suite = test_suite
        if not isinstance(test_suite, TestSuite):
            suite = TestSuite.find_by_id(test_suite)
            if not suite:
                raise EntityNotFoundException(TestSuite, test_suite)
        suite.delete()
        logger.debug("Deleted TestSuite: %r", suite.uuid)
        return suite.uuid

    @staticmethod
    def get_workflow_registry_by_uuid(registry_uuid) -> WorkflowRegistry:
        try:
            r = WorkflowRegistry.find_by_id(registry_uuid)
            if not r:
                raise EntityNotFoundException(WorkflowRegistry, registry_uuid)
            return r
        except Exception:
            raise EntityNotFoundException(WorkflowRegistry, registry_uuid)

    @staticmethod
    def get_workflow_registry_by_uri(registry_uri) -> WorkflowRegistry:
        try:
            r = WorkflowRegistry.find_by_uri(registry_uri)
            if not r:
                raise EntityNotFoundException(WorkflowRegistry, registry_uri)
            return r
        except Exception:
            raise EntityNotFoundException(WorkflowRegistry, registry_uri)

    @staticmethod
    def get_workflow_registry_by_name(registry_name) -> WorkflowRegistry:
        try:
            r = WorkflowRegistry.find_by_name(registry_name)
            if not r:
                raise EntityNotFoundException(WorkflowRegistry, registry_name)
            return r
        except Exception:
            raise EntityNotFoundException(WorkflowRegistry, registry_name)

    @staticmethod
    def get_workflow(uuid, version) -> Workflow:
        return Workflow.find_by_id(uuid, version)

    @staticmethod
    def get_workflows() -> list:
        return Workflow.all()

    @staticmethod
    def get_registry_workflow(registry: WorkflowRegistry, uuid, version=None) -> Workflow:
        return registry.get_workflow(uuid, version)

    @staticmethod
    def get_registry_workflows(registry: WorkflowRegistry) -> list:
        return registry.registered_workflows

    @classmethod
    def get_user_workflow(cls, user: User, uuid, version=None) -> Workflow:
        return cls._find_and_check_workflow(uuid, version, user)

    @staticmethod
    def get_user_workflows(user: User) -> list:
        workflows = []
        registries = WorkflowRegistry.all()
        for registry in registries:
            workflows.extend(registry.get_user_workflows(user))
        return workflows

    @staticmethod
    def get_suite(suite_uuid) -> TestSuite:
        return TestSuite.find_by_id(suite_uuid)

    @staticmethod
    def get_test_instance(instance_uuid) -> TestInstance:
        return TestInstance.find_by_id(instance_uuid)

    @staticmethod
    def find_registry_user_identity(registry: WorkflowRegistry,
                                    internal_id=None, external_id=None) -> OAuthIdentity:
        if not internal_id and not external_id:
            raise ValueError("external_id and internal_id cannot be both None")
        if internal_id:
            return OAuthIdentity.find_by_user_id(internal_id, registry.name)
        return OAuthIdentity.find_by_provider_user_id(external_id, registry.name)

    @staticmethod
    def add_workflow_registry(type, name,
                              client_id, client_secret, client_auth_method="client_secret_post",
                              api_base_url=None, redirect_uris=None) -> WorkflowRegistry:
        try:
            # At the moment client_credentials of registries
            # are associated with the admin account
            user = User.find_by_username("admin")
            if not user:
                raise EntityNotFoundException(User, entity_id="admin")
            server_credentials = providers.new_instance(provider_type=type,
                                                        name=name,
                                                        client_id=client_id,
                                                        client_secret=client_secret,
                                                        api_base_url=api_base_url)
            client_credentials = \
                server.create_client(user, name, server_credentials.api_base_url,
                                     ['client_credentials', 'authorization_code', 'refresh_token'],
                                     ["code", "token"],
                                     "read write",
                                     redirect_uris.split(',')
                                     if isinstance(redirect_uris, str)
                                     else redirect_uris,
                                     client_auth_method, commit=False)
            registry = WorkflowRegistry.new_instance(type, client_credentials, server_credentials)
            registry.save()
            logger.debug(f"WorkflowRegistry '{name}' (type: {type})' created: {registry}")
            return registry
        except providers.OAuth2ProviderNotSupportedException as e:
            raise WorkflowRegistryNotSupportedException(exception=e)

    @staticmethod
    def update_workflow_registry(uuid, name=None,
                                 client_id=None, client_secret=None, client_auth_method=None,
                                 api_base_url=None, redirect_uris=None) -> WorkflowRegistry:
        try:
            registry = WorkflowRegistry.find_by_id(uuid)
            if not registry:
                raise EntityNotFoundException(WorkflowRegistry, entity_id=uuid)
            if name:
                registry.server_credentials.name = name
            if api_base_url:
                registry.uri = api_base_url
                registry.server_credentials.api_base_url = api_base_url
                registry.client_credentials.api_base_url = api_base_url
            if client_id:
                registry.server_credentials.client_id = client_id
            if client_secret:
                registry.server_credentials.client_secret = client_secret
            if redirect_uris:
                registry.client_credentials.redirect_uris = redirect_uris
            if client_auth_method:
                registry.client_credentials.auth_method = client_auth_method
            registry.save()
            logger.info(f"WorkflowRegistry '{uuid}' (name: {name})' updated!")
            return registry
        except providers.OAuth2ProviderNotSupportedException as e:
            raise WorkflowRegistryNotSupportedException(exception=e)

    @staticmethod
    def get_workflow_registries() -> WorkflowRegistry:
        return WorkflowRegistry.all()

    @staticmethod
    def get_workflow_registry(uuid) -> WorkflowRegistry:
        return WorkflowRegistry.find_by_id(uuid)

    @staticmethod
    def get_workflow_registry_users(registry: WorkflowRegistry) -> List[User]:
        return registry.get_users()
