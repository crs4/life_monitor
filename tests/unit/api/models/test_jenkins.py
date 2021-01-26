
import pytest
import logging
import lifemonitor.api.models as models


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
def jenkins_service(jenkins_url, jenkins_resource) -> models.JenkinsTestingService:
    return models.JenkinsTestingService(jenkins_url, jenkins_resource)


@pytest.fixture
def jenkins_job_info(jenkins_service):
    return jenkins_service.project_metadata


def test_connection(jenkins_service, jenkins_job):
    logger.info(jenkins_service.server.get_info())


def test_job_name(jenkins_service, jenkins_job):
    assert jenkins_service.job_name == jenkins_job, "Unexpected job name"


def test_project_metadata(jenkins_service, jenkins_job, jenkins_job_info):
    assert 'name' in jenkins_job_info, "Unable to find job name on project metadata"
    assert jenkins_job_info['name'] == jenkins_job, "Unexpected job name"
    assert 'builds' in jenkins_job_info, "Unable to find build info related with the {}".format(jenkins_job)


def test_latest_builds(jenkins_service):
    builds = jenkins_service.get_test_builds()
    logger.info(builds)
