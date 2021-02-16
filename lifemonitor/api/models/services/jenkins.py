
from __future__ import annotations

import logging
import re
from typing import Optional

import jenkins
import lifemonitor.api.models as models
from lifemonitor.common import EntityNotFoundException, TestingServiceException
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
            raise TestingServiceException(e)

    def check_connection(self) -> bool:
        try:
            assert '_class' in self.server.get_info()
        except Exception as e:
            raise TestingServiceException(detail=str(e))

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
            raise TestingServiceException(
                f"Unable to get the Jenkins job from the resource {job_name}")
        return job_name

    def is_workflow_healthy(self, test_instance: models.TestInstance) -> bool:
        return self.get_last_test_build(test_instance).is_successful()

    def get_last_test_build(self, test_instance: models.TestInstance) -> Optional[models.JenkinsTestBuild]:
        metadata = self.get_project_metadata(test_instance)
        if 'lastBuild' in metadata and metadata['lastBuild']:
            return self.get_test_build(test_instance, metadata['lastBuild']['number'])
        return None

    def get_last_passed_test_build(self, test_instance: models.TestInstance) -> Optional[models.JenkinsTestBuild]:
        metadata = self.get_project_metadata(test_instance)
        if 'lastSuccessfulBuild' in metadata and metadata['lastSuccessfulBuild']:
            return self.get_test_build(test_instance, metadata['lastSuccessfulBuild']['number'])
        return None

    def get_last_failed_test_build(self, test_instance: models.TestInstance) -> Optional[models.JenkinsTestBuild]:
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
                raise TestingServiceException(f"{self}: {e}")
        return test_instance._raw_metadata

    def get_test_builds(self, test_instance: models.TestInstance, limit=10):
        builds = []
        project_metadata = self.get_project_metadata(test_instance, fetch_all_builds=True if limit > 100 else False)
        for build_info in project_metadata['builds']:
            if len(builds) == limit:
                break
            builds.append(self.get_test_build(test_instance, build_info['number']))
        return builds

    def get_test_build(self, test_instance: models.TestInstance, build_number: int) -> models.JenkinsTestBuild:
        try:
            build_metadata = self.server.get_build_info(self.get_job_name(test_instance.resource), int(build_number))
            return models.JenkinsTestBuild(self, test_instance, build_metadata)
        except jenkins.NotFoundException as e:
            raise EntityNotFoundException(models.TestBuild, entity_id=build_number, detail=str(e))
        except jenkins.JenkinsException as e:
            raise TestingServiceException(e)

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
            raise TestingServiceException(e)
