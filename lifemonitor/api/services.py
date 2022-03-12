# Copyright (c) 2020-2021 CRS4
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

from __future__ import annotations

import logging
from datetime import datetime
from typing import List, Optional, Union

import lifemonitor.exceptions as lm_exceptions
from lifemonitor.api import models
from lifemonitor.auth.models import (EventType,
                                     ExternalServiceAuthorizationHeader,
                                     HostingService, Notification, Permission,
                                     Resource, RoleType, Subscription, User)
from lifemonitor.auth.oauth2.client import providers
from lifemonitor.auth.oauth2.client.models import OAuthIdentity
from lifemonitor.auth.oauth2.server import server
from lifemonitor.utils import OpenApiSpecs, ROCrateLinkContext

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
    def _find_and_check_shared_workflow_version(user: User, uuid, version=None) -> models.WorkflowVersion:
        for svc in models.WorkflowRegistry.all():
            try:
                if svc.get_user(user.id):
                    for w in svc.get_user_workflows(user):
                        if str(w.uuid) == str(uuid):
                            if not version or version.lower() == "latest":
                                return w.latest_version
                            elif version and version in w.versions:
                                return w.versions[version]
            except lm_exceptions.NotAuthorizedException as e:
                logger.debug(e)
        return None

    @classmethod
    def _find_and_check_workflow_version(cls, user: User, uuid, version=None):
        w = None
        if not user or user.is_anonymous:
            if not version or version.lower() == "latest":
                _w = models.Workflow.get_public_workflow(uuid)
                if _w:
                    w = _w.latest_version
            else:
                w = models.WorkflowVersion.get_public_workflow_version(uuid, version)
        else:
            if not version or version.lower() == "latest":
                _w = models.Workflow.get_user_workflow(user, uuid)
                if _w:
                    w = _w.latest_version
            else:
                w = models.WorkflowVersion.get_user_workflow_version(user, uuid, version)
            if not w:
                w = cls._find_and_check_shared_workflow_version(user, uuid, version=version)

        if w is None:
            raise lm_exceptions.EntityNotFoundException(models.WorkflowVersion, entity_id=f"{uuid}_{version}")
        # Check whether the user can access the workflow.
        # As a general rule, we grant user access to the workflow
        #   1. if the user belongs to the owners group
        #   2. or the user belongs to the viewers group
        # if user not in w.owners and user not in w.viewers:
        if user and not user.is_anonymous and not user.has_permission(w):
            # if the user is not the submitter
            # and the workflow is associated with a registry
            # then we try to check whether the user is allowed to view the workflow
            if w.registry is None or \
                    isinstance(w.registry, models.WorkflowRegistry) and w.workflow not in w.registry.get_user_workflows(user):
                raise lm_exceptions.NotAuthorizedException(f"User {user.username} is not allowed to access workflow")
        return w

    @classmethod
    def register_workflow(cls, rocrate_or_link, workflow_submitter: User, workflow_version,
                          workflow_uuid=None, workflow_identifier=None,
                          workflow_registry: Optional[models.WorkflowRegistry] = None,
                          authorization=None, name=None, public=False):
        # find or create a user workflow
        w = None
        if workflow_registry:
            if workflow_uuid:
                w = workflow_registry.get_workflow(workflow_uuid)
            else:
                w = workflow_registry.get_workflow(workflow_identifier)
        else:
            w = models.Workflow.get_user_workflow(workflow_submitter, workflow_uuid)
        if not w:
            w = models.Workflow(uuid=workflow_uuid, identifier=workflow_identifier, name=name)
            if workflow_submitter:
                w.permissions.append(Permission(user=workflow_submitter, roles=[RoleType.owner]))
                if workflow_registry:
                    for auth in workflow_submitter.get_authorization(workflow_registry):
                        auth.resources.append(w)

        if str(workflow_version) in w.versions:
            raise lm_exceptions.WorkflowVersionConflictException(workflow_uuid, workflow_version)

        with ROCrateLinkContext(rocrate_or_link) as roc_link:
            if not roc_link:
                if not workflow_registry:
                    raise ValueError("Missing ROC link")
                else:
                    roc_link = workflow_registry.get_rocrate_external_link(w.external_id, workflow_version)

            wv = w.add_version(workflow_version, roc_link, workflow_submitter,
                               name=name, registry=workflow_registry)

            if workflow_submitter:
                wv.permissions.append(Permission(user=workflow_submitter, roles=[RoleType.owner]))
                # automatically register submitter's subscription to workflow events
                workflow_submitter.subscribe(w)
            if authorization:
                auth = ExternalServiceAuthorizationHeader(workflow_submitter, header=authorization)
                auth.resources.append(wv)

            if name is None:
                if wv.workflow_name is None:
                    raise lm_exceptions.LifeMonitorException(title="Missing attribute 'name'",
                                                             detail="Attribute 'name' is not defined and it cannot be retrieved \
                                                            from the workflow RO-Crate (name of 'mainEntity' not found)",
                                                             status=400)
                w.name = wv.workflow_name
                wv.name = wv.workflow_name

            # set workflow visibility
            w.public = public

            # set hosting service
            hosting_service = None
            if wv.based_on:
                hosting_service = HostingService.from_url(wv.based_on)
            elif workflow_registry:
                hosting_service = workflow_registry
            if hosting_service:
                wv.hosting_service = hosting_service

            # parse roc_metadata and register suites and instances
            try:
                if wv.roc_suites:
                    for _, raw_suite in wv.roc_suites.items():
                        cls._init_test_suite_from_json(wv, workflow_submitter, raw_suite)
            except KeyError as e:
                raise lm_exceptions.SpecificationNotValidException(f"Missing property: {e}")
            w.save()
            return wv

    @classmethod
    def update_workflow(cls, workflow_submitter: User,
                        workflow_uuid: str, workflow_version: str,
                        name=None, new_version_label: str = None, public=False,
                        rocrate_or_link: str = None,
                        authorization=None) -> models.WorkflowVersion:

        # get reference to the current workflow version
        wv: models.WorkflowVersion = cls.get_user_workflow_version(workflow_submitter, workflow_uuid, workflow_version)
        w: models.Workflow = wv.workflow
        workflow_registry: models.WorkflowRegistry = wv.registry
        # compute the roc_link
        if workflow_registry is not None:
            # if the workflow comes from a hosting service
            # always reuse the original roc_link pointing to the workflow on the service
            rocrate_or_link = workflow_registry.get_rocrate_external_link(w.external_id, workflow_version)
            logger.debug("Reusing original ROC link: %r", rocrate_or_link)
        elif rocrate_or_link is not None:
            # if an rocrate or link is provided, the workflow version will be replaced
            logger.debug("New roc_link or RO-crate detected: %r", rocrate_or_link)

        with ROCrateLinkContext(rocrate_or_link) as roc_link:
            # if roc_link is not None:
            auth = None
            if authorization:
                auth = ExternalServiceAuthorizationHeader(workflow_submitter, header=authorization)
            # check for changes
            rocrate_changes = wv.check_for_changes(roc_link, extra_auth=auth)
            logger.debug(f"Detected changes wrt '{roc_link}': {rocrate_changes}")
            if len(rocrate_changes) > 0:
                # remove old workflow version
                w.remove_version(wv)
                # create a new workflow version to replace the old one
                wv = w.add_version(workflow_version, roc_link, workflow_submitter,
                                   name=name, registry=workflow_registry)
                if workflow_submitter:
                    wv.permissions.append(Permission(user=workflow_submitter, roles=[RoleType.owner]))
                    # automatically register submitter's subscription to workflow events
                    workflow_submitter.subscribe(w)
                if auth:
                    auth.resources.append(wv)
                # set hosting service
                hosting_service = None
                if wv.based_on:
                    hosting_service = HostingService.from_url(wv.based_on)
                elif workflow_registry:
                    hosting_service = workflow_registry
                if hosting_service:
                    wv.hosting_service = hosting_service
                # parse roc_metadata and register suites and instances
                try:
                    if wv.roc_suites:
                        for _, raw_suite in wv.roc_suites.items():
                            cls._init_test_suite_from_json(wv, workflow_submitter, raw_suite)
                except KeyError as e:
                    raise lm_exceptions.SpecificationNotValidException(f"Missing property: {e}")
            else:
                logger.debug("No changes detected in the ROCrate")

        # update name
        if name is None:
            if wv.workflow_name is None and w.name is None:
                raise lm_exceptions.LifeMonitorException(title="Missing attribute 'name'",
                                                         detail="Attribute 'name' is not defined and it cannot be retrieved \
                                                        from the workflow RO-Crate (name of 'mainEntity' not found)",
                                                         status=400)
            w.name = wv.workflow_name if wv.workflow_name else w.name
        else:
            w.name = name
            wv.name = name
        # update version label
        if new_version_label is not None:
            wv.version = new_version_label
        # update visibility
        if public is not None:
            w.public = public
        # store the new version
        w.save()
        return wv

    @classmethod
    def deregister_user_workflow(cls, workflow_uuid, workflow_version, user: User):
        workflow = cls._find_and_check_workflow_version(user, workflow_uuid, workflow_version)
        logger.debug("WorkflowVersion to delete: %r", workflow)
        if not workflow:
            raise lm_exceptions.EntityNotFoundException(models.WorkflowVersion, entity_id=(workflow_uuid, workflow_version))
        if workflow.submitter != user:
            raise lm_exceptions.NotAuthorizedException("Only the workflow submitter can delete the workflow")
        workflow.delete()
        logger.debug("Deleted workflow wf_uuid: %r - version: %r", workflow_uuid, workflow_version)
        return workflow_uuid, workflow_version

    @staticmethod
    def deregister_registry_workflow(workflow_uuid, workflow_version, registry: models.WorkflowRegistry):
        workflow = registry.get_workflow(workflow_uuid)
        if not workflow:
            raise lm_exceptions.EntityNotFoundException(models.WorkflowVersion, (workflow_uuid, workflow_version))
        logger.debug("WorkflowVersion to delete: %r", workflow)
        try:
            workflow_version = workflow.versions[workflow_version]
            workflow.delete()
            logger.debug("Deleted workflow wf_uuid: %r - version: %r", workflow_uuid, workflow_version)
            return workflow_uuid, workflow_version
        except KeyError:
            raise lm_exceptions.EntityNotFoundException(models.WorkflowVersion, (workflow_uuid, workflow_version))

    @staticmethod
    def _init_test_suite_from_json(wv: models.WorkflowVersion, submitter: models.User, raw_suite):
        """ Create a TestSuite instance (with its related TestInstance)
            from an intermediate JSON representation like:
                {
                    "roc_suite": <ROC_SUITE_ID>,
                    "name": ...,
                    "definition": {
                        "test_engine": {
                            "type": t,
                            "version": ...,
                        },
                        "path": ...,
                    },
                    "instances": [
                        {
                            "roc_instance": <ROC_INSTANCE_ID>,
                            "name": ...,
                            "resource": ...,
                            "service": {
                                "type": ...,
                                "url": ...,
                            },
                        }
                    ]
                }
        """
        try:
            suite = wv.add_test_suite(submitter, raw_suite['name'],
                                      roc_suite=raw_suite['roc_suite'],
                                      definition=raw_suite['definition'])
            for raw_instance in raw_suite["instances"]:
                logger.debug("Instance: %r", raw_instance)
                test_instance = suite.add_test_instance(submitter, raw_instance.get('managed', False),
                                                        raw_instance["name"],
                                                        raw_instance["service"]["type"],
                                                        raw_instance["service"]["url"],
                                                        raw_instance["resource"],
                                                        raw_instance['roc_instance'])
                logger.debug("Created TestInstance: %r", test_instance)
            return suite
        except KeyError as e:
            raise lm_exceptions.SpecificationNotValidException(f"Missing property: {e}")

    @staticmethod
    def subscribe_user_resource(user: User, resource: Resource, events: List[EventType] = None) -> Subscription:
        assert user and not user.is_anonymous, "Invalid user"
        assert resource, "Invalid resource"
        subscription = user.subscribe(resource)
        if events:
            subscription.events = events
        user.save()
        return subscription

    @staticmethod
    def unsubscribe_user_resource(user: User, resource: Resource) -> Subscription:
        assert user and not user.is_anonymous, "Invalid user"
        assert resource, "Invalid resource"
        subscription = user.unsubscribe(resource)
        if isinstance(resource, models.Workflow):
            w: models.Workflow = resource
            for v in w.get_user_versions(user):
                user.unsubscribe(v)
        user.save()
        return subscription

    @classmethod
    def register_test_suite(cls, workflow_uuid, workflow_version,
                            submitter: models.User, test_suite_metadata) -> models.TestSuite:
        workflow = models.WorkflowVersion.get_user_workflow_version(submitter, workflow_uuid, workflow_version)
        if not workflow:
            raise lm_exceptions.EntityNotFoundException(models.WorkflowVersion, (workflow_uuid, workflow_version))
        # For now only the workflow submitter can add test suites
        if workflow.submitter != submitter:
            raise lm_exceptions.NotAuthorizedException("Only the workflow submitter can add test suites")
        assert isinstance(workflow, models.WorkflowVersion)
        suite = cls._init_test_suite_from_json(workflow, submitter, test_suite_metadata)
        suite.save()
        return suite

    @staticmethod
    def deregister_test_suite(test_suite: Union[models.TestSuite, str]) -> str:
        suite = test_suite
        if not isinstance(test_suite, models.TestSuite):
            suite = models.TestSuite.find_by_uuid(test_suite)
            if not suite:
                raise lm_exceptions.EntityNotFoundException(models.TestSuite, test_suite)
        suite.delete()
        logger.debug("Deleted TestSuite: %r", suite.uuid)
        return suite.uuid

    @staticmethod
    def register_test_instance(test_suite: Union[models.TestSuite, str],
                               submitter: User,
                               managed: bool,
                               test_name, testing_service_type,
                               testing_service_url, testing_service_resource):
        suite = test_suite
        if not isinstance(test_suite, models.TestSuite):
            suite = models.TestSuite.find_by_uuid(test_suite)
            if not suite:
                raise lm_exceptions.EntityNotFoundException(models.TestSuite, test_suite)
        test_instance = suite.add_test_instance(submitter,
                                                managed,
                                                test_name,
                                                testing_service_type, testing_service_url,
                                                testing_service_resource)
        test_instance.save()
        return test_instance

    @staticmethod
    def deregister_test_instance(test_instance: Union[models.TestInstance, str]):
        instance = test_instance
        if not isinstance(instance, models.TestInstance):
            instance = models.TestSuite.find_by_uuid(instance)
            if not instance:
                raise lm_exceptions.EntityNotFoundException(models.TestInstance, test_instance)
        instance.delete()
        return instance.uuid

    @classmethod
    def get_workflow_registry_by_generic_reference(cls, registry_reference) -> models.WorkflowRegistry:
        try:
            return cls.get_workflow_registry_by_name(registry_reference)
        except lm_exceptions.EntityNotFoundException:
            pass
        try:
            return cls.get_workflow_registry_by_uri(registry_reference)
        except lm_exceptions.EntityNotFoundException:
            pass
        return cls.get_workflow_registry_by_uuid(registry_reference)

    @staticmethod
    def get_workflow_registry_by_uuid(registry_uuid) -> models.WorkflowRegistry:
        try:
            r = models.WorkflowRegistry.find_by_uuid(registry_uuid)
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
    def get_workflow(wf_uuid) -> models.Workflow:
        return models.Workflow.find_by_uuid(wf_uuid)

    @staticmethod
    def get_workflows() -> List[models.Workflow]:
        return models.Workflow.all()

    @staticmethod
    def get_registry_workflows(registry: models.WorkflowRegistry) -> List[models.Workflow]:
        return registry.get_workflows()

    @staticmethod
    def get_registry_workflow(registry: models.WorkflowRegistry) -> models.Workflow:
        return registry.registered_workflow_versions

    @staticmethod
    def get_registry_workflow_versions(registry: models.WorkflowRegistry, uuid) -> List[models.WorkflowVersion]:
        return registry.get_workflow(uuid).versions.values()

    @staticmethod
    def get_registry_workflow_version(registry: models.WorkflowRegistry, uuid, version=None) -> models.WorkflowVersion:
        w = registry.get_workflow(uuid)
        if w is None:
            raise lm_exceptions.EntityNotFoundException(models.WorkflowVersion, f"{uuid}_{version}")
        return w.latest_version if version is None or version == "latest" else w.versions[version]

    @staticmethod
    def get_public_workflows() -> List[models.Workflow]:
        return models.Workflow.get_public_workflows()

    @staticmethod
    def get_user_workflows(user: User, include_subscriptions: bool = False) -> List[models.Workflow]:
        workflows = [w for w in models.Workflow.get_user_workflows(user, include_subscriptions=include_subscriptions)]
        for svc in models.WorkflowRegistry.all():
            if svc.get_user(user.id):
                try:
                    workflows.extend([w for w in svc.get_user_workflows(user)
                                      if w not in workflows])
                except lm_exceptions.NotAuthorizedException as e:
                    logger.debug(e)
        return workflows

    @staticmethod
    def get_user_registry_workflows(user: User, registry: models.WorkflowRegistry) -> List[models.Workflow]:
        workflows = []
        if registry.get_user(user.id):
            try:
                workflows.extend([w for w in registry.get_user_workflows(user)
                                  if w not in workflows])
            except lm_exceptions.NotAuthorizedException as e:
                logger.debug(e)
        return workflows

    @classmethod
    def get_public_workflow(cls, uuid, version=None) -> models.Workflow:
        return cls._find_and_check_workflow_version(None, uuid, version).workflow

    @classmethod
    def get_public_workflow_version(cls, uuid, version=None) -> models.Workflow:
        return cls._find_and_check_workflow_version(None, uuid, version)

    @classmethod
    def get_user_workflow(cls, user: models.User, uuid, version=None) -> models.Workflow:
        return cls._find_and_check_workflow_version(user, uuid, version).workflow

    @classmethod
    def get_user_workflow_version(cls, user: models.User, uuid, version=None) -> models.WorkflowVersion:
        return cls._find_and_check_workflow_version(user, uuid, version)

    @staticmethod
    def get_workflow_registry_users(registry: models.WorkflowRegistry) -> List[User]:
        return registry.get_users()

    @staticmethod
    def get_suite(suite_uuid) -> models.TestSuite:
        return models.TestSuite.find_by_uuid(suite_uuid)

    @staticmethod
    def get_test_instance(instance_uuid) -> models.TestInstance:
        return models.TestInstance.find_by_uuid(instance_uuid)

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
            registry_scopes = " ".join(OpenApiSpecs.get_instance().registry_scopes.keys())
            server_credentials = providers.new_instance(provider_type=type,
                                                        name=name,
                                                        client_id=client_id,
                                                        client_secret=client_secret,
                                                        api_base_url=api_base_url)
            client_credentials = \
                server.create_client(user, name, server_credentials.api_base_url,
                                     ['client_credentials', 'authorization_code', 'refresh_token'],
                                     ["code", "token"],
                                     registry_scopes,
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
            registry = models.WorkflowRegistry.find_by_uuid(uuid)
            if not registry:
                raise lm_exceptions.EntityNotFoundException(models.WorkflowRegistry, entity_id=uuid)
            if name:
                registry.set_name(name)
            if api_base_url is not None:
                registry.set_uri(api_base_url)
            registry.update_client(client_id=client_id, client_secret=client_secret,
                                   redirect_uris=redirect_uris, client_auth_method=client_auth_method)
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
        return models.WorkflowRegistry.find_by_uuid(uuid)

    @staticmethod
    def setUserNotificationReadingTime(user: User, notifications: List[dict]):
        for n in notifications:
            un = user.get_user_notification(n['uuid'])
            if un is None:
                return lm_exceptions.EntityNotFoundException(Notification, entity_id=n['uuid'])
            un.read = datetime.utcnow()
        user.save()

    @staticmethod
    def deleteUserNotification(user: User, notitification_uuid: str):
        if notitification_uuid is not None:
            n = user.get_user_notification(notitification_uuid)
            logger.debug("Search result notification %r ...", n)
            if n is None:
                return lm_exceptions.EntityNotFoundException(Notification, entity_id=notitification_uuid)
            user.notifications.remove(n)
            user.save()

    @staticmethod
    def deleteUserNotifications(user: User, list_of_uuids: List[str]):
        for n_uuid in list_of_uuids:
            logger.debug("Searching notification %r ...", n_uuid)
            n = user.get_user_notification(n_uuid)
            logger.debug("Search result notification %r ...", n)
            if n is None:
                return lm_exceptions.EntityNotFoundException(Notification, entity_id=n_uuid)
            user.notifications.remove(n)
        user.save()
