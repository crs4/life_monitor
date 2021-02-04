
import os
import pytest
import logging
import requests
from unittest.mock import MagicMock
import lifemonitor.api.models as models


logger = logging.getLogger(__name__)

# global token to test Travis API
token = os.environ.get('TRAVIS_TESTING_SERVICE_TOKEN', False)


@pytest.fixture
def travis_url():
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


@pytest.mark.skipif(not token, reason="Travis token not set")
def test_service_token(travis_url):
    service = models.TravisTestingService(travis_url)
    logger.debug(service)
    tk = models.TestingServiceTokenManager.get_instance().get_token(travis_url)
    assert token == tk.secret, "Unexpected Travis token"


@pytest.mark.skipif(not token, reason="Travis token not set")
def test_connection(travis_service):
    logger.debug("Testing service base url: %r", travis_service.url)
    response = requests.get(travis_service.url)
    assert response.status_code == 200, "Unable to connect to the TravisCI testing service"
    logger.debug("The response: %r", response.json())
    assert type(response.json()) == dict, "Unexpected response type"
    assert response.json()['hello'] == 'world', "Unable to connect to the server: invalid response"


@pytest.mark.skipif(not token, reason="Travis token not set")
def test_repo_id(travis_service, test_instance, travis_job):
    assert travis_service.get_repo_id(test_instance) == travis_job, "Unexpected repo ID"


@pytest.mark.skipif(not token, reason="Travis token not set")
def test_build_url(travis_service, travis_url, travis_job):
    url = travis_service._build_url(travis_job)
    logger.debug(url)
    assert url == "{}/{}".format(travis_url, travis_job), "Invalid url"


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
