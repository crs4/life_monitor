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
from lifemonitor.cache import helper, make_cache_key
from tests import utils

logger = logging.getLogger(__name__)


def test_cache_last_build(app_client, redis_cache, user1):
    valid_workflow = 'sort-and-change-case'
    assert helper.size() == 0, "Cache should be empty"
    _, workflow = utils.pick_and_register_workflow(user1, valid_workflow)
    assert workflow, "Workflow should be set"
    assert len(workflow.test_suites) > 0, "The workflow should have at least one suite"
    suite: models.TestSuite = workflow.test_suites[0]
    assert len(suite.test_instances) > 0, "The suite should have at least one test instance"
    instance: models.TestInstance = suite.test_instances[0]

    last_build_key = make_cache_key(instance.get_last_test_build)
    assert instance.cache.get(last_build_key) is None, "Cache should be empty"
    build = instance.last_test_build
    assert build, "Last build should not be empty"
    cached_build = instance.cache.get(last_build_key)
    assert cached_build is not None, "Cache should not be empty"
    assert build == cached_build, "Build should be equal to the cached build"

    instance.get_test_builds = MagicMock(return_value=None)

    build = instance.last_test_build
    assert build, "Last build should not be empty"
    assert instance.get_test_builds.assert_not_called, "instance.get_test_builds should not be used"
    assert build == cached_build, "Build should be equal to the cached build"


def test_cache_test_builds(app_client, redis_cache, user1):
    valid_workflow = 'sort-and-change-case'
    assert helper.size() == 0, "Cache should be empty"
    _, workflow = utils.pick_and_register_workflow(user1, valid_workflow)
    assert workflow, "Workflow should be set"
    assert len(workflow.test_suites) > 0, "The workflow should have at least one suite"
    suite: models.TestSuite = workflow.test_suites[0]
    assert len(suite.test_instances) > 0, "The suite should have at least one test instance"
    instance: models.TestInstance = suite.test_instances[0]

    limit = 10
    cache_key = make_cache_key(instance.get_test_builds, limit=limit)
    assert instance.cache.get(cache_key) is None, "Cache should be empty"
    builds = instance.get_test_builds(limit=limit)
    assert builds and len(builds) > 0, "Invalid number of builds"

    cached_builds = instance.cache.get(cache_key)
    assert cached_builds is not None and len(cached_builds) > 0, "Cache should not be empty"
    assert len(builds) == len(cached_builds), "Unexpected number of cached builds"

    instance.testing_service.get_test_builds = MagicMock(return_value=None)
    builds = instance.get_test_builds(limit=limit)
    assert builds and len(builds) > 0, "Invalid number of builds"
    assert instance.testing_service.get_test_builds.assert_not_called, "instance.get_test_builds should not be used"
    assert len(builds) == len(cached_builds), "Unexpected number of cached builds"

    limit = 20
    cache_key = instance._get_cache_key_test_builds(limit=limit)
    assert instance.cache.get(cache_key) is None, "Cache should be empty"
