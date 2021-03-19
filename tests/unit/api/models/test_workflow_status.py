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
import uuid
from unittest.mock import MagicMock

import lifemonitor.api.models as models
import lifemonitor.exceptions as lm_exceptions
import pytest

logger = logging.getLogger(__name__)


@pytest.fixture
def workflow():
    # uuid, version, submitter: User, roc_link,
    #  registry: models.WorkflowRegistry = None,
    #  roc_metadata = None, external_id = None, name = None
    return models.WorkflowVersion(MagicMock(), uuid.uuid4(), "1", MagicMock(),
                                  "https://link", MagicMock())


@pytest.fixture
def error_description():
    return "Something wrong happens"


@pytest.fixture
def suite(error_description, request):
    number_of_passing = request.param[0]
    number_of_failing = request.param[1]
    number_of_errors = request.param[2]

    suite = MagicMock()
    suite.test_instances = []
    for i in [True] * number_of_passing + \
             [False] * number_of_failing + \
             [None] * number_of_errors:
        test_instance = MagicMock()
        suite.test_instances.append(test_instance)
        test_instance.testing_service = MagicMock()
        test_instance.last_test_build = MagicMock()
        if i is None:
            test_instance.last_test_build.is_successful.side_effect = \
                lm_exceptions.TestingServiceException(error_description)
        else:
            test_instance.last_test_build.is_successful.return_value = i
    return suite


def test_transition_status_from_not_available_on_one_success():
    new_status = models.WorkflowStatus._update_status(models.AggregateTestStatus.NOT_AVAILABLE, True)
    assert new_status == models.AggregateTestStatus.ALL_PASSING, \
        f"The new status should be {models.AggregateTestStatus.ALL_PASSING}"


def test_transition_status_from_not_available_on_one_failure():
    new_status = models.WorkflowStatus._update_status(models.AggregateTestStatus.NOT_AVAILABLE, False)
    assert new_status == models.AggregateTestStatus.ALL_FAILING, \
        f"The new status should be {models.AggregateTestStatus.ALL_FAILING}"


def test_transition_status_from_all_passing_on_one_success():
    new_status = models.WorkflowStatus._update_status(models.AggregateTestStatus.ALL_PASSING, True)
    assert new_status == models.AggregateTestStatus.ALL_PASSING, \
        f"The new status should be {models.AggregateTestStatus.ALL_PASSING}"


def test_transition_status_from_all_passing_on_one_failure():
    new_status = models.WorkflowStatus._update_status(models.AggregateTestStatus.ALL_PASSING, False)
    assert new_status == models.AggregateTestStatus.SOME_PASSING, \
        f"The new status should be {models.AggregateTestStatus.SOME_PASSING}"


def test_transition_status_from_all_failing_on_one_success():
    new_status = models.WorkflowStatus._update_status(models.AggregateTestStatus.ALL_FAILING, True)
    assert new_status == models.AggregateTestStatus.SOME_PASSING, \
        f"The new status should be {models.AggregateTestStatus.SOME_PASSING}"


def test_transition_status_from_all_failing_on_one_failure():
    new_status = models.WorkflowStatus._update_status(models.AggregateTestStatus.ALL_FAILING, False)
    assert new_status == models.AggregateTestStatus.ALL_FAILING, \
        f"The new status should be {models.AggregateTestStatus.ALL_FAILING}"


def test_transition_status_from_some_passing_on_one_failure():
    new_status = models.WorkflowStatus._update_status(models.AggregateTestStatus.SOME_PASSING, False)
    assert new_status == models.AggregateTestStatus.SOME_PASSING, \
        f"The new status should be {models.AggregateTestStatus.SOME_PASSING}"


def test_transition_status_from_some_passing_on_one_success():
    new_status = models.WorkflowStatus._update_status(models.AggregateTestStatus.SOME_PASSING, True)
    assert new_status == models.AggregateTestStatus.SOME_PASSING, \
        f"The new status should be {models.AggregateTestStatus.SOME_PASSING}"


def test_status_no_suite(workflow):
    assert len(workflow.test_suites) == 0, "Number of suites different from 0"
    status = workflow.status
    assert isinstance(status, models.WorkflowStatus), "Invalid status type"
    assert status.aggregated_status == models.AggregateTestStatus.NOT_AVAILABLE, \
        f"The actual workflow status should be {models.AggregateTestStatus.NOT_AVAILABLE}"
    assert len(status.latest_builds) == 0, "The number of builds should be 0"
    assert len(status.availability_issues) == 1, "One issue should be reported"
    assert "No test suite" in status.availability_issues[0]['issue'], "Invalid issue"


def test_status_no_instances(mocker, workflow):
    assert len(workflow.test_suites) == 0, "Number of suites different from 0"
    workflow.test_suites.append(MagicMock())
    logger.debug(workflow.test_suites)
    status = workflow.status
    assert isinstance(status, models.WorkflowStatus), "Invalid status type"
    assert status.aggregated_status == models.AggregateTestStatus.NOT_AVAILABLE, \
        f"The actual workflow status should be {models.AggregateTestStatus.NOT_AVAILABLE}"
    assert len(status.latest_builds) == 0, "The number of builds should be 0"
    assert len(status.availability_issues) == 1, "One issue should be reported"
    assert "No test instances" in status.availability_issues[0]['issue'], "Invalid issue"


