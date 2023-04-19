# Copyright (c) 2020-2022 CRS4
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

import pytest
from github.WorkflowRun import WorkflowRun

import lifemonitor.api.models as models
from lifemonitor.api.models.repositories.github import GithubWorkflowRepository
from lifemonitor.cache import cache
from tests.conftest_helpers import get_github_token
from tests.unit.test_utils import SerializableMock

logger = logging.getLogger(__name__)

build_query_limit = 20

# reference to the main workflow installed on lifemonitor/workflow-tests repository
workflow_tests_resource = '/repos/lifemonitor/workflow-tests/actions/workflows/28339110'

# set token from env
token = get_github_token()

# Fixtures are matched to test arguments through their name, so the warning
# about redefining the outer name gets in our way.
# pylint: disable=redefined-outer-name


@pytest.fixture
def api_url() -> str:
    return 'https://api.github.com'


@pytest.fixture
def repo_full_name() -> str:
    return "lifemonitor/workflow-tests"


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
        logger.debug("Not param for test_instance fixture")
    # set repo ref
    if ref_type and ref_value:
        ref = f"refs/{'heads' if ref_type=='branch' else 'tags'}/{ref_value}"
    return ref_type, ref_value, ref


@pytest.mark.skipif(not token, reason="Github token not set")
@pytest.fixture
def test_instance(request, git_ref, repo_full_name, test_workflow_resource):
    ref_type, ref_value, ref = git_ref
    test_resource = test_workflow_resource
    try:
        test_resource = request.param
    except Exception:
        pass
    # define a parametric revision
    revision = SerializableMock()
    revision.main_ref = SerializableMock()
    revision.main_ref.shorthand = ref_value
    # define a test suite mock
    test_suite = SerializableMock()
    test_suite.workflow_version = SerializableMock()
    test_suite.workflow_version.version = revision.main_ref.shorthand
    test_suite.workflow_version.revision = revision if ref_value else None
    test_suite.workflow_version.repository = GithubWorkflowRepository(repo_full_name, ref=ref)
    # define a test_instance mock
    instance = SerializableMock()
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
    return models.TestingServiceToken('Bearer', token) if token else None


@pytest.fixture
def github_service(api_url: str, github_token: models.TestingServiceToken) -> models.GithubTestingService:
    return models.GithubTestingService(url=api_url, token=github_token)


@pytest.mark.skipif(not token, reason="Github token not set")
def test_connection_no_api_url(github_token):
    # Test that the GithubTestingService works without specifying a URL for the API.
    # The API URL isn't implemented as a fixture parameter to `github_service` because
    # that would result in repeating all the tests with both fixture values, which
    # makes it more likely that the tests will fail due to GitHub's API request limit rate.
    github_service = models.GithubTestingService(token=github_token)
    assert github_service.check_connection()


@pytest.mark.skipif(not token, reason="Github token not set")
def test_connection(github_service):
    assert github_service.check_connection()


@pytest.mark.skipif(not token, reason="Github token not set")
@pytest.mark.parametrize("git_ref", [("tag", "0.1.0")], indirect=True)
def test_get_builds(github_service, git_ref, test_instance_one_version):
    builds = github_service.get_test_builds(test_instance_one_version)
    assert len(builds) == 1
    assert all(isinstance(b, models.GithubTestBuild) for b in builds)
    # verify order by decreasing timestamp
    for i in range(len(builds) - 1):
        assert builds[i].timestamp > builds[i + 1].timestamp


@pytest.mark.skipif(not token, reason="Github token not set")
@pytest.mark.parametrize("git_ref", [(None, None)], indirect=True)
def test_get_builds_limit(github_service, git_ref, test_instance_one_version):
    number_of_builds = 5
    builds = github_service.get_test_builds(test_instance_one_version, limit=number_of_builds)
    assert len(builds) == number_of_builds, "Returned number of builds != specified limit"


@pytest.mark.skipif(not token, reason="Github token not set")
@pytest.mark.parametrize("git_ref", [(None, None)], indirect=True)
def test_get_one_build(github_service, git_ref, test_instance_one_version):
    builds = github_service.get_test_builds(test_instance_one_version, limit=10)
    test_build = builds[3]
    logger.debug("Loaded builds: {}".format(builds))
    logger.debug("Selected build: {}".format(test_build))
    build = github_service.get_test_build(test_instance_one_version, test_build.id)
    logger.debug("Found build: {}".format(build))
    assert build
    assert build.id == test_build.id
    for p in ('id', 'build_number', 'duration', 'metadata', 'revision', 'result', 'status', 'timestamp', 'url'):
        assert getattr(build, p), "Unable to find the property {}".format(p)


@pytest.mark.skipif(not token, reason="Github token not set")
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


