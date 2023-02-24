# Copyright (c) 2020-2022 CRS4
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
from typing import Dict, List, Optional, Tuple

from lifemonitor.api import serializers
from lifemonitor.api.models.registries.registry import WorkflowRegistry
from lifemonitor.api.models.repositories.base import IssueCheckResult
from lifemonitor.api.models.repositories.github import GithubWorkflowRepository
from lifemonitor.api.models.workflows import Workflow, WorkflowVersion
from lifemonitor.api.services import LifeMonitor
from lifemonitor.auth.models import HostingService, User
from lifemonitor.auth.oauth2.client.models import (
    OAuthIdentity, OAuthIdentityNotFoundException)
from lifemonitor.integrations.github.events import GithubRepositoryReference
from lifemonitor.integrations.github.registry import GithubWorkflowRegistry

from . import issues, pull_requests

# Config a module level logger
logger = logging.getLogger(__name__)


def ping(event: object):
    logger.debug("Ping event: %r", event)
    return "Pong", 200


def map_issues(check_result: IssueCheckResult):
    repo = check_result.repo
    for issue in check_result.checked:
        if issue in check_result.issues:
            gh_issue = issues.find_issue(repo, issue)
            logger.debug("Found existing gh issue: %r", gh_issue)
            if not gh_issue:
                gh_issue = issues.create_issue(repo, issue)
                logger.debug("Created a new GitHub issue: %r", gh_issue)
                for message in issue.get_messages():
                    gh_issue.create_comment(f"<b>{message.type.name}:</b> {message.text}")
                    logger.debug("Added issue message: %r", message)
                if issue.has_changes():
                    pull_requests.create_pull_request_from_github_issue(repo, issue.id, gh_issue, issue.get_changes(repo), allow_update=False)
        else:
            issues.close_issue(repo, issue)


def check_repository_issues(repository_reference: GithubRepositoryReference) -> IssueCheckResult:
    logger.debug("Repository ref: %r", repository_reference)
    repo: GithubWorkflowRepository = repository_reference.repository
    logger.debug("Repository: %r", repo)
    check_result = repo.check(fail_fast=True,
                              include=repo.config.include_issues if repo.config else None,
                              exclude=repo.config.exclude_issues if repo.config else None)
    logger.debug("Issue check result: %r", check_result)
    map_issues(check_result)
    return check_result


def __normalize_registry_identitiers__(registries: List[str], as_strings: bool = True):
    return [] if not registries else \
        [r if not as_strings else r.client_name
         for r in WorkflowRegistry.all() if r.client_name in registries or r.name in registries]


def __get_registries_map__(w: Workflow, registries: List[str]):
    registries_map = []
    for r_id in registries:
        r_wv = None
        versions = []
        for v in w.versions.values():
            r_wv = v.registry_workflow_versions.get(r_id, None)
            if r_wv:
                versions.append(r_wv)
        map_item = (r_id, versions[0].identifier if len(versions) > 0 else None, versions)
        if map_item not in registries_map:
            registries_map.append(map_item)
    return registries_map


def find_workflow_version(repository_reference: GithubRepositoryReference) -> Tuple[Workflow, WorkflowVersion]:
    # found the existing workflow associated with repo
    github_registry: GithubWorkflowRegistry = repository_reference.event.installation.github_registry
    workflow_version = None
    workflow = github_registry.find_workflow(repository_reference.repository.full_name)
    if workflow:
        workflow_version = workflow.versions.get(repository_reference.branch or repository_reference.tag, None)
        logger.debug("Found workflow version: %r", workflow_version)
    return workflow, workflow_version


