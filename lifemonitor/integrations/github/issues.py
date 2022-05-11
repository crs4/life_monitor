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
import re
from typing import List, Union

from lifemonitor.api.models import issues
from lifemonitor.integrations.github.app import LifeMonitorGithubApp

from github.Issue import Issue
from github.IssueComment import IssueComment
from github.Repository import Repository

from . import pull_requests
from .utils import delete_branch, get_labels_from_strings

# Config a module level logger
logger = logging.getLogger(__name__)


class GithubIssue(Issue):

    def __init__(self, requester, headers, attributes, completed):
        super().__init__(requester, headers, attributes, completed)

    def as_repository_issue(self) -> issues.WorkflowRepositoryIssue:
        issue = None
        issue_type = issues.WorkflowRepositoryIssue.from_string(self.title)
        if issue_type:
            issue: issues.WorkflowRepositoryIssue = issue_type()
        return issue


class GithubIssueComment(IssueComment):

    def __init__(self, issue: GithubIssue, requester, headers, attributes, completed):
        super().__init__(requester, headers, attributes, completed)
        self.issue = issue
        self._addressed_to_bot = None
        self.__body = None
        app = LifeMonitorGithubApp.get_instance()
        self.__bot_id = app.bot
        self._pattern = re.compile(r'^@(lm|{0})(\[bot\])?(\s(.*))?'.format(app.bot.strip('[bot]')))

    def __process_comment__(self):
        self.__body = super().body
        if self.user.login == self.__bot_id:
            logger.debug("Comment crated by LifeMonitor Bot")
            self._addressed_to_bot = False
        else:
            m = self._pattern.match(self.__body)
            if not m:
                logger.debug(f"Generic message not addressed to LifeMonitor[bot]")
                self._addressed_to_bot = False
                self.__body = ""
            elif len(m.groups()) < 4:
                logger.debug("Message empty: %r", m.lastgroup)
                self._addressed_to_bot = True
                self.__body = ""
            else:
                logger.debug("Message to LifeMonitor[bot]: %r", m.lastgroup)
                self.__body = m.group(4)
                self._addressed_to_bot = True

    def is_generated_by_bot(self) -> bool:
        return self.user.login == self.__bot_id

    def is_addressed_to_bot(self) -> bool:
        if self._addressed_to_bot is None:
            self.__process_comment__()
        return self._addressed_to_bot

    @property
    def body(self) -> str:
        if self.__body is None:
            self.__process_comment__()
        return self.__body


def process_issues(repo: Repository, issues: List[issues.WorkflowRepositoryIssue]):
    for issue in issues:
        if not issue.has_changes():
            if not find_issue(repo, issue):
                create_issue(repo, issue)
        else:
            if not pull_requests.find_pull_request(repo, issue):
                pull_requests.create_pull_request_from_issue(repo, issue)


def create_issue(repo: Repository, issue: Union[str, issues.WorkflowRepositoryIssue]):
    assert isinstance(repo, Repository)
    if isinstance(issue, str):
        issue = issues.WorkflowRepositoryIssue.from_string(issue)
    if not issue:
        raise ValueError(f"Issue '{issue}' not found")
    try:
        return repo.create_issue(
            title=issue.name,
            body=issue.description,
            labels=get_labels_from_strings(repo, issue.labels)
        )
    except KeyError as e:
        raise ValueError(f"Issue not valid: {str(e)}")


def close_issue(repo: Repository, issue: Union[str, issues.WorkflowRepositoryIssue]):
    assert isinstance(repo, Repository)
    if isinstance(issue, str):
        issue = issues.WorkflowRepositoryIssue.from_string(issue)
    if not issue:
        raise ValueError(f"Issue '{issue}' not found")
    open_issue = find_issue(repo, issue)
    if open_issue:
        open_issue.edit(state='closed')
    # delete PR branch
    delete_branch(repo, issue.id)


def find_issue(repo: Repository, issue: Union[str, issues.WorkflowRepositoryIssue]) -> Issue:
    if isinstance(issue, str):
        issue = issues.WorkflowRepositoryIssue.from_string(issue)
    if not issue:
        raise ValueError(f"Issue '{issue}' not found")
    lm = LifeMonitorGithubApp.get_instance()
    for i in repo.get_issues():
        logger.debug("Checking issue: %r - %r - %r", issue.name, i.user.login, lm.bot)
        if i.user.login == lm.bot and i.title == issue.name:
            logger.debug("Issue '%r' found", issue)
            return i
    return None