@pytest.mark.skipif(not token, reason="Github token not set")
@pytest.mark.parametrize("git_ref", [("branch", "main")], indirect=True)
@pytest.mark.parametrize("test_instance", [workflow_tests_resource], indirect=True)
def test_instance_builds_filtered_by_branch(github_service: models.GithubTestingService, git_ref, test_instance):
    # retrieve repo and ref info
    ref_type, ref_value, ref = git_ref
    _, repository, workflow_id = github_service._get_workflow_info(test_instance.resource)
    # get github workflow
    gh_workflow = github_service._get_gh_workflow(repository, workflow_id)
    logger.debug("Gh Workflow: %r", gh_workflow)
    # get runs filtered by branch
    runs: List[WorkflowRun] = list(run for run in itertools.islice(
        github_service.__get_gh_workflow_runs__(gh_workflow, branch=ref_value), build_query_limit))
    logger.debug("Runs: %r", runs)
    # check if runs refer to the expected branch
    for run in runs:
        assert run.head_branch == ref_value, f"Unexpected branch for workflow run {run}"


@pytest.mark.skipif(not token, reason="Github token not set")
@pytest.mark.parametrize("git_ref", [(None, None)], indirect=True)
@pytest.mark.parametrize("test_instance", [workflow_tests_resource], indirect=True)
def test_get_runs_by_date(github_service: models.GithubTestingService, git_ref, test_instance):
    # retrieve repo and ref info
    ref_type, ref_value, ref = git_ref
    _, repository, workflow_id = github_service._get_workflow_info(test_instance.resource)
    # get github workflow
    gh_workflow = github_service._get_gh_workflow(repository, workflow_id)
    logger.debug("Gh Workflow: %r", gh_workflow)
    # get runs filtered by branch
    runs = list(run for run in itertools.islice(
        github_service.__get_gh_workflow_runs__(gh_workflow, branch=ref_value), build_query_limit))
    logger.debug("Runs: %r", runs)

    # get the latest n runs
    n = round(len(runs) / 2) + 1
    nrun = runs[n]
    logger.debug("N=%d run: %r --> %r", n, nrun, nrun.created_at)
    for run in runs:
        logger.debug("Run: %r --> %r -- %r", run, run.created_at, run.created_at > nrun.created_at)
    logger.debug("Number of runs: %d", len(runs))

    # get all runs after nrun
    runs_after = [_ for _ in github_service.__get_gh_workflow_runs__(
        gh_workflow, branch=ref_value,
        created="{}..{}".format(nrun.created_at.isoformat(),
                                runs[0].created_at.isoformat()))]
    logger.debug("Runs after: %r --- num: %r", runs_after, len(runs_after))
    # check number of runs
    assert len(runs_after) == (n + 1), "Unexpected number of runs"
    # check run creation time
    for run in runs_after:
        logger.debug("Run: %r --> %r -- of array: %r", run, run.created_at, run in runs)
        assert run.created_at >= nrun.created_at, "Run should be created after %r" % nrun.created_at.isoformat()

    logger.debug("Runs after: %r --- num: %r", runs_after, len(runs_after))


@pytest.mark.skipif(not token, reason="Github token not set")
@pytest.mark.parametrize("git_ref", [("branch", "main"), ("tag", "0.1.0"), ("tag", "0.3.0")], indirect=True)
@pytest.mark.parametrize("test_instance", [workflow_tests_resource], indirect=True)
def test_instance_builds_versioned_by_revision(
        github_service: models.GithubTestingService, git_ref, test_instance):

    ref_type, ref_value, ref = git_ref
    repo = test_instance.test_suite.workflow_version.repository
    assert repo
    assert repo.revision.main_ref.shorthand == ref_value or "main"

    _, repository, workflow_id = github_service._get_workflow_info(test_instance.resource)
    repo = GithubWorkflowRepository(repository)
    for w in repo.get_workflows():
        logger.debug("Workflow: %r", w)

    gh_workflow = github_service._get_gh_workflow(repository, workflow_id)
    logger.debug("Gh Workflow: %r", gh_workflow)

    branch_runs = list(run for run in itertools.islice(
        github_service.__get_gh_workflow_runs__(gh_workflow, branch=ref_value), build_query_limit))
    logger.debug("Runs: %r", branch_runs)

    instance_runs = github_service.get_test_builds(test_instance, limit=len(branch_runs))
    logger.debug("Instance runs: %r", instance_runs)

    assert len(instance_runs) == len(branch_runs), "Unexpected number of runs for the instance revision"

    branch_run_ids = [_.id for _ in branch_runs]
    instance_run_ids = [_.build_number for _ in instance_runs]
    found = []
    not_found = []
    for run in branch_run_ids:
        if run in instance_run_ids:
            found.append(run)
        else:
            not_found.append(run)
    logger.debug("Found: %r", found)
    logger.debug("Not found: %r", not_found)


