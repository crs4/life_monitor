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
from time import sleep
from unittest.mock import MagicMock

import lifemonitor.api.models as models
from lifemonitor.cache import cache, make_cache_key
from tests import utils
from tests.unit.test_utils import PickableMock

logger = logging.getLogger(__name__)


def test_cache_last_build(app_client, redis_cache, user1):
    valid_workflow = 'sort-and-change-case'
    cache.clear()
    assert cache.size() == 0, "Cache should be empty"
    _, workflow = utils.pick_and_register_workflow(user1, valid_workflow)
    assert workflow, "Workflow should be set"
    assert len(workflow.test_suites) > 0, "The workflow should have at least one suite"
    suite: models.TestSuite = workflow.test_suites[0]
    assert len(suite.test_instances) > 0, "The suite should have at least one test instance"
    instance: models.TestInstance = suite.test_instances[0]

    last_build_key = make_cache_key(instance.get_last_test_build, client_scope=False, args=(instance,))
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
    cache.clear()
    assert cache.size() == 0, "Cache should be empty"
    _, workflow = utils.pick_and_register_workflow(user1, valid_workflow)
    assert workflow, "Workflow should be set"
    assert len(workflow.test_suites) > 0, "The workflow should have at least one suite"
    suite: models.TestSuite = workflow.test_suites[0]
    assert len(suite.test_instances) > 0, "The suite should have at least one test instance"
    instance: models.TestInstance = suite.test_instances[0]

    limit = 10
    cache_key = make_cache_key(instance.get_test_builds, client_scope=False, args=(instance,), kwargs={"limit": limit})
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
    cache_key = make_cache_key(instance.get_test_builds, client_scope=False, args=(instance,), kwargs={"limit": limit})
    assert instance.cache.get(cache_key) is None, "Cache should be empty"


def test_cache_last_build_update(app_client, redis_cache, user1):
    valid_workflow = 'sort-and-change-case'
    logger.debug("Cache content: %r", cache.keys)
    cache.clear()
    assert cache.size() == 0, "Cache should be empty"
    _, w = utils.pick_and_register_workflow(user1, valid_workflow)
    assert w, "Workflow should be set"

    try:
        for s in w.test_suites:
            logger.info("Updating workflow: %r", w)
            for i in s.test_instances:
                builds_data = i.testing_service.get_test_builds(i)
                i.testing_service.get_test_builds = PickableMock()
                i.testing_service.get_test_builds.return_value = builds_data
                with i.cache.transaction(str(i)) as t:
                    assert i.cache.get_current_transaction() == t, "Unexpected transaction"

                    cache_key = make_cache_key(i.get_test_builds, client_scope=False, args=[i])
                    logger.debug("The cache key: %r", cache_key)
                    assert not cache.has(cache_key), "The key should not be in cache"

                    logger.debug("\n\nGetting latest builds (first call)...")
                    builds = i.get_test_builds()
                    logger.debug("Getting latest builds (first call): %r\n", builds)
                    i.testing_service.get_test_builds.assert_called_once(), "i.testing_service.get_test_builds should be called once"
                    assert cache.has(cache_key), "The key should be in cache"
                    cache_size = cache.size()
                    logger.debug("Current cache size: %r", cache_size)
                    assert i.cache.get_current_transaction() == t, "Unexpected transaction"

                    logger.debug("\n\nGetting latest builds (second call)...")
                    builds = i.get_test_builds()
                    logger.debug("Getting latest builds (second call): %r\n", builds)
                    i.testing_service.get_test_builds.assert_called_once(), "i.testing_service.get_test_builds should be called once"
                    assert cache.has(cache_key), "The key should be in cache"
                    assert cache.size() == cache_size, "Unexpected cache size"
                    assert i.cache.get_current_transaction() == t, "Unexpected transaction"

                    logger.debug("\n\nGetting latest builds (third call)...")
                    builds = i.get_test_builds()
                    logger.debug("Getting latest builds (third call): %r\n", builds)
                    i.testing_service.get_test_builds.assert_called_once(), "i.testing_service.get_test_builds should be called once"
                    assert cache.has(cache_key), "The key should be in cache"
                    assert cache.size() == cache_size, "Unexpected cache size"
                    assert i.cache.get_current_transaction() == t, "Unexpected transaction"

                    b_data = []
                    for b in builds:
                        b_data.append(i.testing_service.get_test_build(i, b.id))

                    i.testing_service.get_test_build = PickableMock()
                    for count in range(0, len(b_data)):
                        b = b_data[count]
                        i.testing_service.get_test_build.return_value = b

                        cache_key = make_cache_key(i.get_test_build, client_scope=False, args=[i, b.id])

                        logger.debug("\n\nChecking build (first call): %r", i.get_test_build(b.id))
                        i.testing_service.get_test_build.call_count == count + 1, "i.testing_service.get_test_build should be called once"
                        assert cache.has(cache_key), f"The key {cache_key} should be in cache"
                        cache_size = cache.size()
                        logger.debug("Current cache size: %r", cache_size)

                        logger.debug("\n\nChecking build (second call): %r", i.get_test_build(b.id))
                        i.testing_service.get_test_build.call_count == count + 1, "i.testing_service.get_test_build should be called once"
                        assert cache.has(cache_key), f"The key {cache_key} should be in cache"
                        assert cache.size() == cache_size, "Unexpected cache size"

                        logger.debug("\n\nChecking build (third call): %r", i.get_test_build(b.id))
                        i.testing_service.get_test_build.call_count == count + 1, "i.testing_service.get_test_build should be called once"
                        assert cache.has(cache_key), f"The key {cache_key} should be in cache"
                        assert cache.size() == cache_size, "Unexpected cache size"

                    logger.debug("\n\nGetting latest build: %r", i.last_test_build)
                    i.testing_service.get_test_builds.assert_called_once(), "i.testing_service.get_test_builds should be called once"
                    logger.debug("\n\nGetting latest build... DONE\n\n")

                logger.debug("\n\nGetting latest build: %r", i.last_test_build)

    except Exception as e:
        logger.error("Error when executing task 'check_last_build': %s", str(e))
        if logger.isEnabledFor(logging.DEBUG):
            logger.exception(e)

    sleep(2)
    assert cache.size() > 0, "Cache should not be empty"
    logger.debug(cache.keys())
    assert len(cache.backend.keys("lock*")) == 0, "No lock should be set"


def test_cache_task_last_build(app_client, redis_cache, user1):
    valid_workflow = 'sort-and-change-case'
    logger.debug("Cache content: %r", cache.keys)
    cache.clear()
    assert cache.size() == 0, "Cache should be empty"
    _, workflow = utils.pick_and_register_workflow(user1, valid_workflow)
    assert workflow, "Workflow should be set"

    from lifemonitor.tasks.tasks import check_last_build
    check_last_build()

    sleep(2)
    assert cache.size() > 0, "Cache should not be empty"
    logger.debug(cache.keys())
    assert len(cache.backend.keys("lock*")) == 0, "No lock should be set"
