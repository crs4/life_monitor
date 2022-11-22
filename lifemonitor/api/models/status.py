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

from __future__ import annotations

import logging

import lifemonitor.exceptions as lm_exceptions
from lifemonitor.lang import messages

# set module level logger
logger = logging.getLogger(__name__)


class AggregateTestStatus:
    ALL_PASSING = "all_passing"
    SOME_PASSING = "some_passing"
    ALL_FAILING = "all_failing"
    NOT_AVAILABLE = "not_available"


class Status:

    def __init__(self) -> None:
        self._status = AggregateTestStatus.NOT_AVAILABLE
        self._latest_builds = None
        self._availability_issues = None

    @property
    def aggregated_status(self):
        return self._status

    @property
    def latest_builds(self):
        return self._latest_builds.copy()

    @property
    def availability_issues(self):
        return self._availability_issues.copy()

    @staticmethod
    def _update_status(current_status, build_passing):
        status = current_status
        if status == AggregateTestStatus.NOT_AVAILABLE:
            if build_passing:
                status = AggregateTestStatus.ALL_PASSING
            elif not build_passing:
                status = AggregateTestStatus.ALL_FAILING
        elif status == AggregateTestStatus.ALL_PASSING:
            if not build_passing:
                status = AggregateTestStatus.SOME_PASSING
        elif status == AggregateTestStatus.ALL_FAILING:
            if build_passing:
                status = AggregateTestStatus.SOME_PASSING
        return status

    @classmethod
    def _skip_build(cls, test_build) -> bool:
        return not test_build or test_build.status not in ["passed", "failed", "error"]

    @classmethod
    def check_status(cls, suites):
        status = AggregateTestStatus.NOT_AVAILABLE
        latest_builds = []
        availability_issues = []

        if len(suites) == 0:
            availability_issues.append({
                "issue": messages.no_test_suite
            })

        for suite in suites:
            if len(suite.test_instances) == 0:
                availability_issues.append({
                    "issue": messages.no_test_instance_for_suite.format(suite)
                })
            for test_instance in suite.test_instances:
                try:
                    latest_build = test_instance.last_test_build
                    if latest_build is None:
                        availability_issues.append({
                            "service": test_instance.testing_service.url,
                            "test_instance": test_instance,
                            "issue": messages.no_build_found_for_instance.format(test_instance)
                        })
                    else:
                        # Search the latest completed build
                        for latest_build in test_instance.get_test_builds():
                            logger.debug("Checking build %r: %r", latest_build, latest_build.status)
                            if not cls._skip_build(latest_build):
                                break
                        # add build to the set of latest builds
                        latest_builds.append(latest_build)
                        # Update aggregated status using the latest completed build
                        logger.debug("Latest build found: %r", latest_build)
                        if not cls._skip_build(latest_build):
                            status = cls._update_status(status, latest_build.is_successful())
                except lm_exceptions.TestingServiceException as e:
                    availability_issues.append({
                        "service": test_instance.testing_service.url,
                        "resource": test_instance.resource,
                        "issue": str(e)
                    })
                    logger.exception(e)
                except Exception as e:
                    availability_issues.append({
                        "service": test_instance.testing_service.url,
                        "resource": test_instance.resource,
                        "issue": str(e)
                    })
                    logger.exception(e)

        # update the current status
        return status, latest_builds, availability_issues


class WorkflowStatus(Status):

    def __init__(self, workflow) -> None:
        self.workflow = workflow
        self._status, self._latest_builds, self._availability_issues = WorkflowStatus.check_status(self.workflow.test_suites)


class SuiteStatus(Status):

    def __init__(self, suite) -> None:
        self.suite = suite
        self._status, self._latest_builds, self._availability_issues = Status.check_status([suite])
