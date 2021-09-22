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
from typing import Optional
from unittest.mock import MagicMock

import lifemonitor.api.models as models
import pytest
from tests.conftest_helpers import get_github_token

logger = logging.getLogger(__name__)

build_query_limit = 20

# Fixtures are matched to test arguments through their name, so the warning
# about redefining the outer name gets in our way.
# pylint: disable=redefined-outer-name


@pytest.fixture
def api_url() -> str:
    return 'https://api.github.com'


@pytest.fixture
def test_workflow_resource() -> str:
    return '/repos/crs4/life_monitor/actions/workflows/4094661'


@pytest.fixture
def test_instance(test_workflow_resource):
    instance = MagicMock()
    instance.resource = test_workflow_resource
    return instance


@pytest.fixture
def github_token() -> Optional[models.TestingServiceToken]:
    return models.TestingServiceToken('Bearer', get_github_token())


@pytest.fixture
def github_service(api_url: str, github_token: models.TestingServiceToken) -> models.GithubTestingService:
    return models.GithubTestingService(url=api_url, token=github_token)


def test_connection_no_api_url(github_token):
    # Test that the GithubTestingService works without specifying a URL for the API.
    # The API URL isn't implemented as a fixture parameter to `github_service` because
    # that would result in repeating all the tests with both fixture values, which
    # makes it more likely that the tests will fail due to GitHub's API request limit rate.
    github_service = models.GithubTestingService(token=github_token)
    assert github_service.check_connection()


def test_connection(github_service):
    assert github_service.check_connection()


def test_get_builds(github_service, test_instance):
    builds = github_service.get_test_builds(test_instance)
    assert len(builds) == 10
    assert all(isinstance(b, models.GithubTestBuild) for b in builds)
    # verify order by decreasing timestamp
    for i in range(len(builds) - 1):
        assert builds[i].timestamp > builds[i + 1].timestamp


def test_get_builds_limit(github_service, test_instance):
    number_of_builds = 5
    builds = github_service.get_test_builds(test_instance, limit=number_of_builds)
    assert len(builds) == number_of_builds, "Returned number of builds != specified limit"


def test_get_one_build(github_service, test_instance):
    builds = github_service.get_test_builds(test_instance, limit=8)
    test_build = builds[3]
    build = github_service.get_test_build(test_instance, test_build.build_number)
    assert build
    assert build.id == test_build.id
    for p in ('id', 'build_number', 'duration', 'metadata', 'revision', 'result', 'status', 'timestamp', 'url'):
        assert getattr(build, p), "Unable to find the property {}".format(p)


def test_get_last_builds(github_service: models.GithubTestingService, test_instance):
    the_builds = github_service.get_test_builds(test_instance, limit=build_query_limit)
    # latest build
    last_build = github_service.get_last_test_build(test_instance)
    assert last_build.id == the_builds[0].id
    # latest passed build
    latest_passed_build = github_service.get_last_passed_test_build(test_instance)
    # Get first passed build from the list, or None if there are None
    build = next((b for b in the_builds if b.is_successful()), None)
    assert build == latest_passed_build or (build is None) or \
        (build is not None and latest_passed_build is not None and build.id == latest_passed_build.id)
    # latest failed build
    latest_failed_build = github_service.get_last_failed_test_build(test_instance)
    build = next((b for b in the_builds if not b.is_successful()), None)
    assert build == latest_failed_build or build is None or \
        (build is not None and latest_failed_build is not None and build.id == latest_failed_build.id)
