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

import itertools
import logging
from datetime import datetime, timedelta
from typing import List, Optional
from unittest.mock import MagicMock

import lifemonitor.api.models as models
import pytest
from github.Workflow import Workflow
from github.WorkflowRun import WorkflowRun
from lifemonitor.api.models.repositories.github import GithubWorkflowRepository
from lifemonitor.cache import cache
from tests.conftest_helpers import get_github_token

logger = logging.getLogger(__name__)

build_query_limit = 20

# reference to the main workflow installed on life-monitor/workflow-tests repository
workflow_tests_resource = '/repos/life-monitor/workflow-tests/actions/workflows/28339110'

# Fixtures are matched to test arguments through their name, so the warning
# about redefining the outer name gets in our way.
# pylint: disable=redefined-outer-name


@pytest.fixture
def api_url() -> str:
    return 'https://api.github.com'


@pytest.fixture
def repo_full_name() -> str:
    return "life-monitor/workflow-tests"


@pytest.fixture
def test_workflow_resource() -> str:
    return workflow_tests_resource


@pytest.fixture
def git_ref(request):
    ref_type = "branch"
    ref_value = "main"
    ref = None
    try:
        ref_type = request.param[0]
        ref_value = request.param[1]
    except Exception:
        logger.warning("Not param for test_instance fixture")
    # set repo ref
    if ref_type and ref_value:
        ref = f"refs/{'heads' if ref_type=='branch' else 'tags'}/{ref_value}"
    return ref_type, ref_value, ref


@pytest.fixture
def test_instance(request, git_ref, repo_full_name, test_workflow_resource):
    ref_type, ref_value, ref = git_ref
    test_resource = test_workflow_resource
    try:
        test_resource = request.param
    except Exception:
        pass
    # define a parametric revision
    revision = MagicMock()
    revision.main_ref = MagicMock()
    revision.main_ref.shorthand = ref_value
    # define a test suite mock
    test_suite = MagicMock()
    test_suite.workflow_version = MagicMock()
    test_suite.workflow_version.version = revision.main_ref.shorthand
    test_suite.workflow_version.revision = revision if ref_value else None
    test_suite.workflow_version.repository = GithubWorkflowRepository(repo_full_name, ref=ref)
    # define a test_instance mock
    instance = MagicMock()
    instance.resource = test_resource
    instance.test_suite = test_suite
    return instance


@pytest.fixture
def test_instance_one_version(test_instance):
    test_instance.test_suite.workflow_version.previous_version = None
    test_instance.test_suite.workflow_version.next_version = None
    return test_instance


@pytest.fixture
def github_token() -> Optional[models.TestingServiceToken]:
    token = get_github_token()
    return models.TestingServiceToken('Bearer', token) if token else None


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


@pytest.mark.parametrize("git_ref", [("tag", "0.1.0")], indirect=True)
def test_get_builds(github_service, git_ref, test_instance_one_version):
    builds = github_service.get_test_builds(test_instance_one_version)
    assert len(builds) == 1
    assert all(isinstance(b, models.GithubTestBuild) for b in builds)
    # verify order by decreasing timestamp
    for i in range(len(builds) - 1):
        assert builds[i].timestamp > builds[i + 1].timestamp


@pytest.mark.parametrize("git_ref", [(None, None)], indirect=True)
def test_get_builds_limit(github_service, git_ref, test_instance_one_version):
    number_of_builds = 5
    builds = github_service.get_test_builds(test_instance_one_version, limit=number_of_builds)
    assert len(builds) == number_of_builds, "Returned number of builds != specified limit"


@pytest.mark.parametrize("git_ref", [(None, None)], indirect=True)
def test_get_one_build(github_service, git_ref, test_instance_one_version):
    builds = github_service.get_test_builds(test_instance_one_version, limit=8)
    test_build = builds[3]
    build = github_service.get_test_build(test_instance_one_version, test_build.id)
    assert build
    assert build.id == test_build.id
    for p in ('id', 'build_number', 'duration', 'metadata', 'revision', 'result', 'status', 'timestamp', 'url'):
        assert getattr(build, p), "Unable to find the property {}".format(p)


@pytest.mark.parametrize("git_ref", [(None, None)], indirect=True)
def test_get_last_builds(github_service: models.GithubTestingService, git_ref, test_instance_one_version):
    the_builds = github_service.get_test_builds(test_instance_one_version, limit=build_query_limit)
    # latest build
    last_build = github_service.get_last_test_build(test_instance_one_version)
    assert last_build.id == the_builds[0].id
    # latest passed build
    latest_passed_build = github_service.get_last_passed_test_build(test_instance_one_version)
    # Get first passed build from the list, or None if there are None
    build = next((b for b in the_builds if b.is_successful()), None)
    assert build == latest_passed_build or (build is None) or \
        (build is not None and latest_passed_build is not None and build.id == latest_passed_build.id)
    # latest failed build
    latest_failed_build = github_service.get_last_failed_test_build(test_instance_one_version)
    build = next((b for b in the_builds if not b.is_successful()), None)
    assert build == latest_failed_build or build is None or \
        (build is not None and latest_failed_build is not None and build.id == latest_failed_build.id)