def register_repository_workflow(repository_reference: GithubRepositoryReference, registries: List[str] = None) -> WorkflowVersion:
    logger.debug("Repository ref: %r", repository_reference)
    # set a reference to LifeMonitorService
    lm = LifeMonitor.get_instance()
    # set a reference to the github repo
    repo: GithubWorkflowRepository = repository_reference.repository
    logger.debug("Repository: %r", repo)

    # set reference to the github workflow registry
    github_registry: GithubWorkflowRegistry = repository_reference.event.installation.github_registry

    # normalized list of registries
    registries = __normalize_registry_identitiers__(registries)

    #
    registered_workflow = None

    try:
        # set a reference to the Gihub hosting service instance
        hosting_service: HostingService = repository_reference.hosting_service
        logger.debug("Hosting service: %r", hosting_service)
        # set the workflow version name
        workflow_version = repository_reference.branch or repository_reference.tag
        # search user identity
        identity: OAuthIdentity = hosting_service.server_credentials\
            .find_identity_by_provider_user_id(str(repository_reference.owner_id))
        repo_owner = identity.user
        logger.debug("Workflow Submitter: %r", repo_owner)
        # set the repo link
        repo_link = f"{hosting_service.uri}/{repo.full_name}.git"
        logger.debug("Workflow RepoLink: %s", repo_link)
        # found and update the existing workflows associated with
        workflow = github_registry.find_workflow(repo.full_name)
        if workflow:
            logger.debug("Updating workflow: %r", workflow)
            current_wv = wv = workflow.versions.get(workflow_version, None)

            # initialize registries map
            registries_map = __get_registries_map__(workflow, registries=registries)

            logger.debug("Created registries map: %r", registries_map)
            # register or update the workflow version
            if not wv:
                logger.debug("Registering workflow version on worlflow: %r ....", workflow)
                wv = lm.register_workflow(repo_link, repo_owner, workflow_version,
                                          workflow_uuid=workflow.uuid,
                                          name=repo.config.workflow_name, public=repo.config.public)
                logger.debug("Registering workflow version on worlflow: %r .... DONE", workflow)
            else:
                logger.debug("Updating workflow version: %r...", wv)
                wv = lm.update_workflow(wv.submitter, workflow.uuid, workflow_version,
                                        name=repo.config.workflow_name,
                                        rocrate_or_link=repo_link, public=repo.config.public)
                logger.debug("Updating workflow version: %r... DONE", wv)

            # register workflow on registries
            logger.debug("(old,new) workflows: (%r, %r)", current_wv, wv)
            if current_wv != wv:
                register_workflow_on_registries(github_registry, repo_owner, repo, wv, registries_map)
            else:
                # register workflow on new registries if any
                registries_list = [r for r in registries_map if r[0] not in wv.registry_workflow_versions] if registries_map else None
                if registries_list:
                    if current_wv != wv or len(registries_list) > 0:
                        register_workflow_on_registries(github_registry, repo_owner, repo, wv, registries_list)
                else:
                    logger.warning("Skipped registration of workflow %r on registries %r", wv, registries_list)
            # append to the list of registered workflows
            registered_workflow = wv
        # if no matches found, register a new workflow
        else:
            # register workflow version on LifeMonitor
            wv = lm.register_workflow(repo_link, repo_owner, workflow_version,
                                      name=repo.config.workflow_name, public=repo.config.public)
            # register workflow on registries
            register_workflow_on_registries(github_registry, repo_owner, repo, wv, registries_map=[(_, None, []) for _ in registries])
            # append to the list of registered workflows
            registered_workflow = wv

        # register workflow version on github registry
        if registered_workflow:
            github_registry.add_workflow_version(registered_workflow, repo.full_name, repo.ref)
            github_registry.save()

    except OAuthIdentityNotFoundException as e:
        logger.warning("Github identity '%r' doesn't match with any LifeMonitor user identity", repository_reference.owner_id)
        if logger.isEnabledFor(logging.DEBUG):
            logger.exception(e)

    return registered_workflow


