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
import re
from typing import (Any, Callable, Dict, List, Optional, OrderedDict, Tuple,
                    Type, Union)

import github
from github.GithubException import GithubException
from github.GitRef import GitRef
from github.Issue import Issue
from github.Label import Label
from github.PaginatedList import PaginatedList
from github.Repository import Repository
from github.Requester import Requester

from lifemonitor.cache import Timeout, cache_function
from lifemonitor.integrations.github.config import (DEFAULT_BASE_URL,
                                                    DEFAULT_PER_PAGE,
                                                    DEFAULT_TIMEOUT)
from lifemonitor.utils import parse_date_interval

from ...api.models.wizards import (IOHandler, QuestionStep, Step, UpdateStep,
                                   Wizard)

# Config a module level logger
logger = logging.getLogger(__name__)


def is_github_url(url):
    """
    Returns True if the given URL is a GitHub URL, False otherwise.
    """
    pattern = r"^https?://(www\.)?github\.com/.*$"
    return bool(re.match(pattern, url))


def normalized_github_url(url):
    if not is_github_url(url):
        return None
    if not url.endswith('.git'):
        url += '.git'
    return url


def crate_branch(repo: Repository, branch_name: str, rev: str = None) -> GitRef:
    head = repo.get_commit(rev or repo.rev or 'HEAD')
    logger.debug("HEAD commit: %r", head.sha)
    logger.debug("New target branch ref: %r", f'refs/heads/{branch_name}'.format(**locals()))
    return repo.create_git_ref(ref=f'refs/heads/{branch_name}'.format(**locals()), sha=head.sha)


def delete_branch(repo: Repository, branch_name: str) -> bool:
    try:
        ref = repo.get_git_ref(f"heads/{branch_name}".format(**locals()))
        ref.delete()
        return True
    except GithubException as e:
        logger.debug("Unable to delete branch '%s': %s", branch_name, str(e))
        return False


def get_labels_from_strings(repo: Repository, labels: List[str]) -> List[Label]:
    result = []
    if labels:
        for name in labels:
            label = None
            try:
                label = repo.get_label(name)
            except GithubException:
                logger.debug("Label %s not found...", name)
                try:
                    label = repo.create_label(name, '1f8787')
                except GithubException as e:
                    if logger.isEnabledFor(logging.DEBUG):
                        logger.exception(e)
                    logger.error(f"Unable to create label: {name}: {str(e)}")
            if label:
                result.append(label)
    return result


class GithubIOHandler(IOHandler):

    def __init__(self, app, issue: Issue) -> None:
        super().__init__()
        self.issue = issue
        self.app = app

    def get_input(self, question: QuestionStep) -> object:
        assert isinstance(question, QuestionStep), question
        found = False
        candidates = []
        helper: Wizard = question.wizard
        next_step = helper.get_next_step(question, ignore_skip=True)
        logger.debug("Next step: %r", next_step)
        for c in self.issue.get_comments():
            logger.debug("Checking comment: %r", c.body)
            step = question.wizard.find_step(c.body)
            logger.debug("Current step: %r", step)
            if step and step.title == question.title:
                found = True
            elif found:
                logger.debug("Found")
                if not next_step or step != next_step:
                    logger.debug("Adding... %r", c)
                    candidates.append(c)
                else:
                    break
        logger.debug("Candidates: %r", candidates)
        for ca in reversed(candidates):
            cbody = self.parse_answer(ca)
            logger.debug("Checking candidate: %r -- options: %r", cbody, question.options)
            logger.debug("Check condition: %r", cbody in question.options)
            if question.options is None or len(question.options) == 0 or cbody in question.options:
                return ca
        return None

    def parse_answer(self, answer: object) -> str:
        return re.sub(r'(@%s)\s+' % self.app.bot.strip("[bot]"), '',
                      answer.body) if answer else None

    def get_input_as_text(self, question: QuestionStep) -> object:
        return self.parse_answer(self.get_input(question))

    def as_string(self, step: Step, append_help: bool = False) -> str:
        result = f"<b>{step.title}</b><br/>"
        if step.description:
            result += f"{step.description}<br/>"
        if isinstance(step, QuestionStep) and step.options:
            result += "<br>> Choose among the following options: <b><code>{}</code></b><br>".format(', '.join(step.options))
        if isinstance(step, UpdateStep):
            logger.debug("Preparing PR... %r", step)
        if append_help:
            result += self.get_help()
        return result

    def get_help(self):
        return f'<br>\n> **?** type **@{self.app.bot.strip("[bot]")}** to answer'

    def write(self, step: Step, append_help: bool = False):
        assert isinstance(step, Step), step
        self.issue.create_comment(step.as_string(append_help=append_help))


class GithubApiWrapper(github.Github):
    """
    Extend the main Github class to customise the internal requester object.
    """

    def __init__(
        self,
        login_or_token=None,
        password=None,
        jwt=None,
        base_url=DEFAULT_BASE_URL,
        timeout=DEFAULT_TIMEOUT,
        user_agent="PyGithub/Python",
        per_page=DEFAULT_PER_PAGE,
        verify=True,
        retry=None,
        pool_size=None,
    ):
        super().__init__(login_or_token, password, jwt, base_url, timeout,
                         user_agent, per_page, verify, retry, pool_size)  # type: ignore
        self.__requester = CachedGithubRequester(
            login_or_token,
            password,
            jwt,
            base_url,
            timeout,
            user_agent,
            per_page,
            verify,
            retry,
            pool_size,
        )  # type: ignore


