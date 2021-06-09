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

import itertools as it
import logging
from typing import Generator, Optional, Tuple
from urllib.parse import urlparse
from urllib.error import URLError

import github
from github import Github, GithubException

import lifemonitor.api.models as models
import lifemonitor.exceptions as lm_exceptions

from .service import TestingService

# set module level logger
logger = logging.getLogger()


class GithubTestingService(TestingService):
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
        logger.debug("url: %s; token: %s\nClient configuration: %s",
                     url, token, self._configuration_)
        try:
            self._gh_obj = Github(base_url=url, **self._configuration_)
            logger.debug("Github client created.")
        except Exception as e:
            raise lm_exceptions.TestingServiceException(e)

    @property
    def _gh_service(self) -> Github:
        logger.debug("Github client requested.")
        if not self._gh_obj:
            logger.debug("Instantiating with: url %s; token: %s\nClient configuration: %s",
                         self.url, None, self._configuration_)
            self._gh_obj = Github(base_url=self.url, **self._configuration_)
            logger.debug("Github client created.")
        return self._gh_obj

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

    def _iter_runs(self, test_instance: models.TestInstance, status: str = None) -> Generator[github.WorkflowRun.WorkflowRun]:
        _, repository, workflow_id = self._parse_workflow_url(test_instance.resource)
        logger.debug("iterating over runs --  wf id: %s; repository: %s; status: %s", workflow_id, repository, status)

        status_arg = status if status else github.GithubObject.NotSet
        workflow = self._gh_service.get_repo(repository).get_workflow(workflow_id)
        logger.debug("Retrieved workflow %s from github", workflow_id)
        for run in workflow.get_runs(status=status_arg):
            yield run

    def get_last_test_build(self, test_instance: models.TestInstance) -> Optional[GithubTestBuild]:
        for run in self._iter_runs(test_instance, status=self.GithubStatus.COMPLETED):
            return GithubTestBuild(self, test_instance, run)
        return None

    def get_last_passed_test_build(self, test_instance: models.TestInstance) -> Optional[GithubTestBuild]:
        for run in self._iter_runs(test_instance, status=self.GithubStatus.COMPLETED):
            if run.conclusion == self.GithubConclusion.SUCCESS:
                return GithubTestBuild(self, test_instance, run)
        return None

    def get_last_failed_test_build(self, test_instance: models.TestInstance) -> Optional[GithubTestBuild]:
        for run in self._iter_runs(test_instance, status=self.GithubStatus.COMPLETED):
            if run.conclusion == self.GithubConclusion.FAILURE:
                return GithubTestBuild(self, test_instance, run)
        return None

    def get_test_builds(self, test_instance: models.TestInstance, limit=10) -> list:
        return list(GithubTestBuild(self, test_instance, run)
                    for run in it.islice(self._iter_runs(test_instance), limit))

    def get_test_build(self, test_instance: models.TestInstance, build_number: int) -> GithubTestBuild:
        logger.debug("Inefficient get_test_build implementation.  Rewrite me!")
        # TODO:  We search through the runs of the workflow because there's no
        # obvious way to istantiate a PyGithub WorkflowRun object given a build
        # number -- but there's has to be a way.  We can easily asseble the URL
        # of the request to directly retrive the data we need here.
        assert isinstance(build_number, int)
        for run in self._iter_runs(test_instance):
            if run.id == build_number:
                return GithubTestBuild(self, test_instance, run)
        raise lm_exceptions.EntityNotFoundException(models.TestBuild, entity_id=build_number)

    def _parse_workflow_url(self, resource: str) -> Tuple[str, str, str]:
        """
        Given a URL to the testing Github Worklflow, returns a tuple
        (server, repository, workflow_id)
        """
        # URL identifies a Github Workflow and should have the form:
        #   https://api.github.com/repos/crs4/life_monitor/actions/workflows/4094661
        expected_url_msg = " Expected '/repos/{org}/{reponame}/actions/workflows/{workflow_id}'"
        try:
            logger.debug("Parsing testing instance resource URL '%s'", resource)
            result = urlparse(resource)
            server = f"{result.scheme}://{result.netloc}"
            # simply split the path using the / delimiter.  We'll later access the parts by index
            parts = result.path.split('/')
            # Validate our assumptions
            if len(parts) != 7:
                raise RuntimeError("Unexpected number of parts in URL to Github Workflow." + expected_url_msg)
            if parts[1] != 'repos':
                raise RuntimeError("Missing or misplaced /repos in URL to Github Workflow." + expected_url_msg)
            if parts[4] != 'actions' or parts[5] != 'workflows':
                raise RuntimeError("Missing or misplaced /actions/workflows in URL to Github Workflow." + expected_url_msg)
            # Extract info
            repository = '/'.join(parts[2:4])
            workflow_id = parts[6]
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
        return str(self._metadata.id)

    @property
    def build_number(self) -> int:
        return self._metadata.id

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
        return int(self._metadata.updated_at.timestamp())

    @property
    def url(self) -> str:
        return self._metadata.url
