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
from typing import Optional

import jenkins
import lifemonitor.api.models as models
import lifemonitor.exceptions as lm_exceptions
from lifemonitor.lang import messages

from .service import TestingService

# set module level logger
logger = logging.getLogger(__name__)


class JenkinsTestingService(TestingService):
    _server = None
    _job_name = None
    __mapper_args__ = {
        'polymorphic_identity': 'jenkins_testing_service'
    }

    def __init__(self, url: str, token: models.TestingServiceToken = None) -> None:
        super().__init__(url, token)
        try:
            self._server = jenkins.Jenkins(self.url)
        except Exception as e:
            raise lm_exceptions.TestingServiceException(e)

    def check_connection(self) -> bool:
        try:
            assert '_class' in self.server.get_info()
        except Exception as e:
            raise lm_exceptions.TestingServiceException(detail=str(e))

    @property
    def server(self) -> jenkins.Jenkins:
        if not self._server:
            self._server = jenkins.Jenkins(self.url)
        return self._server

    @staticmethod
    def get_job_name(resource):
        # extract the job name from the resource path
        logger.debug(f"Getting project metadata - resource: {resource}")
        job_name = re.sub("(?s:.*)/", "", resource.strip('/'))
        logger.debug(f"The job name: {job_name}")
        if not job_name or len(job_name) == 0:
            raise lm_exceptions.TestingServiceException(
                f"Unable to get the Jenkins job from the resource {job_name}")
        return job_name

    def get_last_test_build(self, test_instance: models.TestInstance) -> Optional[JenkinsTestBuild]:
        metadata = self.get_project_metadata(test_instance)
        if 'lastBuild' in metadata and metadata['lastBuild']:
            return self.get_test_build(test_instance, metadata['lastBuild']['number'])
        return None

    def get_last_passed_test_build(self, test_instance: models.TestInstance) -> Optional[JenkinsTestBuild]:
        metadata = self.get_project_metadata(test_instance)
        if 'lastSuccessfulBuild' in metadata and metadata['lastSuccessfulBuild']:
            return self.get_test_build(test_instance, metadata['lastSuccessfulBuild']['number'])
        return None

    def get_last_failed_test_build(self, test_instance: models.TestInstance) -> Optional[JenkinsTestBuild]:
        metadata = self.get_project_metadata(test_instance)
        if 'lastFailedBuild' in metadata and metadata['lastFailedBuild']:
            return self.get_test_build(metadata['lastFailedBuild']['number'])
        return None

    def test_builds(self, test_instance: models.TestInstance) -> list:
        builds = []
        metadata = self.get_project_metadata(test_instance)
        for build_info in metadata['builds']:
            builds.append(self.get_test_build(test_instance, build_info['number']))
        return builds

    def get_project_metadata(self, test_instance: models.TestInstance, fetch_all_builds=False):
        if not hasattr(test_instance, "_raw_metadata") or test_instance._raw_metadata is None:
            try:
                test_instance._raw_metadata = self.server.get_job_info(
                    self.get_job_name(test_instance.resource), fetch_all_builds=fetch_all_builds)
            except jenkins.JenkinsException as e:
                raise lm_exceptions.TestingServiceException(f"{self}: {e}")
        return test_instance._raw_metadata

    def get_test_builds(self, test_instance: models.TestInstance, limit=10):
        builds = []
        project_metadata = self.get_project_metadata(test_instance, fetch_all_builds=True if limit > 100 else False)
        for build_info in project_metadata['builds']:
            if len(builds) == limit:
                break
            builds.append(self.get_test_build(test_instance, build_info['number']))
        return builds

    def get_test_build(self, test_instance: models.TestInstance, build_number: int) -> JenkinsTestBuild:
        try:
            build_metadata = self.server.get_build_info(self.get_job_name(test_instance.resource), int(build_number))
            return JenkinsTestBuild(self, test_instance, build_metadata)
        except jenkins.NotFoundException as e:
            raise lm_exceptions.EntityNotFoundException(models.TestBuild, entity_id=build_number, detail=str(e))
        except jenkins.JenkinsException as e:
            raise lm_exceptions.TestingServiceException(e)

    def get_test_build_output(self, test_instance: models.TestInstance, build_number, offset_bytes=0, limit_bytes=131072):
        try:
            logger.debug("test_instance '%r', build_number '%r'", test_instance.name, build_number)
            logger.debug("query param: offset=%r, limit=%r", offset_bytes, limit_bytes)

            if not isinstance(offset_bytes, int) or offset_bytes < 0:
                raise ValueError(messages.invalid_log_offset)
            if not isinstance(limit_bytes, int) or limit_bytes < 0:
                raise ValueError(messages.invalid_log_limit)

            output = self.server.get_build_console_output(self.get_job_name(test_instance.resource), build_number)
            if len(output) < offset_bytes:
                raise ValueError(messages.invalid_log_offset)

            return output[offset_bytes:(offset_bytes + len(output) if limit_bytes == 0 else limit_bytes)]

        except jenkins.JenkinsException as e:
            raise lm_exceptions.TestingServiceException(e)


class JenkinsTestBuild(models.TestBuild):

    @property
    def id(self) -> str:
        return self.metadata['number']

    @property
    def build_number(self) -> int:
        return self.metadata['number']

    def is_running(self) -> bool:
        return self.metadata['building'] is True

    @property
    def status(self) -> str:
        if self.is_running():
            return models.BuildStatus.RUNNING
        if self.metadata['result']:
            if self.metadata['result'] == 'SUCCESS':
                return models.BuildStatus.PASSED
            elif self.metadata['result'] == 'ABORTED':
                return models.BuildStatus.ABORTED
            elif self.metadata['result'] == 'FAILURE':
                return models.BuildStatus.FAILED
        return models.BuildStatus.ERROR

    @property
    def revision(self):
        rev_info = list(map(lambda x: x["lastBuiltRevision"],
                            filter(lambda x: "lastBuiltRevision" in x, self.metadata["actions"])))
        return rev_info[0] if len(rev_info) == 1 else None

    @property
    def timestamp(self) -> int:
        return self.metadata['timestamp']

    @property
    def duration(self) -> int:
        return self.metadata['duration']

    @property
    def result(self) -> models.TestBuild.Result:
        return models.TestBuild.Result.SUCCESS \
            if self.metadata["result"] == "SUCCESS" else models.TestBuild.Result.FAILED

    @property
    def url(self) -> str:
        return self.metadata['url']
