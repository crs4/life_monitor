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

import datetime
import logging
import re
import urllib
from typing import Optional

import requests

import lifemonitor.api.models as models
from lifemonitor.exceptions import EntityNotFoundException, TestingServiceException

from .service import TestingService

# set module level logger
logger = logging.getLogger(__name__)


class TravisTestingService(TestingService):
    _server = None
    _job_name = None
    __mapper_args__ = {
        'polymorphic_identity': 'travis_testing_service'
    }
    __headers__ = {
        'Travis-API-Version': '3'
    }

    __dot_com = 'https://api.travis-ci.com'
    __dot_org = 'https://api.travis-ci.org'

    @property
    def api_base_url(self):
        if self.url == 'https://travis-ci.org':
            return self.__dot_org
        elif self.url == 'https://travis-ci.com':
            return self.__dot_com
        if self.url not in [self.__dot_com, self.__dot_org]:
            raise ValueError("Invalid API url")
        return self.url

    def _build_headers(self, token: models.TestingServiceToken = None):
        headers = self.__headers__.copy()
        token = token if token else self.token
        if token:
            headers['Authorization'] = 'token {}'.format(token.secret)
        return headers

    def _build_url(self, path, params=None):
        query = "?" + urllib.parse.urlencode(params) if params else ""
        return urllib.parse.urljoin(self.api_base_url, path + query)

    def _get(self, path, token: models.TestingServiceToken = None, params=None) -> object:
        logger.debug("Getting resource: %r", self._build_url(path, params))
        response = requests.get(self._build_url(path, params), headers=self._build_headers(token))
        return response.json() if response.status_code == 200 else response

    @staticmethod
    def get_repo_id(test_instance: models.TestInstance):
        # extract the job name from the resource path
        logger.debug(f"Getting project metadata - resource: {test_instance.resource}")
        repo = re.sub(r'^(/)?(repo/)?(github/)?(.+)', r'\4', test_instance.resource.strip('/(build(s)?)?'))
        repo_slug = urllib.parse.quote(repo, safe='')
        logger.debug(f"The repo ID: {repo_slug}")
        if not repo_slug or len(repo_slug) == 0:
            raise TestingServiceException(
                f"Unable to get the Travis job from the resource {test_instance.resource}")
        return repo_slug

    def is_workflow_healthy(self, test_instance: models.TestInstance) -> bool:
        return self.get_last_test_build(test_instance).is_successful()

    def _get_last_test_build(self, test_instance: models.TestInstance, state=None) -> Optional[models.TravisTestBuild]:
        try:
            repo_id = self.get_repo_id(test_instance)
            params = {'limit': 1, 'sort_by': 'number:desc'}
            if state:
                params['state'] = state
            response = self._get("/repo/{}/builds".format(repo_id), params=params)
            if isinstance(response, requests.Response):
                if response.status_code == 404:
                    raise EntityNotFoundException(models.TestBuild)
                else:
                    raise TestingServiceException(status=response.status_code,
                                                  detail=str(response.content))
            if 'builds' not in response or len(response['builds']) == 0:
                raise EntityNotFoundException(models.TestBuild)
            return models.TravisTestBuild(self, test_instance, response['builds'][0])
        except Exception as e:
            raise TestingServiceException(e)

    def get_last_test_build(self, test_instance: models.TestInstance) -> Optional[models.TravisTestBuild]:
        return self._get_last_test_build(test_instance)

    def get_last_passed_test_build(self, test_instance: models.TestInstance) -> Optional[models.TravisTestBuild]:
        return self._get_last_test_build(test_instance, state='passed')

    def get_last_failed_test_build(self, test_instance: models.TestInstance) -> Optional[models.TravisTestBuild]:
        return self._get_last_test_build(test_instance, state='failed')

    def get_project_metadata(self, test_instance: models.TestInstance):
        try:
            return self._get("/repo/{}".format(self.get_repo_id(test_instance)))
        except Exception as e:
            raise TestingServiceException(f"{self}: {e}")

    def get_test_builds(self, test_instance: models.TestInstance, limit=10):
        try:
            repo_id = self.get_repo_id(test_instance)
            response = self._get("/repo/{}/builds".format(repo_id), params={'limit': limit})
        except Exception as e:
            raise TestingServiceException(details=f"{e}")
        if isinstance(response, requests.Response):
            logger.debug(response)
            raise TestingServiceException(status=response.status_code,
                                          detail=str(response.content))
        try:
            builds = []
            for build_info in response['builds']:
                builds.append(models.TravisTestBuild(self, test_instance, build_info))
            return builds
        except Exception as e:
            raise TestingServiceException(details=f"{e}")

    def get_test_build(self, test_instance: models.TestInstance, build_number: int) -> models.TravisTestBuild:
        try:
            response = self._get("/build/{}".format(build_number))
        except Exception as e:
            raise TestingServiceException(details=f"{e}")
        if isinstance(response, requests.Response):
            if response.status_code == 404:
                raise EntityNotFoundException(models.TestBuild, entity_id=build_number)
            else:
                raise TestingServiceException(status=response.status_code,
                                              detail=str(response.content))
        return models.TravisTestBuild(self, test_instance, response)

    def get_test_build_output(self, test_instance: models.TestInstance, build_number, offset_bytes=0, limit_bytes=131072):
        try:
            _metadata = self._get(f"/build/{build_number}/jobs")
        except Exception as e:
            raise TestingServiceException(details=f"{e}")

        logger.debug("test_instance '%r', build_number '%r'", test_instance.name, build_number)
        logger.debug("query param: offset=%r, limit=%r", offset_bytes, limit_bytes)

        if isinstance(_metadata, requests.Response):
            if _metadata.status_code == 404:
                raise EntityNotFoundException(models.TestBuild, entity_id=build_number)
            else:
                raise TestingServiceException(status=_metadata.status_code,
                                              detail=str(_metadata.content))
        try:
            logger.debug("Number of jobs (test_instance '%r', build_number '%r'): %r", test_instance.name, build_number, len(_metadata['jobs']))
            if 'jobs' not in _metadata or len(_metadata['jobs']) == 0:
                logger.debug("Ops... no job found")
                return ""

            offset = 0
            output = ""
            current_job_index = 0
            while current_job_index < len(_metadata['jobs']) and \
                    (offset <= offset_bytes or limit_bytes == 0 or len(output) < limit_bytes):
                url = "/job/{}/log".format(_metadata['jobs'][current_job_index]['id'])
                logger.debug("URL: %r", url)
                response = self._get(url)
                if isinstance(response, requests.Response):
                    if response.status_code == 404:
                        raise EntityNotFoundException(models.TestBuild, entity_id=build_number)
                    else:
                        raise TestingServiceException(status=response.status_code,
                                                      detail=str(response.content))
                job_output = response['content']
                if job_output:
                    logger.debug("Job output length: %r", len(job_output))
                    output += job_output
                    offset += len(job_output)
                current_job_index += 1
            # filter output
            return output[offset_bytes:(offset_bytes + len(output) if limit_bytes == 0 else limit_bytes)]
        except Exception as e:
            logger.exception(e)
            raise TestingServiceException(details=f"{e}")


