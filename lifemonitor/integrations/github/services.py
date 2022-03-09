
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

from lifemonitor.api.models import TestInstance
from lifemonitor.api.models.repositories.base import IssueCheckResult
from lifemonitor.api.models.repositories.github import GithubWorkflowRepository
from lifemonitor.cache import cache
from lifemonitor.integrations.github.events import GithubRepositoryReference

from . import issues, pull_requests, utils

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


def check_repository(repository_reference: GithubRepositoryReference):
    logger.debug("Repository ref: %r", repository_reference)
    repo: GithubWorkflowRepository = repository_reference.repository
    logger.debug("Repository: %r", repo)
    check_result = repo.check(fail_fast=True)
    logger.debug("Issue check result: %r", check_result)
    map_issues(check_result)
