from __future__ import annotations

import logging
from typing import Union, List

import lifemonitor.exceptions as lm_exceptions
from lifemonitor.api import models
from lifemonitor.auth.models import ExternalServiceAuthorizationHeader, User, Permission, RoleType
from lifemonitor.auth.oauth2.client import providers
from lifemonitor.auth.oauth2.client.models import OAuthIdentity
from lifemonitor.auth.oauth2.server import server

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
            w = models.Workflow.get_user_workflow(user, uuid).latest_version
        else:
            w = models.WorkflowVersion.get_user_workflow(user, uuid, version)
        if w is None:
            raise lm_exceptions.EntityNotFoundException(models.WorkflowVersion, f"{uuid}_{version}")
        # Check whether the user can access the workflow.
        # As a general rule, we grant user access to the workflow
        #   1. if the user belongs to the owners group
        #   2. or the user belongs to the viewers group
        # if user not in w.owners and user not in w.viewers:
        if not user.has_permission(w):
            # if the user is not the submitter
            # and the workflow is associated with a registry
            # then we try to check whether the user is allowed to view the workflow
            if w.workflow_registry is None or w not in w.workflow_registry.get_user_workflows(user):
                raise lm_exceptions.NotAuthorizedException(f"User {user.username} is not allowed to access workflow")
        return w

    @staticmethod
    def register_workflow(workflow_submitter: User,
                          workflow_uuid, workflow_version, roc_link,
                          workflow_registry: models.WorkflowRegistry = None,
                          authorization=None, name=None):

        # find or create a user workflow
        if workflow_registry:
            w = workflow_registry.get_workflow(workflow_uuid)
        else:
            w = models.Workflow.get_user_workflow(workflow_submitter, workflow_uuid)
        if not w:
            w = models.Workflow(uuid=workflow_uuid, name=name)
            w.permissions.append(Permission(user=workflow_submitter, roles=[RoleType.owner]))
            if workflow_registry:
                for auth in workflow_submitter.get_authorization(workflow_registry):
                    auth.resources.append(w)
            else:
                raise("Unsupported yet")

        wv = w.add_version(workflow_version, roc_link, workflow_submitter,
                           uuid=workflow_uuid, name=name,
                           hosting_service=workflow_registry)
        wv.permissions.append(Permission(user=workflow_submitter, roles=[RoleType.owner]))
        if authorization:
            wv.authorizations.append(ExternalServiceAuthorizationHeader(workflow_submitter, header=authorization))
        if wv.test_metadata:
            logger.debug("Test metadata found in the crate")
            # FIXME: the test metadata can describe more than one suite
            wv.add_test_suite(workflow_submitter, wv.test_metadata)
        w.save()
        return wv

    @classmethod
    def deregister_user_workflow(cls, workflow_uuid, workflow_version, user: User):
        workflow = cls._find_and_check_workflow(workflow_uuid, workflow_version, user)
        logger.debug("WorkflowVersion to delete: %r", workflow)
        if not workflow:
            raise lm_exceptions.EntityNotFoundException(models.WorkflowVersion, (workflow_uuid, workflow_version))
        if workflow.submitter != user:
            raise lm_exceptions.NotAuthorizedException("Only the workflow submitter can add test suites")
        workflow.delete()
        logger.debug("Deleted workflow wf_uuid: %r - version: %r", workflow_uuid, workflow_version)
        return workflow_uuid, workflow_version

    @staticmethod
    def deregister_registry_workflow(workflow_uuid, workflow_version, registry: models.WorkflowRegistry):
        workflow = registry.get_workflow(workflow_uuid).versions[workflow_version]
        logger.debug("WorkflowVersion to delete: %r", workflow)
        if not workflow:
            raise lm_exceptions.EntityNotFoundException(models.WorkflowVersion, (workflow_uuid, workflow_version))
        workflow.delete()
        logger.debug("Deleted workflow wf_uuid: %r - version: %r", workflow_uuid, workflow_version)
        return workflow_uuid, workflow_version

    @staticmethod
    def register_test_suite(workflow_uuid, workflow_version,
                            submitter: models.User, test_suite_metadata) -> models.TestSuite:
        workflow = models.WorkflowVersion.get_user_workflow(submitter, workflow_uuid, workflow_version)
        if not workflow:
            raise lm_exceptions.EntityNotFoundException(models.WorkflowVersion, (workflow_uuid, workflow_version))
        # For now only the workflow submitter can add test suites
        if workflow.submitter != submitter:
            raise lm_exceptions.NotAuthorizedException("Only the workflow submitter can add test suites")
        suite = workflow.add_test_suite(submitter, test_suite_metadata)
        suite.save()
        return suite

    @staticmethod
    def deregister_test_suite(test_suite: Union[models.TestSuite, str]) -> str:
        suite = test_suite
        if not isinstance(test_suite, models.TestSuite):
            suite = models.TestSuite.find_by_id(test_suite)
            if not suite:
                raise lm_exceptions.EntityNotFoundException(models.TestSuite, test_suite)
        suite.delete()
        logger.debug("Deleted TestSuite: %r", suite.uuid)
        return suite.uuid

    @staticmethod
    def get_workflow_registry_by_uuid(registry_uuid) -> models.WorkflowRegistry:
        try:
            r = models.WorkflowRegistry.find_by_id(registry_uuid)
            if not r:
                raise lm_exceptions.EntityNotFoundException(models.WorkflowRegistry, registry_uuid)
            return r
        except Exception:
            raise lm_exceptions.EntityNotFoundException(models.WorkflowRegistry, registry_uuid)

    @staticmethod
    def get_workflow_registry_by_uri(registry_uri) -> models.WorkflowRegistry:
        try:
            r = models.WorkflowRegistry.find_by_uri(registry_uri)
            if not r:
                raise lm_exceptions.EntityNotFoundException(models.WorkflowRegistry, registry_uri)
            return r
        except Exception:
            raise lm_exceptions.EntityNotFoundException(models.WorkflowRegistry, registry_uri)

    @staticmethod
    def get_workflow_registry_by_name(registry_name) -> models.WorkflowRegistry:
        try:
            r = models.WorkflowRegistry.find_by_name(registry_name)
            if not r:
                raise lm_exceptions.EntityNotFoundException(models.WorkflowRegistry, registry_name)
            return r
        except Exception:
            raise lm_exceptions.EntityNotFoundException(models.WorkflowRegistry, registry_name)

    @staticmethod
    def get_workflows() -> list:
        return models.WorkflowVersion.all()

    @staticmethod
    def get_registry_workflow(registry: models.WorkflowRegistry, uuid, version=None) -> models.WorkflowVersion:
        w = registry.get_workflow(uuid)
        return w.latest_version if version is None else w.versions[version]

    @staticmethod
    def get_registry_workflows(registry: models.WorkflowRegistry) -> List[models.WorkflowVersion]:
        return registry.registered_workflows

    @classmethod
    def get_user_workflow(cls, user: models.User, uuid, version=None) -> models.WorkflowVersion:
        return cls._find_and_check_workflow(uuid, version, user)

    @staticmethod
    def get_workflow_registry_users(registry: models.WorkflowRegistry) -> List[User]:
        return registry.get_users()

    @staticmethod
    def get_user_workflows(user: User) -> list:
        workflows = [w for w in models.WorkflowVersion.get_user_workflows(user)]
        # TODO: replace WorkflowRegistry with a more general Entity
        for svc in models.WorkflowRegistry.all():
            try:
                if svc.get_user(user.id):
                    workflows.extend(svc.get_user_workflows(user))
            except lm_exceptions.lm_exceptions.EntityNotFoundException:
                pass
        return workflows

    @staticmethod
    def get_suite(suite_uuid) -> models.TestSuite:
        return models.TestSuite.find_by_id(suite_uuid)

    @staticmethod
    def get_test_instance(instance_uuid) -> models.TestInstance:
        return models.TestInstance.find_by_id(instance_uuid)

    @staticmethod
    def find_registry_user_identity(registry: models.WorkflowRegistry,
                                    internal_id=None, external_id=None) -> OAuthIdentity:
        if not internal_id and not external_id:
            raise ValueError("external_id and internal_id cannot be both None")
        if internal_id:
            return OAuthIdentity.find_by_user_id(internal_id, registry.name)
        return OAuthIdentity.find_by_provider_user_id(external_id, registry.name)

    @staticmethod
    def add_workflow_registry(type, name,
                              client_id, client_secret, client_auth_method="client_secret_post",
                              api_base_url=None, redirect_uris=None) -> models.WorkflowRegistry:
        try:
            # At the moment client_credentials of registries
            # are associated with the admin account
            user = User.find_by_username("admin")
            if not user:
                raise lm_exceptions.EntityNotFoundException(User, entity_id="admin")
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
            registry = models.WorkflowRegistry.new_instance(type, client_credentials, server_credentials)
            registry.save()
            logger.debug(f"WorkflowRegistry '{name}' (type: {type})' created: {registry}")
            return registry
        except providers.OAuth2ProviderNotSupportedException as e:
            raise lm_exceptions.WorkflowRegistryNotSupportedException(exception=e)

    @staticmethod
    def update_workflow_registry(uuid, name=None,
                                 client_id=None, client_secret=None, client_auth_method=None,
                                 api_base_url=None, redirect_uris=None) -> models.WorkflowRegistry:
        try:
            registry = models.WorkflowRegistry.find_by_id(uuid)
            if not registry:
                raise lm_exceptions.EntityNotFoundException(models.WorkflowRegistry, entity_id=uuid)
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
            raise lm_exceptions.WorkflowRegistryNotSupportedException(exception=e)

    @staticmethod
    def get_workflow_registries() -> models.WorkflowRegistry:
        return models.WorkflowRegistry.all()

    @staticmethod
    def get_workflow_registry(uuid) -> models.WorkflowRegistry:
        return models.WorkflowRegistry.find_by_id(uuid)
