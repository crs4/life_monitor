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
from typing import List, Optional

from lifemonitor.api.models.registries.registry import WorkflowRegistry
from lifemonitor.api.models.repositories.base import IssueCheckResult
from lifemonitor.api.models.repositories.github import GithubWorkflowRepository
from lifemonitor.api.models.workflows import Workflow, WorkflowVersion
from lifemonitor.api.services import LifeMonitor
from lifemonitor.auth.models import HostingService, User
from lifemonitor.auth.oauth2.client.models import (
    OAuthIdentity, OAuthIdentityNotFoundException)
from lifemonitor.integrations.github.events import GithubRepositoryReference

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
            if not issue.has_changes():
                if not issues.find_issue(repo, issue):
                    issues.create_issue(repo, issue)
            else:
                if not pull_requests.find_pull_request(repo, issue):
                    pull_requests.create_pull_request(repo, issue)
        else:
            issues.close_issue(repo, issue)


def check_repository_issues(repository_reference: GithubRepositoryReference) -> IssueCheckResult:
    logger.debug("Repository ref: %r", repository_reference)
    repo: GithubWorkflowRepository = repository_reference.repository
    logger.debug("Repository: %r", repo)
    check_result = repo.check(fail_fast=True)
    logger.debug("Issue check result: %r", check_result)
    map_issues(check_result)
    return check_result


def register_repository_workflow(repository_reference: GithubRepositoryReference, registries: List[WorkflowRegistry] = None):
    logger.debug("Repository ref: %r", repository_reference)
    # set a reference to LifeMonitorService
    lm = LifeMonitor.get_instance()
    # set a reference to the github repo
    repo: GithubWorkflowRepository = repository_reference.repository
    logger.debug("Repository: %r", repo)

    #
    registered_workflows = []

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
        # set the repo link
        repo_link = f"{hosting_service.uri}/{repo.full_name}.git"
        logger.debug("RepoLink: %s", repo_link)
        # found and update the existing workflows associated with
        workflows = Workflow.get_hosted_workflows_by_uri(hosting_service, repo_link, submitter=repo_owner)
        for w in workflows:
            logger.warning("Updating workflow: %r", w)
            current_wv = wv = w.versions.get(workflow_version, None)
            if not wv:
                logger.debug("Registering workflow version on worlflow: %r", w)
                wv = lm.register_workflow(repo_link, repo_owner, workflow_version, w.uuid)
            else:
                logger.debug("Updating workflow version: %r", wv)
                wv = lm.update_workflow(wv.submitter, w.uuid, workflow_version, rocrate_or_link=repo_link)

            # register workflow on registries
            if current_wv != wv:
                register_workflow_on_registries(repo_owner, wv, repository_reference, registries)
            else:
                # register workflow on new registries if any
                registries_list = [r for r in registries if r not in wv.registry_workflow_versions] if registries else None
                if registries_list and current_wv != wv or len(registries_list) > 0:
                    register_workflow_on_registries(repo_owner, wv, repository_reference, registries_list)
                else:
                    logger.warning("Skipped registration of workflow %r on registries %r", wv, registries_list)
            # append to the list of registered workflows
            registered_workflows.append(wv)
        # if no matches found, register a new workflow
        if len(workflows) == 0:
            logger.debug("Submitter: %r", repo_owner)
            # register workflow version on LifeMonitor
            wv = lm.register_workflow(repo_link, repo_owner, workflow_version)
            # register workflow on registries
            register_workflow_on_registries(repo_owner, wv, repository_reference, registries)
            # append to the list of registered workflows
            registered_workflows.append(wv)
    except OAuthIdentityNotFoundException as e:
        logger.warning("Github identity '%r' doesn't match with any LifeMonitor user identity", repository_reference.owner_id)
        if logger.isEnabledFor(logging.DEBUG):
            logger.exception(e)

    return registered_workflows


def delete_repository_workflow_version(repository_reference: GithubRepositoryReference, registries: List[WorkflowRegistry] = None):
    logger.warning("Deleting Repository ref: %r", repository_reference)
    # set a reference to LifeMonitorService
    lm = LifeMonitor.get_instance()
    # set a reference to the github repo
    repo: GithubWorkflowRepository = repository_reference.repository
    logger.debug("Repository: %r", repo)

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
        # set the repo link
        repo_link = f"{hosting_service.uri}/{repo.full_name}.git"
        logger.debug("RepoLink: %s", repo_link)
        # found and update the existing workflows associated with
        workflows = Workflow.get_hosted_workflows_by_uri(hosting_service, repo_link, submitter=repo_owner)
        for w in workflows:
            logger.warning("Updating workflow: %r", w)
            wv = w.versions.get(workflow_version, None)
            if wv:
                # delete workflow version from registries if there are not other versions
                if len(wv.workflow.versions) <= 1:
                    delete_workflow_from_registries(repo_owner, wv, registries)
                # delete workflow version from LifeMontiro
                logger.debug("Removing version '%r' of worlflow: %r", workflow_version, w)
                lm.deregister_user_workflow(w.uuid, workflow_version, repo_owner)
            else:
                logger.debug("No version '%r' of workflow '%r' found", workflow_version, w)

    except OAuthIdentityNotFoundException as e:
        logger.warning("Github identity '%r' doesn't match with any LifeMonitor user identity", repository_reference.owner_id)
        if logger.isEnabledFor(logging.DEBUG):
            logger.exception(e)


def register_workflow_on_registries(submitter: User, workflow: WorkflowVersion,
                                    repository_reference: GithubRepositoryReference, registries: List[str]):
    result = []
    logger.debug("Registries: %r", registries)
    for registry_name in registries:
        logger.debug("Registry: %r", registry_name)
        registry: WorkflowRegistry = WorkflowRegistry.find_by_name(registry_name)
        logger.debug("Registry: %r", registry)
        if registry:
            result.append(register_workflow_on_registry(submitter, workflow, repository_reference, registry))
    return result


def register_workflow_on_registry(submitter: User, workflow_version: WorkflowVersion,
                                  repository_reference: GithubRepositoryReference, registry: Optional[str | WorkflowRegistry]):
    assert isinstance(registry, str) or isinstance(registry, WorkflowRegistry), registry
    registry: WorkflowRegistry = WorkflowRegistry.find_by_name(registry) if isinstance(registry, str) else registry
    logger.warning("Registry: %r", registry)
    if registry:
        registered_workflow = registry.register_workflow_version(
            submitter, repository_reference.repository, external_id=workflow_version.workflow.get_registry_identifier(registry))
        logger.warning("Registered workflows: %r", registered_workflow)
        workflow_version.workflow.external_id = registered_workflow.identifier
        registry.add_workflow_version(workflow_version, registered_workflow.identifier, registered_workflow.latest_version)
        workflow_version.save()
        return registered_workflow
    return None


def delete_workflow_from_registries(submitter: User, workflow: WorkflowVersion, registries: List[str]):
    result = []
    logger.debug("Registries: %r", registries)
    for registry_name in registries:
        logger.debug("Registry: %r", registry_name)
        registry: WorkflowRegistry = WorkflowRegistry.find_by_name(registry_name)
        logger.debug("Registry: %r", registry)
        if registry:
            workflow_registry = workflow.registry_workflow_versions.get(registry.name, None)
            if workflow_registry:
                result.append(registry.client.delete_workflow(submitter, workflow_registry.identifier))
    return result