def __cache_request_value__(requester, verb: str, url: str, *args,
                            parameters: Optional[Dict[str, Any]] = None,
                            headers: Optional[Dict[str, str]] = None,
                            input: Optional[Any] = None, **kwargs):
    logger.debug("VERB: %r", verb)
    logger.debug("URL: %r", url)
    if verb.upper() != "GET":
        return True
    return False


class CachedGithubRequester(Requester):

    """
    Extend the default Github Requester to enable caching.
    """

    # @cached(timeout=Timeout.NONE, client_scope=False, transactional_update=True, unless=__cache_request_value__)
    def requestJsonAndCheck(self, verb: str, url: str,
                            parameters: Optional[Dict[str, Any]] = None,
                            headers: Optional[Dict[str, str]] = None,
                            input: Optional[Any] = None) -> Tuple[Dict[str, Any], Optional[Dict[str, Any]]]:
        return super().requestJsonAndCheck(verb, url, parameters, headers, input)

    # @cached(timeout=Timeout.NONE, client_scope=False, transactional_update=True, unless=__cache_request_value__)
    def requestMultipartAndCheck(self, verb: str, url: str,
                                 parameters: Optional[Dict[str, Any]] = None,
                                 headers: Optional[Dict[str, Any]] = None,
                                 input: Optional[OrderedDict] = None) -> Tuple[Dict[str, Any], Optional[Dict[str, Any]]]:
        return super().requestMultipartAndCheck(verb, url, parameters, headers, input)

    # @cached(timeout=Timeout.NONE, client_scope=False, transactional_update=True, unless=__cache_request_value__)
    def requestBlobAndCheck(self, verb: str, url: str,
                            parameters: Optional[Dict[str, Any]] = None,
                            headers: Optional[Dict[str, Any]] = None,
                            input: Optional[str] = None) -> Tuple[Dict[str, Any], Optional[Dict[str, Any]]]:
        return super().requestBlobAndCheck(verb, url, parameters, headers, input)


class CachedPaginatedList(PaginatedList):

    """
    Extend the default Github PaginatedList to enable caching of list items.
    """

    def __init__(self, contentClass: Type, requester: Requester,
                 firstUrl: str, firstParams: Any, headers: Optional[Dict[str, str]] = None,
                 list_item: str = "items",
                 transactional_update: Union[bool, Callable, None] = False,
                 force_use_cache: Union[bool, Callable, None] = False,
                 unless: Union[bool, Callable, None] = None,
                 limit: Optional[int] = None) -> None:
        super().__init__(contentClass, requester, firstUrl, firstParams, headers, list_item)
        self.transaction_update = transactional_update
        self.unless = unless
        self.force_use_cache = force_use_cache
        self.limit = limit
        self.created = firstParams.get('created', None)

    def __process_item__(self, item):

        def _get_item_(item):
            logger.debug("Transaction update: %r", self.force_use_cache(item) if self.force_use_cache else False)
            logger.debug("Run Status: %r", item.status)
            logger.debug("Run attempts: %r", item.raw_data['run_attempt'])
            return item

        logger.debug(f"Processing item: {item}")
        if not item:
            return None

        return cache_function(_get_item_,
                              timeout=Timeout.NONE, client_scope=False,
                              transactional_update=self.transaction_update,
                              unless=self.unless,
                              force_cache_value=self.force_use_cache,
                              args=(item,))

    def __getitem__(self, index):
        return self.__process_item__(super().__getitem__(index))

    def __iter__(self):
        runs_count = 0
        operator = start_date = end_date = None
        try:
            operator, start_date, end_date = parse_date_interval(self.created)
            logger.debug(f"operator={operator} start_date={start_date} end_date={end_date}")
        except ValueError:
            logger.warning("Unable to parse date interval: %r", self.created)
        logger.debug(f"Iterating over attempts: runs limit={self.limit}")
        for item in super().__iter__():
            run_started_at = item.created_at  # datetime.fromisoformat(item.raw_data['run_started_at'][:-1])
            # if operator == '>' and start_date:
            #     if run_started_at <= start_date:
            #         logger.warning(f"Skipping item: {item} {item.created_at} {run_started_at}")
            #         continue
            # elif operator == '>=' and start_date:
            #     if run_started_at < start_date:
            #         logger.warning(f"Skipping item: {item} {item.created_at} {run_started_at}")
            #         continue
            if operator == '<' and end_date:
                if run_started_at >= end_date:
                    logger.warning(f"Skipping item: {item} {item.created_at} {run_started_at}")
                    continue
            # elif operator == '<=' and end_date:
            #     if run_started_at > end_date:
            #         logger.warning(f"Skipping item: {item} {item.created_at} {run_started_at}")
            #         continue
            elif operator == '..' and start_date and end_date:
                if run_started_at < start_date or run_started_at >= end_date:
                    logger.warning(f"Skipping item: {item} {item.created_at} {run_started_at}")
                    continue
            yield self.__process_item__(item)
            runs_count += 1
            logger.debug("Updated number of runs: %r", runs_count)
            if self.limit and runs_count >= self.limit:
                logger.debug("Limit of number of runs reached: %d (limit: %d)", runs_count, self.limit)
                break
