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

from lifemonitor.api.models.repositories.base import IssueCheckResult
from lifemonitor.api.models.repositories.github import GithubWorkflowRepository
from lifemonitor.api.models.workflows import Workflow
from lifemonitor.api.services import LifeMonitor
from lifemonitor.auth.models import HostingService
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


def register_repository_workflow(repository_reference: GithubRepositoryReference):
    logger.debug("Repository ref: %r", repository_reference)
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
            if not wv:
                logger.debug("Registering workflow version on worlflow: %r", w)
                lm.register_workflow(repo_link, repo_owner, workflow_version, w.uuid)
            else:
                logger.debug("Updating workflow version: %r", wv)
                lm.update_workflow(wv.submitter, w.uuid, workflow_version, rocrate_or_link=repo_link)
        # if no matches found, register a new workflow
        if len(workflows) == 0:
            logger.debug("Submitter: %r", repo_owner)
            lm.register_workflow(repo_link, repo_owner, workflow_version)
    except OAuthIdentityNotFoundException as e:
        logger.warning("Github identity '%r' doesn't match with any LifeMonitor user identity", repository_reference.owner_id)
        if logger.isEnabledFor(logging.DEBUG):
            logger.exception(e)


def delete_repository_workflow_version(repository_reference: GithubRepositoryReference):
    logger.debug("Repository ref: %r", repository_reference)
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
                logger.debug("Removing version '%r' of worlflow: %r", workflow_version, w)
                lm.deregister_user_workflow(w.uuid, workflow_version, repo_owner)
            else:
                logger.debug("No version '%r' of workflow '%r' found", workflow_version, w)

    except OAuthIdentityNotFoundException as e:
        logger.warning("Github identity '%r' doesn't match with any LifeMonitor user identity", repository_reference.owner_id)
        if logger.isEnabledFor(logging.DEBUG):
            logger.exception(e)