def delete_repository_workflow_version(repository_reference: GithubRepositoryReference,
                                       registries: List[str] = None) -> Dict:
    logger.debug("Deleting Repository ref: %r", repository_reference)
    # set a reference to LifeMonitorService
    lm = LifeMonitor.get_instance()
    # set a reference to the github repo
    repo: GithubWorkflowRepository = repository_reference.repository
    logger.debug("Repository: %r", repo)

    try:
        # set reference to the github workflow registry
        github_registry: GithubWorkflowRegistry = repository_reference.event.installation.github_registry
        # set a reference to the Gihub hosting service instance
        hosting_service: HostingService = repository_reference.hosting_service
        logger.debug("Hosting service: %r", hosting_service)
        # set the workflow version name
        workflow_version = repository_reference.branch or repository_reference.tag
        # search user identity
        identity: OAuthIdentity = hosting_service.server_credentials\
            .find_identity_by_provider_user_id(str(repository_reference.owner_id))
        repo_owner = identity.user
        # set the repo link
        repo_link = f"{hosting_service.uri}/{repo.full_name}.git"
        logger.debug("RepoLink: %s", repo_link)

        # Try to delete the workflow from registries only if it has only one version.
        # Deletion of a single workflow version is not supported at the moment
        # due to the limitation of the supported registry API (i.e., Seek)
        w = github_registry.find_workflow(repo.full_name)
        if not w:
            logger.warning(f"No workflow associated with '{repo.full_name}' found")
        else:
            # try to find the workflow version
            wv = lm.get_user_workflow_version(repo_owner, w.uuid, workflow_version)
            if not wv:
                logger.warning(f"Unable to find the version {workflow_version} of workflow {w.uuid}")
                return None
            else:
                # serialize the workflow version object before deletion
                wv = serializers.WorkflowVersionSchema(exclude=('meta', 'links')).dump(wv)

            # normalize the list of registries
            registries = __normalize_registry_identitiers__(registries, as_strings=True)
            logger.debug("Normalized list of registries: %r", registries)

            # initialize registries map
            registry_workflows_map = __get_registries_map__(w, registries=registries)
            logger.debug("List of registries for wf %r: %r", w, registry_workflows_map)

            # filter workflows with only one version
            filtered_registries = [_ for _ in registry_workflows_map if len(_[2]) == 1]
            logger.debug("Filtered registry workflows: %r", filtered_registries)

            # delete workflow from registries
            logger.debug("Removing version '%r' of worlflow %r from registries %r....", workflow_version, w, filtered_registries)
            delete_workflow_from_registries(github_registry, repo_owner, w, filtered_registries)
            logger.debug("Removing version '%r' of worlflow %r from registries %r.... DONE", workflow_version, w, filtered_registries)

            # delete workflow version from LifeMonitor
            logger.debug("Removing version '%r' of worlflow %r from LifeMonitor....", workflow_version, w)

            lm.deregister_user_workflow_version(w.uuid, workflow_version, repo_owner)
            logger.debug("Removing version '%r' of worlflow %r from LifeMonitor.... DONE", workflow_version, w)

            # return the deleted workflow version (serialized)
            return wv

    except OAuthIdentityNotFoundException as e:
        logger.warning("Github identity '%r' doesn't match with any LifeMonitor user identity", repository_reference.owner_id)
        if logger.isEnabledFor(logging.DEBUG):
            logger.exception(e)

    return None


def register_workflow_on_registries(github_registry: GithubWorkflowRegistry, submitter: User, repo: GithubWorkflowRepository,
                                    workflow: WorkflowVersion, registries_map: List[Tuple[str, Optional[str]]]):
    result = []
    logger.debug("Registries map: %r", registries_map)
    for registry_name, workflow_identifier, _ in registries_map:
        logger.debug("Registering workflow %r on registry %r ", workflow, registry_name)
        registry: WorkflowRegistry = WorkflowRegistry.find_by_client_name(registry_name)
        logger.debug("Registry: %r", registry)
        if registry:
            result.append(register_workflow_on_registry(github_registry, submitter, repo, workflow, workflow_identifier, registry))
    return result


def register_workflow_on_registry(github_registry: GithubWorkflowRegistry, submitter: User,
                                  repo: GithubWorkflowRepository, workflow_version: WorkflowVersion,
                                  workflow_identifier: str, registry: Optional[str | WorkflowRegistry]):
    assert isinstance(registry, str) or isinstance(registry, WorkflowRegistry), registry
    registry: WorkflowRegistry = WorkflowRegistry.find_by_client_name(registry) if isinstance(registry, str) else registry
    logger.warning("Registry: %r", registry)
    if registry:
        try:
            registered_workflow = registry.register_workflow_version(
                submitter, workflow_version.repository, external_id=workflow_identifier)
            logger.debug("Registered workflows: %r", registered_workflow)
            workflow_version.workflow.external_id = registered_workflow.identifier
            logger.debug("Adding workflow version %r to registry %r", workflow_version, registry)
            registry.add_workflow_version(workflow_version, registered_workflow.identifier, registered_workflow.latest_version, registry_workflow=registered_workflow)
            for auth in submitter.get_authorization(registry):
                auth.resources.append(workflow_version.workflow)
            workflow_version.save()
            return registered_workflow
        except Exception as e:
            logger.exception(e)
    return None


def delete_workflow_from_registries(github_registry: GithubWorkflowRegistry, submitter: User,
                                    workflow: WorkflowVersion, registries_map: List[Tuple[str, Optional[str]]]):
    result = []
    logger.debug("Registries: %r", registries_map)
    for registry_name, workflow_identifier, _ in registries_map:
        logger.debug("Processing deletion of workflow %r on registry %r", workflow_identifier, registry_name)
        if workflow_identifier:
            registry: WorkflowRegistry = WorkflowRegistry.find_by_client_name(registry_name)
            logger.debug("Registry: %r", registry)
            if registry:
                registry.client.delete_workflow(submitter, workflow_identifier)
                result.append(workflow_identifier)
    return result
