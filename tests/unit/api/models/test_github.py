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

import pytest

import lifemonitor.api.models as models

logger = logging.getLogger(__name__)

build_query_limit = 20

# Fixtures are matched to test arguments through their name, so the warning
# about redefining the outer name gets in our way.
# pylint: disable=redefined-outer-name


@pytest.fixture
def test_workflow_url():
    return 'https://api.github.com/repos/crs4/life_monitor/actions/workflows/4094661'


@pytest.fixture
def test_instance(test_workflow_url):
    instance = MagicMock()
    instance.resource = test_workflow_url
    return instance


@pytest.fixture
def github_token() -> Optional[models.TestingServiceToken]:
    return None


@pytest.fixture
def github_service(github_token: models.TestingServiceToken = None) -> models.GitHubTestingService:
    return models.GitHubTestingService(token=github_token)


def test_connection(github_service):
    assert github_service.check_connection()


def test_get_builds(github_service, test_instance):
    builds = github_service.get_test_builds(test_instance)
    assert len(builds) == 10
    assert all(isinstance(b, models.GitHubTestBuild) for b in builds)
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


def test_get_last_builds(github_service: models.GitHubTestingService, test_instance):
    the_builds = github_service.get_test_builds(test_instance, limit=build_query_limit)
    # latest build
    last_build = github_service.get_last_test_build(test_instance)
    assert last_build.id == the_builds[0].id
    # latest passed build
    latest_passed_build = github_service.get_last_passed_test_build(test_instance)
    # Get first passed build from the list, or None if there are None
    build = next((b for b in the_builds if b.is_successful()), None)
    assert build == latest_passed_build or \
        (build is not None and latest_passed_build is not None and build.id == latest_passed_build.id)
    # latest failed build
    latest_failed_build = github_service.get_last_failed_test_build(test_instance)
    build = next((b for b in the_builds if not b.is_successful()), None)
    assert build == latest_failed_build or \
        (build is not None and latest_failed_build is not None and build.id == latest_failed_build.id)