@pytest.mark.skipif(not token, reason="Github token not set")
@pytest.mark.parametrize("git_ref", [(None, None)], indirect=True)
def test_instance_builds_versioned_by_date(
        github_service: models.GithubTestingService, git_ref, test_instance_one_version):

    assert not test_instance_one_version.test_suite.workflow_version.previous_version
    assert not test_instance_one_version.test_suite.workflow_version.next_version

    ref_type, ref_value, ref = git_ref

    repo = test_instance_one_version.test_suite.workflow_version.repository
    assert repo
    assert repo.revision.main_ref.shorthand == ref_value or "main"

    _, repository, workflow_id = github_service._get_workflow_info(test_instance_one_version.resource)

    repo = GithubWorkflowRepository(repository)
    for w in repo.get_workflows():
        logger.debug("Workflow: %r", w)

    gh_workflow = github_service._get_gh_workflow(repository, workflow_id)
    logger.debug("Gh Workflow: %r", gh_workflow)

    items_limit = 10

    # github_service._get_gh_workflow_runs(
    all_runs = github_service._list_workflow_runs(test_instance_one_version, limit=items_limit)
    for run in all_runs:
        logger.debug("Run: {} created at {} updated at {} attempts {}".format(run, run.created_at, run.updated_at, run.raw_data.get("run_attempt")))
    assert len(all_runs) == 6, "Unexpected number of runs"

    instance_all_builds = github_service.get_test_builds(test_instance_one_version, limit=items_limit)
    for instance in instance_all_builds:
        logger.debug("Instance run: %r", instance)

    assert len(instance_all_builds) == 10, "Unexpected number of runs for the instance revision"

    for run in all_runs:
        logger.debug("Build %r created at %r updated at %r", run, run.created_at, run.updated_at)

    with cache.transaction():
        branch_run_ids = [_.id for _ in all_runs]
        instance_run_ids = [_.build_number for _ in instance_all_builds]
        found = []
        not_found = []
        for run in branch_run_ids:
            if run in instance_run_ids:
                found.append(run)
            else:
                not_found.append(run)
        logger.debug("Found: %r", found)
        logger.debug("Not found: %r", not_found)

        assert len(instance_all_builds) >= 3, "Unexpected number of runs"

    # simulate latest version with at least one previous version
    with cache.transaction():
        for b in instance_all_builds:
            logger.debug("Instance: %r - %r", b, b.created_at)
        logger.debug("Build split: %r", datetime.fromtimestamp(all_runs[2].created_at.timestamp()))
        v1 = MagicMock()
        v1.created = datetime.fromtimestamp(all_runs[2].created_at.timestamp())
        test_instance_one_version.test_suite.workflow_version.previous_version = v1
        test_instance_one_version.test_suite.workflow_version.created = datetime.fromtimestamp(all_runs[1].created_at.timestamp())
        test_instance_one_version.test_suite.workflow_version.next_version = None

        assert test_instance_one_version.test_suite.workflow_version.previous_version

        instance_builds = github_service.get_test_builds(test_instance_one_version, limit=items_limit)
        logger.debug("Instance runs: %r --> count: %d", instance_builds, len(instance_builds))
        # raise RuntimeError("Runs: %r", instance_builds)

        instance_run_ids = [_.build_number for _ in instance_builds]
        found = []
        not_found = []
        for run in all_runs:
            if run.id in instance_run_ids:
                found.append(run)
            else:
                not_found.append(run)
        logger.debug("Found: %r", [f"{x}: {x.created_at}" for x in found])
        logger.debug("Not found: %r", [f"{x}: {x.created_at}" for x in not_found])

        assert len(instance_builds) == (len(instance_all_builds) - 1), "Unexpected number of runs for the instance revision"

    # simulate an intermediate workflow version
    with cache.transaction():
        # builds_split = all_runs[1]
        v2 = MagicMock()
        test_instance_one_version.test_suite.workflow_version.next_version = v2
        test_instance_one_version.test_suite.workflow_version.created = datetime.fromtimestamp(all_runs[1].created_at.timestamp())
        v2.created = datetime.fromtimestamp(all_runs[0].created_at.timestamp())

        instance_builds = github_service.get_test_builds(test_instance_one_version, limit=items_limit)
        logger.debug("Instance runs: %r", instance_builds)

        assert len(instance_builds) == 8, "Unexpected number of runs for the instance revision"


@pytest.mark.skipif(not token, reason="Github token not set")
@pytest.mark.skip(reason="skip this test by default")
@pytest.mark.parametrize("git_ref", [("tag", "0.3.0")], indirect=True)
@pytest.mark.parametrize("test_instance", [workflow_tests_resource], indirect=True)
def test_versioned_instance_new_build(
        github_service: models.GithubTestingService, git_ref, test_instance):

    assert test_instance.resource == workflow_tests_resource

    ref_type, ref_value, ref = git_ref
    repo = test_instance.test_suite.workflow_version.repository
    assert repo
    assert repo.revision.main_ref.shorthand == ref_value

    last_build = github_service.get_last_test_build(test_instance)
    assert last_build, "Last build not found"

    assert github_service.start_test_build(test_instance), "Test instance build not started"


@pytest.mark.skipif(not token, reason="Github token not set")
def test_instance_list_gh_workflows(github_service: models.GithubTestingService, repo_full_name):
    repo = github_service._gh_service.get_repo(repo_full_name)
    for w in repo.get_workflows():
        logger.debug("Workflow: %r", w)
