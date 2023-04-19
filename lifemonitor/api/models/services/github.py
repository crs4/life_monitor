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
from typing import Generator, List, Optional, Tuple
from urllib.error import URLError
from urllib.parse import urlparse

import lifemonitor.api.models as models
import lifemonitor.exceptions as lm_exceptions
from lifemonitor.cache import Timeout, cached
from lifemonitor.integrations.github.utils import (CachedPaginatedList,
                                                   GithubApiWrapper)

import github
from github import GithubException
from github import \
    RateLimitExceededException as GithubRateLimitExceededException
from github.GithubException import UnknownObjectException
from github.Repository import Repository
from github.Workflow import Workflow
from github.WorkflowRun import WorkflowRun

from .service import TestingService

# set module level logger
logger = logging.getLogger(__name__)


class GithubTestingService(TestingService):
    _RESOURCE_PATTERN = re.compile(r"/?repos/(?P<owner>[^/]+)/(?P<repo>[^/]+)/actions/workflows/(?P<wf>[^/]+)")

    _gh_obj = None
    __mapper_args__ = {
        'polymorphic_identity': 'github_testing_service'
    }

    # TODO: make these configurable
    _configuration_ = {
        'retry': 2,
        'timeout': 11,
        'per_page': 100
    }

    class GithubStatus:
        COMPLETED = 'completed'
        QUEUED = 'queued'
        IN_PROGRESS = 'in_progress'

    class GithubConclusion:
        ACTION_REQUIRED = 'action_required'
        CANCELLED = 'cancelled'
        FAILURE = 'failure'
        NEUTRAL = 'neutral'
        SUCCESS = 'success'
        SKIPPED = 'skipped'
        STALE = 'stale'
        TIMED_OUT = 'timed_out'

    def __init__(self, url: str = None, token: models.TestingServiceToken = None) -> None:
        logger.debug("GithubTestingService constructor instantiating client")
        if not url:
            url = github.MainClass.DEFAULT_BASE_URL
        super().__init__(url, token)

    def initialize(self):
        try:
            logger.debug("Instantiating with: url %s; token: %r\nClient configuration: %s",
                         self.url, self.token is not None, self._configuration_)
            self._gh_obj = GithubApiWrapper(base_url=self.url,
                                            login_or_token=self.token.value if self.token else None,
                                            **self._configuration_)
            logger.debug("Github client created.")
        except Exception as e:
            raise lm_exceptions.TestingServiceException(e)

    @property
    def base_url(self):
        return 'https://github.com'

    @property
    def api_base_url(self):
        return github.MainClass.DEFAULT_BASE_URL

    @property
    def _gh_service(self) -> GithubApiWrapper:
        logger.debug("Github client requested.")
        if not self._gh_obj:
            self.initialize()
        return self._gh_obj

    @cached(timeout=Timeout.NONE, client_scope=False, transactional_update=True)
    def _get_workflow_info(self, resource):
        return self._parse_workflow_url(resource)

    @cached(timeout=Timeout.NONE, client_scope=False, transactional_update=True)
    def _get_repo(self, test_instance: models.TestInstance):
        logger.debug("Getting github repository from remote service...")
        _, repo_full_name, _ = self._get_workflow_info(test_instance.resource)
        repository = self._gh_service.get_repo(repo_full_name)
        logger.debug("Repo ID: %s", repository.id)
        logger.debug("Repo full name: %s", repository.full_name)
        logger.debug("Repo URL: %s", f'https://github.com/{repository.full_name}')
        return repository

    @staticmethod
    def _convert_github_exception_to_lm(github_exc: GithubException) -> lm_exceptions.LifeMonitorException:
        return lm_exceptions.LifeMonitorException(
            title=github_exc.__class__.__name__,
            status=github_exc.status,
            detail=str(github_exc),
            data=github_exc.data,
            headers=github_exc.headers)

    def check_connection(self) -> bool:
        try:
            # Call the GET /rate_limit API to test the connection. Seems to be the
            # simplest call with a small, constant-size result
            self._gh_service.get_rate_limit()
            logger.debug("GithubTestingService:  check_connection() -> seems ok")
            self._gh_service.get_rate_limit()
            return True
        except GithubException as e:
            logger.info("Caught exception from Github GET /rate_limit: %s.  Connection not working?", e)
            return False

    @cached(timeout=Timeout.NONE, client_scope=False, transactional_update=True)
    def _get_gh_workflow(self, repository, workflow_id) -> Workflow:
        logger.debug("Getting github workflow...")
        return self._gh_service.get_repo(repository).get_workflow(workflow_id)

    @cached(timeout=Timeout.NONE, client_scope=False, transactional_update=True)
    def _get_gh_workflow_from_test_instance_resource(self, test_instance_resource: str) -> Workflow:
        _, repository, workflow_id = self._get_workflow_info(test_instance_resource)
        logger.debug("Getting github workflow --  wf id: %s; repository: %s", workflow_id, repository)

        workflow = self._get_gh_workflow(repository, workflow_id)
        logger.debug("Retrieved workflow %s from github", workflow_id)

        return workflow

    def __get_gh_workflow_runs__(self,
                                 workflow: github.Worflow.Workflow,
                                 branch=github.GithubObject.NotSet,
                                 status=github.GithubObject.NotSet,
                                 created=github.GithubObject.NotSet,
                                 limit: Optional[int] = None) -> CachedPaginatedList:
        """
        Extends `Workflow.get_runs` to support `created` param
        """
        logger.debug("Getting runs of workflow %r ...", workflow)
        branch = branch or github.GithubObject.NotSet
        status = status or github.GithubObject.NotSet
        created = created or github.GithubObject.NotSet
        assert (branch is github.GithubObject.NotSet or isinstance(branch, github.Branch.Branch) or isinstance(branch, str)), branch
        assert status is github.GithubObject.NotSet or isinstance(status, str), status
        url_parameters = dict()
        if branch is not github.GithubObject.NotSet:
            url_parameters["branch"] = (
                branch.name if isinstance(branch, github.Branch.Branch) else branch
            )
        if created is not github.GithubObject.NotSet:
            url_parameters["created"] = created
        if status is not github.GithubObject.NotSet:
            url_parameters["status"] = status
        logger.debug("Getting runs of workflow %r - branch: %r", workflow, branch)
        logger.debug("Getting runs of workflow %r - status: %r", workflow, status)
        logger.debug("Getting runs of workflow %r - created: %r", workflow, created)
        logger.debug("Getting runs of workflow %r - params: %r", workflow, url_parameters)
        # return github.PaginatedList.PaginatedList( # Default pagination class
        return CachedPaginatedList(
            github.WorkflowRun.WorkflowRun,
            workflow._requester,
            f"{workflow.url}/runs",
            url_parameters,
            None,
            transactional_update=True,
            list_item="workflow_runs",
            limit=limit
            # disable force_use_cache: a run might be updated with new attempts even when its status is completed
            # force_use_cache=lambda r: r.status == GithubTestingService.GithubStatus.COMPLETED and r.raw_data['run']
        )

    @cached(timeout=Timeout.NONE, client_scope=False, transactional_update=True,
            force_cache_value=lambda r: r[1]["status"] == GithubTestingService.GithubStatus.COMPLETED)
    def __get_gh_workflow_run_attempt__(self,
                                        workflow_run: github.WorkflowRun.WorkflowRun,
                                        attempt: int):
        url = f"{workflow_run.url}/attempts/{attempt}"
        logger.debug("Attempt URL: %r", url)
        headers, data = workflow_run._requester.requestJsonAndCheck("GET", url)
        return headers, data

    @cached(timeout=Timeout.NONE, client_scope=False, transactional_update=True)
    def __get_gh_workflow_run_attempts__(self,
                                         workflow_run: github.WorkflowRun.WorkflowRun,
                                         limit: Optional[int] = None) -> List[github.WorkflowRun.WorkflowRun]:
        result = []
        i = workflow_run.raw_data['run_attempt']
        while i >= 1:
            headers, data = self.__get_gh_workflow_run_attempt__(workflow_run, i)
            result.append(WorkflowRun(workflow_run._requester, headers, data, True))
            i -= 1
            if limit and len(result) == limit:
                break
        return result

    @cached(timeout=Timeout.NONE, client_scope=False, transactional_update=True)
    def __get_workflow_runs_iterator(self, workflow: Workflow.Workflow, test_instance: models.TestInstance,
                                     limit: Optional[int] = None) -> CachedPaginatedList:
        branch = github.GithubObject.NotSet
        created = github.GithubObject.NotSet
        try:
            branch = test_instance.test_suite.workflow_version.revision.main_ref.shorthand
            assert branch, "Branch cannot be empty"
        except Exception:
            branch = github.GithubObject.NotSet
            logger.debug("No revision associated with workflow version %r", workflow)
            workflow_version = test_instance.test_suite.workflow_version
            logger.debug("Checking Workflow version: %r (previous: %r, next: %r)",
                         workflow_version, workflow_version.previous_version, workflow_version.next_version)
            if workflow_version.previous_version and workflow_version.next_version:
                created = "{}..{}".format(workflow_version.created.isoformat(),
                                          workflow_version.next_version.created.isoformat())
            elif workflow_version.previous_version:
                created = ">={}".format(workflow_version.created.isoformat())
            elif workflow_version.next_version:
                created = "<{}".format(workflow_version.next_version.created.isoformat())
            else:
                logger.debug("No previous version found, then no filter applied... Loading all available builds")
        logger.debug("Fetching runs : %r - %r", branch, created)
        # return list(self.__get_gh_workflow_runs__(workflow, branch=branch, created=created))
        # return list(itertools.islice(self.__get_gh_workflow_runs__(workflow, branch=branch, created=created), limit))
        return self.__get_gh_workflow_runs__(workflow, branch=branch, created=created, limit=limit)

    @cached(timeout=Timeout.NONE, client_scope=False, transactional_update=True)
    def _list_workflow_runs(self, test_instance: models.TestInstance,
                            status: Optional[str] = None, limit: int = 10) -> List[github.WorkflowRun.WorkflowRun]:
        # get gh workflow
        workflow = self._get_gh_workflow_from_test_instance_resource(test_instance.resource)
        logger.debug("Retrieved workflow %s from github", workflow)
        logger.debug("Workflow Runs Limit: %r", limit)
        logger.debug("Workflow Runs Status: %r", status)

        return list(self.__get_workflow_runs_iterator(workflow, test_instance, limit=limit))

    @cached(timeout=Timeout.NONE, client_scope=False, transactional_update=True)
    def _list_workflow_run_attempts(self, test_instance: models.TestInstance,
                                    status: Optional[str] = None, limit: int = 10) -> List[github.WorkflowRun.WorkflowRun]:
        # get gh workflow
        workflow = self._get_gh_workflow_from_test_instance_resource(test_instance.resource)
        logger.debug("Retrieved workflow %s from github", workflow)
        logger.debug("Workflow Runs Limit: %r", limit)
        logger.debug("Workflow Runs Status: %r", status)

        result = []
        for run in self.__get_workflow_runs_iterator(workflow, test_instance):
            logger.debug("Loading Github run ID %r", run.id)
            # The Workflow.get_runs method in the PyGithub API has a status argument
            # which in theory we could use to filter the runs that are retrieved to
            # only the ones with the status that interests us.  This worked in the past,
            # but as of 2021/06/23 the relevant Github API started returning only the
            # latest three matching runs when we specify that argument.
            #
            # To work around the problem, we call `get_runs` with no arguments, thus
            # retrieving all the runs regardless of status, and then we filter below.
            # if status is None or run.status == status:
            logger.debug("Number of attempts of run ID %r: %r", run.id, run.raw_data['run_attempt'])
            if (limit is None or limit > 1) and run.raw_data['run_attempt'] > 1:
                for attempt in self.__get_gh_workflow_run_attempts__(
                        run, limit=(limit - len(result) if limit else None)):
                    logger.debug("Attempt: %r %r %r", attempt, status, attempt.status)
                    if status is None or attempt.status == status:
                        result.append(attempt)
            else:
                if status is None or run.status == status:
                    result.append(run)

        for run in result:
            logger.debug("Run: %r --> %r -- %r", run, run.created_at, run.updated_at)
        return result

    def get_last_test_build(self, test_instance: models.TestInstance) -> Optional[GithubTestBuild]:
        try:
            logger.debug("Getting latest build...")
            for run in self._list_workflow_run_attempts(test_instance, status=self.GithubStatus.COMPLETED):
                return GithubTestBuild(self, test_instance, run)
            logger.debug("Getting latest build... DONE")
            return None
        except GithubRateLimitExceededException as e:
            raise lm_exceptions.RateLimitExceededException(detail=str(e), instance=test_instance)

    def get_last_passed_test_build(self, test_instance: models.TestInstance) -> Optional[GithubTestBuild]:
        try:
            logger.debug("Getting last passed build...")
            for run in self._list_workflow_run_attempts(test_instance, status=self.GithubStatus.COMPLETED):
                if run.conclusion == self.GithubConclusion.SUCCESS:
                    return GithubTestBuild(self, test_instance, run)
            return None
        except GithubRateLimitExceededException as e:
            raise lm_exceptions.RateLimitExceededException(detail=str(e), instance=test_instance)

    def get_last_failed_test_build(self, test_instance: models.TestInstance) -> Optional[GithubTestBuild]:
        try:
            logger.debug("Getting last failed build...")
            for run in self._list_workflow_run_attempts(test_instance, status=self.GithubStatus.COMPLETED):
                if run.conclusion == self.GithubConclusion.FAILURE:
                    return GithubTestBuild(self, test_instance, run)
            return None
        except GithubRateLimitExceededException as e:
            raise lm_exceptions.RateLimitExceededException(detail=str(e), instance=test_instance)

    def get_test_builds(self, test_instance: models.TestInstance, limit=10) -> list:
        try:
            logger.debug("Getting test builds...")
            return [GithubTestBuild(self, test_instance, run)
                    for run in self._list_workflow_run_attempts(test_instance, limit=limit)[:limit]]
        except GithubRateLimitExceededException as e:
            raise lm_exceptions.RateLimitExceededException(detail=str(e), instance=test_instance)

    @cached(timeout=Timeout.NONE, client_scope=False,
            force_cache_value=lambda b: b._metadata.status == GithubTestingService.GithubStatus.COMPLETED)
    def get_test_build(self, test_instance: models.TestInstance, build_number: int) -> GithubTestBuild:
        try:
            # parse build identifier
            run_id, run_attempt = build_number.split('_')
            logger.debug("Searching build: %r %r", run_id, run_attempt)
            # get a reference to the test instance repository
            repo: Repository = self._get_repo(test_instance)
            headers, data = self._get_test_build(run_id, run_attempt, repo)
            return GithubTestBuild(self, test_instance, WorkflowRun(repo._requester, headers, data, True))
        except ValueError as e:
            if logger.isEnabledFor(logging.DEBUG):
                logger.exception(e)
            raise lm_exceptions.BadRequestException(detail="Invalid build identifier")

    @cached(timeout=Timeout.NONE, client_scope=False,
            force_cache_value=lambda b: b[1]['status'] == GithubTestingService.GithubStatus.COMPLETED)
    def _get_test_build(self, run_id, run_attempt, repo: Repository) -> GithubTestBuild:
        try:
            # build url
            url = f"/repos/{repo.full_name}/actions/runs/{run_id}/attempts/{run_attempt}"
            logger.debug("Build URL: %s", url)
            headers, data = repo._requester.requestJsonAndCheck("GET", url)
            return headers, data
        except ValueError as e:
            if logger.isEnabledFor(logging.DEBUG):
                logger.exception(e)
            raise lm_exceptions.BadRequestException(detail="Invalid build identifier")
        except GithubRateLimitExceededException as e:
            raise lm_exceptions.RateLimitExceededException(detail=str(e), run_id=run_id, run_attempt=run_attempt)
        except UnknownObjectException as e:
            raise lm_exceptions.EntityNotFoundException(models.TestBuild, entity_id=f"{run_id}_{run_attempt}", detail=str(e))

    def get_instance_external_link(self, test_instance: models.TestInstance) -> str:
        _, repo_full_name, workflow_id = self._get_workflow_info(test_instance.resource)
        return f'https://github.com/{repo_full_name}/actions/workflows/{workflow_id}'

    def get_test_build_external_link(self, test_build: models.TestBuild) -> str:
        repo = self._get_repo(test_build.test_instance)
        return f'https://github.com/{repo.full_name}/actions/runs/{test_build.build_number}/attempts/{test_build.attempt_number}'

    def get_test_build_output(self, test_instance: models.TestInstance, build_number, offset_bytes=0, limit_bytes=131072):
        raise lm_exceptions.NotImplementedException(detail="not supported for GitHub test builds")

    def start_test_build(self, test_instance: models.TestInstance, build_number: int = None) -> bool:
        try:
            last_build = self.get_last_test_build(test_instance) \
                if build_number is None else self.get_test_build(test_instance, build_number)
            assert last_build
            if last_build:
                run: WorkflowRun = last_build._metadata
                assert isinstance(run, WorkflowRun)
                return run.rerun()
            else:
                workflow = self._get_gh_workflow_from_test_instance_resource(test_instance.resource)
                assert isinstance(workflow, Workflow), workflow
                return workflow.create_dispatch(test_instance.test_suite.workflow_version.version)
        except Exception as e:
            if logger.isEnabledFor(logging.DEBUG):
                logger.exception(e)
        return False

    @classmethod
    def _parse_workflow_url(cls, resource: str) -> Tuple[str, str, str]:
        """
        Utility method to parse github workflow URIs.  Given a URL to the testing
        Github Workflow, returns a tuple (server, repository, workflow_id).

        The `resource` can be a full url to a Github workflow; e.g.,

             https://api.github.com/repos/crs4/life_monitor/actions/workflows/4094661

        Alternatively, `resource` can forego the server part (e.g., `https://api.github.com`)
        and even the leading root slash of the path part.  For instance, `resource` can be:

             repos/crs4/life_monitor/actions/workflows/4094661

        In the latter case, the return value for server will be an empty string.
        """
        try:
            result = urlparse(resource)
            if result.scheme and result.netloc:
                server = f"{result.scheme}://{result.netloc}"
            else:
                server = ""
            m = cls._RESOURCE_PATTERN.match(result.path)
            if not m:
                raise RuntimeError("Malformed GitHub workflow path. Expected: 'repos/{owner}/{reponame}/actions/workflows/{workflow_id}'")
            repository = f'{m.group("owner")}/{m.group("repo")}'
            workflow_id = m.group("wf")
            logger.debug("parse result -- server: '%s'; repository: '%s'; workflow_id: '%s'", server, repository, workflow_id)
            return server, repository, workflow_id
        except URLError as e:
            raise lm_exceptions.SpecificationNotValidException(
                detail="Invalid link to Github Workflow",
                original_exception=str(e))
        except RuntimeError as e:
            raise lm_exceptions.SpecificationNotValidException(
                detail="Unexpected format of link to Github Workflow",
                parse_error=e.args[0])


