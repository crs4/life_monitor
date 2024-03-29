# Copyright (c) 2020-2024 CRS4
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

import lifemonitor.api.models as models
import requests
from lifemonitor.api.models.services.service import TestingService
from lifemonitor.cache import Timeout, cached
from lifemonitor.exceptions import (EntityNotFoundException,
                                    TestingServiceException)

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

    __dot_com = {'site': "https://travis-ci.com", 'api': "https://api.travis-ci.com"}
    __dot_org = {'site': "https://travis-ci.org", 'api': 'https://api.travis-ci.org'}

    # define the token type
    token_type = 'token'

    def initialize(self):
        pass

    @property
    def base_url(self):
        if '.org' in self.url:
            return self.__dot_org['site']
        elif '.com' in self.url:
            return self.__dot_com['site']
        else:
            raise ValueError("Invalid Service URL")

    @property
    def api_base_url(self):
        if '.org' in self.url:
            return self.__dot_org['api']
        elif '.com' in self.url:
            return self.__dot_com['api']
        else:
            raise ValueError("Invalid Service URL")

    def _build_headers(self, token: models.TestingServiceToken = None):
        headers = self.__headers__.copy()
        token = token if token else self.token
        if token:
            headers['Authorization'] = f'{token.type} {token.value}'
        return headers

    def _build_url(self, path, params=None):
        query = "?" + urllib.parse.urlencode(params) if params else ""
        return urllib.parse.urljoin(self.api_base_url, path + query)

    def _get(self, path, token: models.TestingServiceToken = None, params=None) -> object:
        logger.debug("Getting resource: %r", self._build_url(path, params))
        response = requests.get(self._build_url(path, params), headers=self._build_headers(token))
        return response.json() if response.status_code == 200 else response

    @staticmethod
    def get_repo_id(test_instance: models.TestInstance, quote=True):
        # extract the job name from the resource path
        logger.debug(f"Getting project metadata - resource: {test_instance.resource}")
        repo = re.sub(r'^(/)?(repo/)?(github/)?(.+)', r'\4', test_instance.resource.strip('/(build(s)?)?'))
        repo_id = urllib.parse.quote(repo, safe='') if quote else repo
        logger.debug(f"The repo ID: {repo_id}")
        if not repo_id or len(repo_id) == 0:
            raise TestingServiceException(
                f"Unable to get the Travis job from the resource {test_instance.resource}")
        return repo_id

    def get_repo_slug(self, test_instance: models.TestInstance):
        metadata = self.get_project_metadata(test_instance)
        return metadata['slug']

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

    @cached(timeout=Timeout.NONE, client_scope=False, transactional_update=True)
    def get_project_metadata(self, test_instance: models.TestInstance):
        try:
            logger.debug("Getting Travis project metadata...")
            return self._get("/repo/{}".format(self.get_repo_id(test_instance)))
        except Exception as e:
            raise TestingServiceException(f"{self}: {e}")

    def get_test_builds(self, test_instance: models.TestInstance, limit=10) -> list:
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

    def _get_test_build(self, test_instance: models.TestInstance, build_number: int) -> models.TravisTestBuild:
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

    def _disable_build_cache(func, obj: TravisTestingService,
                             test_instance: models.TestInstance, build_number: int,
                             *args, **kwargs):
        build = obj._get_test_build(test_instance, build_number)
        return build.is_running()

    def get_test_build(self, test_instance: models.TestInstance, build_number: int) -> models.TravisTestBuild:
        return self._get_test_build(test_instance, build_number)

    def get_instance_external_link(self, test_instance: models.TestInstance) -> str:
        testing_service = test_instance.testing_service
        repo_slug = testing_service.get_repo_slug(test_instance)
        return urllib.parse.urljoin(testing_service.base_url, f'{repo_slug}/builds')

    def get_test_build_external_link(self, test_build: models.TestBuild) -> str:
        testing_service = test_build.test_instance.testing_service
        repo_slug = testing_service.get_repo_slug(test_build.test_instance)
        return urllib.parse.urljoin(testing_service.base_url, f'{repo_slug}/builds/{test_build.id}')

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
