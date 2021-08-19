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

import logging
from unittest.mock import MagicMock

import lifemonitor.api.models as models
import pytest
import requests
import urllib
from tests.conftest_helpers import get_random_slice_indexes, get_travis_token

logger = logging.getLogger(__name__)

# global token to test Travis API
token = get_travis_token()


@pytest.fixture
def travis_url():
    return 'https://travis-ci.org'


@pytest.fixture
def travis_api_url():
    return 'https://api.travis-ci.org'


@pytest.fixture
def travis_token():
    return models.TestingServiceToken("token", token) if token else False


@pytest.fixture
def travis_job():
    return '1002447'


@pytest.fixture
def travis_resource(travis_job):
    return '/repo/{}'.format(travis_job)


@pytest.fixture
def test_instance(travis_resource):
    instance = MagicMock()
    instance.resource = travis_resource
    return instance


@pytest.fixture
def travis_service(travis_url, travis_token) -> models.TravisTestingService:
    return models.TravisTestingService(travis_url, travis_token)


@pytest.fixture
def travis_job_info(travis_service, test_instance):
    return travis_service.get_project_metadata(test_instance)


def test_slug_repo_name(travis_service: models.TravisTestingService):
    slug_repo_name = "owner/repo"
    slug_repo_safe = urllib.parse.quote(slug_repo_name, safe='')
    test_instance = MagicMock()
    for repo in (f'/{slug_repo_name}', f'/github/{slug_repo_name}',
                 f'/{slug_repo_name}/', f'/{slug_repo_name}/build', f'/{slug_repo_name}/builds'):
        test_instance.resource = f'/{repo}'
        assert travis_service.get_repo_id(test_instance) == slug_repo_safe, "Unexpected slug repo name"


def test_repo_id(travis_service: models.TravisTestingService):
    slug_repo_name = "12345"
    slug_repo_safe = urllib.parse.quote(slug_repo_name, safe='')
    test_instance = MagicMock()
    for repo in (f'/{slug_repo_name}', f'/repo/{slug_repo_name}',
                 f'/{slug_repo_name}/', f'/{slug_repo_name}/build', f'/{slug_repo_name}/builds'):
        test_instance.resource = f'/{repo}'
        assert travis_service.get_repo_id(test_instance) == slug_repo_safe, "Unexpected slug repo name"


@pytest.mark.skipif(not token, reason="Travis token not set")
def test_service_token(travis_service: models.TravisTestingService):
    tk = travis_service.token
    assert tk, "The Travis token should be set"
    assert token == tk.value, "Unexpected Travis token"


@pytest.mark.skipif(not token, reason="Travis token not set")
def test_connection(travis_service):
    logger.debug("Testing service base url: %r", travis_service.url)
    response = requests.get(travis_service.api_base_url)
    assert response.status_code == 200, "Unable to connect to the TravisCI testing service"
    logger.debug("The response: %r", response.json())
    assert type(response.json()) == dict, "Unexpected response type"
    assert response.json()['hello'] == 'world', "Unable to connect to the server: invalid response"


@pytest.mark.skipif(not token, reason="Travis token not set")
def test_build_url(travis_service, travis_api_url, travis_job):
    url = travis_service._build_url(travis_job)
    logger.debug(url)
    assert url == "{}/{}".format(travis_api_url, travis_job), "Invalid url"


@pytest.mark.skipif(not token, reason="Travis token not set")
def test_project_metadata(travis_service, travis_job, travis_job_info):
    assert 'name' in travis_job_info, "Unable to find job name on project metadata"
    assert str(travis_job_info['id']) == travis_job, "Unexpected job ID"
    logger.debug("Job info: %r", travis_job_info)
    assert '@href' in travis_job_info, "Unable to find build info related with the {}".format(travis_job)
    assert travis_job_info['@href'] == "/repo/{}".format(travis_job), "Invalid repo"


@pytest.mark.skipif(not token, reason="Travis token not set")
def test_get_builds(travis_service, travis_job, test_instance):
    number_of_builds = 5
    builds = travis_service.get_test_builds(test_instance, limit=number_of_builds)
    logger.debug(len(builds))
    assert len(builds) == number_of_builds, "Unexpected number of limits"
    for b in builds:
        assert isinstance(b, models.TravisTestBuild), "Invalid build type"
        logger.debug(b)


@pytest.mark.skipif(not token, reason="Travis token not set")
def test_get_build(travis_service, test_instance):
    builds = travis_service.get_test_builds(test_instance)
    logger.info(builds)
    test_build = builds[0]
    logger.debug("Testing build: %r", test_build.id)
    build = travis_service.get_test_build(test_instance, test_build.id)
    logger.info(build)
    for p in ['id', 'build_number', 'duration', 'timestamp', 'status', 'duration', 'url']:
        assert getattr(build, p), "Unable to find the property {}".format(p)


@pytest.mark.skipif(not token, reason="Travis token not set")
def test_get_last_test_build(travis_service: models.TravisTestingService, test_instance):
    builds = travis_service.get_test_builds(test_instance)
    last_build = builds[0]  # builds are always ordered from the latest executed
    build = travis_service.get_last_test_build(test_instance)
    logger.debug("First build from the build list: %r", last_build.id)
    logger.debug("ID of the lastest build: %r", build.id)
    assert last_build.id == build.id, "Invalid build ID"


@pytest.mark.skipif(not token, reason="Travis token not set")
def test_get_last_failed_test_build(travis_service: models.TravisTestingService, test_instance):
    # search the last failed build
    builds = travis_service.get_test_builds(test_instance, limit=1000)
    found_failed_build = None
    for b in builds:
        logger.debug("Checking %r: status -> %r", b.id, b.status)
        if b.status == models.BuildStatus.FAILED:
            found_failed_build = b
            break
    logger.debug("Found build: %r", found_failed_build)
    assert found_failed_build, "Unable to find the latest failed build"
    build = travis_service.get_last_failed_test_build(test_instance)
    logger.debug("Latest failed build: %r", build)
    assert build, "Unable to get the latest failed build"
    # check if the two builds are equal or not
    assert found_failed_build.id == build.id, "Invalid build ID"


@pytest.mark.skipif(not token, reason="Travis token not set")
def test_get_last_passed_test_build(travis_service: models.TravisTestingService, test_instance):
    # search the last failed build
    builds = travis_service.get_test_builds(test_instance, limit=1000)
    found_failed_build = None
    for b in builds:
        logger.debug("Checking %r: status -> %r", b.id, b.status)
        if b.status == models.BuildStatus.PASSED:
            found_failed_build = b
            break
    logger.debug("Found build: %r", found_failed_build)
    assert found_failed_build, "Unable to find the latest failed build"
    build = travis_service.get_last_passed_test_build(test_instance)
    logger.debug("Latest passed build: %r", build)
    assert build, "Unable to get the latest failed build"
    # check if the two builds are equal or not
    assert found_failed_build.id == build.id, "Invalid build ID"


@pytest.mark.skipif(not token, reason="Travis token not set")
def test_get_last_logs(travis_service: models.TravisTestingService, test_instance):
    # search the last failed build
    builds = travis_service.get_test_builds(test_instance, limit=1000)
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
