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
import os
from typing import List, Union

from lifemonitor.api.models.issues import WorkflowRepositoryIssue
from lifemonitor.api.models.repositories.files import RepositoryFile
from lifemonitor.api.models.repositories.github import \
    InstallationGithubWorkflowRepository
from lifemonitor.exceptions import IllegalStateException
from lifemonitor.integrations.github.app import LifeMonitorGithubApp

from github.GithubException import GithubException
from github.Issue import Issue
from github.PullRequest import PullRequest
from github.Repository import Repository

from . import issues
from .utils import crate_branch, delete_branch

# Config a module level logger
logger = logging.getLogger(__name__)


class GithubPullRequest(PullRequest):

    def __init__(self, requester, headers, attributes, completed):
        super().__init__(requester, headers, attributes, completed)

    def as_repository_issue(self) -> issues.WorkflowRepositoryIssue:
        issue = None
        issue_type = WorkflowRepositoryIssue.from_string(self.title)
        if issue_type:
            issue: issues.WorkflowRepositoryIssue = issue_type()
        return issue

    def as_issue(self) -> issues.GithubIssue:
        return issues.GithubIssue(self._requester, self.raw_headers, super().as_issue().raw_data, True)


def find_pull_request_by_issue(repo: Repository, issue: Union[str, WorkflowRepositoryIssue]) -> PullRequest:
    if isinstance(issue, str):
        issue = WorkflowRepositoryIssue.from_string(issue)
    if not issue:
        raise ValueError(f"Issue '{issue}' not found")
    logger.debug("Searching for PR associated with issue: %r", issue.name)
    return find_pull_request_by_title(repo, issue.name)


def find_pull_request_by_title(repo: Repository, title: str) -> PullRequest:
    lm = LifeMonitorGithubApp.get_instance()
    for i in repo.get_pulls():
        logger.debug("Checking if PR %r matches %r", i, title)
        if i.user.login == lm.bot and i.title == title:
            return i
    return None


def __prepare_pr_head__(repo: InstallationGithubWorkflowRepository,
                        identifier: str, files: List[RepositoryFile], allow_update: bool = True):
    assert isinstance(repo, Repository)

    try:
        head = identifier
        logger.debug("PR head: %r", head)
        branch = None
        try:
            branch = repo.get_branch(head)
            if branch and not allow_update:
                return None
        except GithubException as e:
            logger.debug("Branch not found: %r", str(e))
        try:
            if not branch:
                branch = crate_branch(repo, head)
        except Exception as e:
            raise IllegalStateException("Unable to prepare support branch for PR %r: %r" % (head, str(e)))
        for change in files:
            current_file_version = repo.find_remote_file_by_name(change.name, ref=head)
            if current_file_version:
                logger.debug("Found a previous version of the file: %r", current_file_version)
                if allow_update:
                    repo.update_file(os.path.join(change.dir, change.name),
                                     f"Update {change.name}", change.get_content(),
                                     sha=current_file_version.sha, branch=head)
            else:
                repo.create_file(os.path.join(change.dir, change.name),
                                 f"Add {change.name}", change.get_content(), branch=head)
        return head
    except KeyError as e:
        raise ValueError(f"Issue not valid: {str(e)}")
    except Exception as e:
        logger.exception(e)
        raise RuntimeError(e)


def create_pull_request_from_github_issue(repo: InstallationGithubWorkflowRepository,
                                          identifier: str,
                                          issue: Issue, files: List[RepositoryFile],
                                          allow_update: bool = True,
                                          create_comment: str = None, update_comment: str = None):
    assert isinstance(repo, Repository), repo
    assert isinstance(issue, Issue), issue
    try:
        pr = find_pull_request_by_title(repo, issue.id)
        if pr and update_comment:
            issue.create_comment(update_comment)
        head = __prepare_pr_head__(repo, identifier, files, allow_update=allow_update)
        logger.debug("HEAD: %r -> %r", head, repo)
        if not pr:
            if create_comment:
                issue.create_comment(create_comment)
            pr = repo.create_pull(issue=issue,
                                  base=repo.ref or repo.default_branch, head=head)
        return pr
    except Exception as e:
        logger.exception(e)
        raise RuntimeError(str(e))


def create_pull_request_from_lm_issue(repo: InstallationGithubWorkflowRepository,
                                      issue: Union[str, WorkflowRepositoryIssue],
                                      allow_update: bool = True):
    assert isinstance(repo, Repository)
    if isinstance(issue, str):
        issue = WorkflowRepositoryIssue.from_string(issue)
    if not issue:
        raise ValueError(f"Issue '{issue}' not found")
    return create_pull_request(repo, issue.id, issue.name, issue.description, issue.get_changes(repo), allow_update=allow_update)


def create_pull_request(repo: InstallationGithubWorkflowRepository,
                        identifier: str, title: str, description: str, files: List[RepositoryFile],
                        allow_update: bool = True):
    assert isinstance(repo, Repository)

    try:
        head = __prepare_pr_head__(repo, identifier, files, allow_update=allow_update)
        pr = find_pull_request_by_title(repo, identifier)
        if not pr:
            logger.debug("HEAD: %r -> %r", head, repo)
            pr = repo.create_pull(title=title, body=description,
                                  base=repo.ref or repo.default_branch, head=head)
        return pr
    except Exception as e:
        logger.exception(e)
        raise RuntimeError(e)


def delete_pull_request_by_issue(repo: Repository,
                                 issue: issues.LifeMonitorIssue):
    return delete_pull_request(repo, issue.id, issue.title)


def delete_pull_request(repo: Repository, identifier: str, title: str):
    lm = LifeMonitorGithubApp.get_instance()
    # delete PR
    for pr in repo.get_pulls():
        if pr.user.login == lm.bot and pr.title == title:
            pr.edit(state='closed')
    # delete PR branch
    delete_branch(repo, identifier)
