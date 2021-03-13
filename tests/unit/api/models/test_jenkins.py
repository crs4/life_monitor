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

import pytest
import logging
from unittest.mock import patch, MagicMock, PropertyMock
import lifemonitor.api.models as models
from tests.conftest_helpers import get_random_slice_indexes


logger = logging.getLogger(__name__)


@pytest.fixture
def jenkins_url():
    return 'http://jenkins:8080'


@pytest.fixture
def jenkins_job():
    return 'test'


@pytest.fixture
def jenkins_resource(jenkins_job):
    return 'job/{}'.format(jenkins_job)


@pytest.fixture
def test_instance(jenkins_resource):
    instance = MagicMock()
    instance.resource = jenkins_resource
    instance._raw_metadata = None
    return instance


@pytest.fixture
def jenkins_service(jenkins_url) -> models.JenkinsTestingService:
    return models.JenkinsTestingService(jenkins_url)


@pytest.fixture
def jenkins_job_info(jenkins_service, test_instance):
    return jenkins_service.get_project_metadata(test_instance)


def test_connection(jenkins_service):
    logger.info(jenkins_service.server.get_info())


def test_job_name(jenkins_service, jenkins_resource, jenkins_job):
    assert jenkins_service.get_job_name(jenkins_resource) == jenkins_job, "Unexpected job name"


def test_project_metadata_cache(jenkins_url, test_instance):
    raw_data = "obj"
    with patch("lifemonitor.api.models.JenkinsTestingService.server", new_callable=PropertyMock) as server_property:
        server = MagicMock()
        server.get_job_info.return_value = raw_data
        server_property.return_value = server
        jenkins_service = models.JenkinsTestingService(jenkins_url)
        metadata = jenkins_service.get_project_metadata(test_instance)
        server.get_job_info.assert_called_once()
        assert metadata == raw_data, "Unexpected retrieved metadata"
        metadata = jenkins_service.get_project_metadata(test_instance)
        assert server.get_job_info.call_count == 1, "The cache should be used"
        assert metadata == raw_data, "Unexpected retrieved metadata"


def test_project_metadata(jenkins_service, jenkins_job, test_instance):
    jenkins_job_info = jenkins_service.get_project_metadata(test_instance)
    assert 'name' in jenkins_job_info, "Unable to find job name on project metadata"
    assert jenkins_job_info['name'] == jenkins_job, "Unexpected job name"
    assert 'builds' in jenkins_job_info, "Unable to find build info related with the {}".format(jenkins_job)


def test_latest_builds(jenkins_service, test_instance):
    builds = jenkins_service.get_test_builds(test_instance)
    logger.info(builds)
    last_build = builds[0]  # builds are always ordered from the latest executed
    build = jenkins_service.get_last_test_build(test_instance)
    logger.debug("First build from the build list: %r", last_build.id)
    logger.debug("ID of the lastest build: %r", build.id)
    assert last_build.id == build.id, "Invalid build ID"


def test_get_last_failed_test_build(jenkins_service, test_instance):
    # search the last failed build
    builds = jenkins_service.get_test_builds(test_instance, limit=1000)
    found_failed_build = None
    for b in builds:
        logger.debug("Checking %r: status -> %r", b.id, b.status)
        if b.status == models.BuildStatus.FAILED:
            found_failed_build = b
            break
    logger.debug("Found build: %r", found_failed_build)
    assert found_failed_build is None, "All builds should be passed"


def test_get_last_passed_test_build(jenkins_service, test_instance):
    # search the last failed build
    builds = jenkins_service.get_test_builds(test_instance, limit=1000)
    found_failed_build = None
    for b in builds:
        logger.debug("Checking %r: status -> %r", b.id, b.status)
        if b.status == models.BuildStatus.PASSED:
            found_failed_build = b
            break
    logger.debug("Found build: %r", found_failed_build)
    assert found_failed_build, "Unable to find the latest failed build"
    build = jenkins_service.get_last_passed_test_build(test_instance)
    logger.debug("Latest passed build: %r", build)
    assert build, "Unable to get the latest failed build"
    # check if the two builds are equal or not
    assert found_failed_build.id == build.id, "Invalid build ID"


def test_get_last_logs(jenkins_service: models.JenkinsTestingService, test_instance):
    # search the last failed build
    builds = jenkins_service.get_test_builds(test_instance, limit=1000)
    assert len(builds) > 0, "Unexpected number of builds"
    build = builds[-1]
    logger.debug("The last build: %r", build)

    # get all the output
    output = build.output
    logger.debug("output length: %r", len(output))
    assert build.get_output(offset_bytes=0, limit_bytes=0) == output, "Unexpected output"

    # test pagination
    slices = get_random_slice_indexes(3, len(output))
    logger.debug("Slice indexes: %r", slices)
    for s in slices:
        logger.debug("Checking slice: %r", s)
        sout = build.get_output(offset_bytes=s[0], limit_bytes=s[1])
        limit_bytes = s[1] if s[1] else (len(output))
        assert len(sout) == limit_bytes - s[0], "Unexpected output length"
        assert output[s[0]:limit_bytes] == sout, "The actual output slice if different from the expected"