@pytest.mark.parametrize("suite", [(1, 0, 0)], indirect=True)
def test_status_only_one_build_passing(workflow, suite):
    assert len(workflow.test_suites) == 0, "Number of suites different from 0"
    assert len(suite.test_instances) == 1, "Unexpected number of test instances"
    status = workflow.status
    assert isinstance(status, models.WorkflowStatus), "Invalid status type"
    assert status.aggregated_status == models.AggregateTestStatus.NOT_AVAILABLE, \
        f"The actual workflow status should be {models.AggregateTestStatus.NOT_AVAILABLE}"
    workflow.test_suites.append(suite)
    status = workflow.status
    assert isinstance(status, models.WorkflowStatus), "Invalid status type"
    assert status.aggregated_status == models.AggregateTestStatus.ALL_PASSING, \
        f"The actual workflow status should be {models.AggregateTestStatus.NOT_AVAILABLE}"
    assert len(status.latest_builds) == 1, "The number of builds should be 1"


@pytest.mark.parametrize("suite", [(0, 1, 0)], indirect=True)
def test_status_only_one_build_failing(workflow, suite):
    assert len(workflow.test_suites) == 0, "Number of suites different from 0"
    assert len(suite.test_instances) == 1, "Unexpected number of test instances"
    status = workflow.status
    assert isinstance(status, models.WorkflowStatus), "Invalid status type"
    assert status.aggregated_status == models.AggregateTestStatus.NOT_AVAILABLE, \
        f"The actual workflow status should be {models.AggregateTestStatus.NOT_AVAILABLE}"
    workflow.test_suites.append(suite)
    logger.debug("Adding suite: %r", suite)
    status = workflow.status
    assert status.aggregated_status == models.AggregateTestStatus.ALL_FAILING, \
        f"The actual workflow status should be {models.AggregateTestStatus.ALL_FAILING}"
    assert len(status.latest_builds) == 1, "The number of builds should be 1"


@pytest.mark.parametrize("suite", [(5, 0, 0)], indirect=True)
def test_status_all_build_passing(workflow, suite):
    assert len(workflow.test_suites) == 0, "Number of suites different from 0"
    assert len(suite.test_instances) == 5, "Unexpected number of test instances"
    status = workflow.status
    assert isinstance(status, models.WorkflowStatus), "Invalid status type"
    assert status.aggregated_status == models.AggregateTestStatus.NOT_AVAILABLE, \
        f"The actual workflow status should be {models.AggregateTestStatus.NOT_AVAILABLE}"
    workflow.test_suites.append(suite)
    status = workflow.status
    assert status.aggregated_status == models.AggregateTestStatus.ALL_PASSING, \
        f"The actual workflow status should be {models.AggregateTestStatus.ALL_PASSING}"
    assert len(status.latest_builds) == 5, "The number of builds should be 5"


@pytest.mark.parametrize("suite", [(0, 5, 0)], indirect=True)
def test_status_all_build_failing(workflow, suite):
    assert len(workflow.test_suites) == 0, "Number of suites different from 0"
    assert len(suite.test_instances) == 5, "Unexpected number of test instances"
    status = workflow.status
    assert isinstance(status, models.WorkflowStatus), "Invalid status type"
    assert status.aggregated_status == models.AggregateTestStatus.NOT_AVAILABLE, \
        f"The actual workflow status should be {models.AggregateTestStatus.NOT_AVAILABLE}"
    workflow.test_suites.append(suite)
    status = workflow.status
    assert status.aggregated_status == models.AggregateTestStatus.ALL_FAILING, \
        f"The actual workflow status should be {models.AggregateTestStatus.ALL_FAILING}"
    assert len(status.latest_builds) == 5, "The number of builds should be 5"


@pytest.mark.parametrize("suite", [(3, 2, 0)], indirect=True)
def test_status_some_build_passing(workflow, suite):
    assert len(workflow.test_suites) == 0, "Number of suites different from 0"
    assert len(suite.test_instances) == 5, "Unexpected number of test instances"
    status = workflow.status
    assert isinstance(status, models.WorkflowStatus), "Invalid status type"
    assert status.aggregated_status == models.AggregateTestStatus.NOT_AVAILABLE, \
        f"The actual workflow status should be {models.AggregateTestStatus.NOT_AVAILABLE}"
    workflow.test_suites.append(suite)
    status = workflow.status
    assert status.aggregated_status == models.AggregateTestStatus.SOME_PASSING, \
        f"The actual workflow status should be {models.AggregateTestStatus.SOME_PASSING}"
    assert len(status.latest_builds) == 5, "The number of builds should be 5"


@pytest.mark.parametrize("suite", [(3, 2, 1)], indirect=True)
def test_status_some_build_passing_check_issues(workflow, suite, error_description):
    assert len(workflow.test_suites) == 0, "Number of suites different from 0"
    assert len(suite.test_instances) == 6, "Unexpected number of test instances"
    status = workflow.status
    assert isinstance(status, models.WorkflowStatus), "Invalid status type"
    assert status.aggregated_status == models.AggregateTestStatus.NOT_AVAILABLE, \
        f"The actual workflow status should be {models.AggregateTestStatus.NOT_AVAILABLE}"
    workflow.test_suites.append(suite)
    status = workflow.status
    assert status.aggregated_status == models.AggregateTestStatus.SOME_PASSING, \
        f"The actual workflow status should be {models.AggregateTestStatus.SOME_PASSING}"
    assert len(status.latest_builds) == 6, "The number of builds should be 5"
    assert len(status.availability_issues) == 1, "One issue should be reported"
    assert error_description in status.availability_issues[0]['issue'], "Invalid issue"
