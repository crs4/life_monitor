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
from hashlib import sha1
from typing import Union

from lifemonitor.api.models.issues import WorkflowRepositoryIssue
from lifemonitor.api.models.repositories.github import \
    InstallationGithubWorkflowRepository
from lifemonitor.exceptions import IllegalStateException
from lifemonitor.integrations.github.app import LifeMonitorGithubApp

from github.PullRequest import PullRequest
from github.Repository import Repository

from . import issues
from .utils import crate_branch, delete_branch

# Config a module level logger
logger = logging.getLogger(__name__)


def find_pull_request(repo: Repository, issue: Union[str, WorkflowRepositoryIssue]) -> PullRequest:
    if isinstance(issue, str):
        issue = WorkflowRepositoryIssue.from_string(issue)
    if not issue:
        raise ValueError(f"Issue '{issue}' not found")
    lm = LifeMonitorGithubApp.get_instance()
    for i in repo.get_pulls():
        logger.debug("Checking issue: %r - %r - %r", issue.name, i.user.login, lm.bot)
        if i.user.login == lm.bot and i.title == issue.name:
            return i
    return None


def create_pull_request(repo: InstallationGithubWorkflowRepository,
                        issue: Union[str, WorkflowRepositoryIssue],
                        allow_update: bool = True):
    assert isinstance(repo, Repository)
    if isinstance(issue, str):
        issue = WorkflowRepositoryIssue.from_string(issue)
    if not issue:
        raise ValueError(f"Issue '{issue}' not found")
    try:
        head = issue.id
        branch = None
        try:
            branch = repo.get_branch(head)
            if branch and not allow_update:
                return "Nothing to do", 204
        except Exception as e:
            if logger.isEnabledFor(logging.DEBUG):
                logger.exception(e)
        try:
            if not branch:
                branch = crate_branch(repo, head)
        except Exception as e:
            logger.debug(str(e))
            raise IllegalStateException("Unable to prepare support branch for PR %r" % head)
        for change in issue.get_changes():
            current_file_version = repo.find_remote_file_by_name(change.name, ref=head)
            if current_file_version:
                logger.debug("Found a previous version of the file: %r", current_file_version)
                repo.update_file(change.path, f"{issue.name} [update]", change.get_content(), sha=current_file_version.sha, branch=head)
            else:
                repo.create_file(change.path, issue.name, change.get_content(), branch=head)
                repo.create_pull(title=issue.name, body=issue.description, base=repo.ref, head=head)
    except KeyError as e:
        raise ValueError(f"Issue not valid: {str(e)}")


def delete_pull_request(repo: Repository,
                        issue: issues.LifeMonitorIssue):
    lm = LifeMonitorGithubApp.get_instance()
    # delete PR
    for pr in repo.get_pulls():
        if pr.user.login == lm.bot and pr.title == issue.title:
            pr.edit(state='closed')
    # delete PR branch
    delete_branch(repo, issue.id)