class TravisTestBuild(models.TestBuild):

    @property
    def id(self) -> str:
        return str(self.metadata['id'])

    @property
    def build_number(self) -> int:
        return self.metadata['number']

    def is_running(self) -> bool:
        return len(self.metadata['finished_at']) == 0

    @property
    def status(self) -> str:
        if self.is_running():
            return models.BuildStatus.RUNNING
        if self.metadata['state'] == 'passed':
            return models.BuildStatus.PASSED
        elif self.metadata['state'] == 'canceled':
            return models.BuildStatus.ABORTED
        elif self.metadata['state'] == 'failed':
            return models.BuildStatus.FAILED
        return models.BuildStatus.ERROR

    @property
    def revision(self):
        return self.metadata['commit']

    @property
    def timestamp(self) -> int:
        return datetime.datetime.strptime(
            self.metadata["started_at"], "%Y-%m-%dT%H:%M:%SZ").timestamp()

    @property
    def duration(self) -> int:
        return self.metadata['duration']

    @property
    def result(self) -> models.TestBuild.Result:
        return models.TestBuild.Result.SUCCESS \
            if self.metadata["state"] == "passed" else models.TestBuild.Result.FAILED

    @property
    def url(self) -> str:
        return "{}{}".format(self.testing_service.url, self.metadata['@href'])