class GithubTestBuild(models.TestBuild):
    def __init__(self,
                 testing_service: models.TestingService,
                 test_instance: models.TestInstance,
                 metadata: github.WorkflowRun.WorkflowRun) -> None:
        super().__init__(testing_service, test_instance, metadata)

    @property
    def id(self) -> str:
        return f"{self._metadata.id}_{self.attempt_number}"

    @property
    def build_number(self) -> int:
        return self._metadata.id

    @property
    def attempt_number(self) -> int:
        return self._metadata.raw_data['run_attempt']

    @property
    def duration(self) -> int:
        return int((self._metadata.updated_at - self._metadata.created_at).total_seconds())

    def is_running(self) -> bool:
        return self._metadata.status == GithubTestingService.GithubStatus.IN_PROGRESS

    @property
    def metadata(self):
        # Rather than expose the PyGithub object outside this class, we expose
        # the raw metadata from Github
        return self._metadata.raw_data

    @property
    def result(self) -> models.TestBuild.Result:
        if self._metadata.status == GithubTestingService.GithubStatus.COMPLETED:
            if self._metadata.conclusion == GithubTestingService.GithubConclusion.SUCCESS:
                return models.TestBuild.Result.SUCCESS
            return models.TestBuild.Result.FAILED
        return None

    @property
    def revision(self):
        return self._metadata.head_sha

    @property
    def status(self) -> str:
        if self._metadata.status == GithubTestingService.GithubStatus.IN_PROGRESS:
            return models.BuildStatus.RUNNING
        if self._metadata.status == GithubTestingService.GithubStatus.QUEUED:
            return models.BuildStatus.WAITING
        if self._metadata.status != GithubTestingService.GithubStatus.COMPLETED:
            logger.error("Unexpected run status value '%s'!!", self._metadata.status)
            # Try to keep going notwithstanding the unexpected status
        if self._metadata.conclusion == GithubTestingService.GithubConclusion.SUCCESS:
            return models.BuildStatus.PASSED
        if self._metadata.conclusion == GithubTestingService.GithubConclusion.CANCELLED:
            return models.BuildStatus.ABORTED
        if self._metadata.conclusion == GithubTestingService.GithubConclusion.FAILURE:
            return models.BuildStatus.FAILED
        return models.BuildStatus.ERROR

    @property
    def timestamp(self) -> int:
        return int(self._metadata.created_at.timestamp())

    @property
    def created_at(self) -> int:
        return self._metadata.created_at

    @property
    def updated_at(self) -> int:
        return self._metadata.updated_at

    @property
    def url(self) -> str:
        return f"{self._metadata.url}/attempts/{self.attempt_number}"
