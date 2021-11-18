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
import pytest
from lifemonitor.cache import (IllegalStateException, cache, init_cache,
                               make_cache_key)
from tests import utils
from tests.unit.test_utils import SerializableMock

logger = logging.getLogger(__name__)


@pytest.mark.parametrize("app_settings", [(False, {"CACHE_TYPE": "Flask_caching.backends.simplecache.SimpleCache"})], indirect=True)
def test_cache_config(app_settings, app_context):
    logger.debug("App settings: %r", app_settings)
    app = app_context.app
    logger.debug("App: %r", app)
    config = app.config
    logger.debug("Config: %r", config)
    assert config.get("CACHE_TYPE") == "Flask_caching.backends.simplecache.SimpleCache", "Unexpected cache type on app config"
    init_cache(app)
    assert cache.cache_enabled is False, "Cache should be disabled"
    with pytest.raises(IllegalStateException):
        cache.backend


def test_cache_transaction_setup(app_context, redis_cache):
    cache.clear()
    key = "test"
    value = "test"
    assert cache.size() == 0, "Cache should be empty"
    with cache.transaction("test") as t:
        assert t.size() == 0, "Unexpected transaction size: it should be empty"
        t.set(key, value)
        assert t.size() == 1, "Unexpected transaction size: it should be equal to 1"
        assert t.has(key), f"key '{key}' should be set in the current transaction"
        assert cache.size() == 0, "Cache should be empty"

    assert cache.size() == 1, "Cache should contain one element"
    assert cache.has(key), f"key '{key}' should be in cache"
    assert cache.get_current_transaction() is None, "Unexpected transaction"


def test_cache_timeout(app_context, redis_cache):
    cache.clear()
    assert cache.size() == 0, "Cache should be empty"
    key = "test5"
    value = 1024
    timeout = 5
    cache.set(key, value, timeout=timeout)
    assert cache.size() == 1, "Cache should not be empty"
    assert cache.has(key) is True, f"Key {key} should be in cache"
    sleep(5)
    assert cache.size() == 0, "Cache should be empty"
    assert cache.has(key) is False, f"Key {key} should not be in cache after {timeout} secs"


def test_cache_last_build(app_context, redis_cache, user1):
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


def test_cache_test_builds(app_context, redis_cache, user1):
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


def test_cache_last_build_update(app_context, redis_cache, user1):
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
                i.testing_service.get_test_builds = SerializableMock()
                i.testing_service.get_test_builds.return_value = builds_data
                transaction_keys = None
                with i.cache.transaction(str(i)) as t:
                    assert i.cache.get_current_transaction() == t, "Unexpected transaction"

                    cache_key = make_cache_key(i.get_test_builds, client_scope=False, args=[i])
                    logger.debug("The cache key: %r", cache_key)
                    assert not cache.has(cache_key), "The key should not be in cache"

                    logger.debug("\n\nGetting latest builds (first call)...")
                    builds = i.get_test_builds()
                    logger.debug("Getting latest builds (first call): %r\n", builds)
                    i.testing_service.get_test_builds.assert_called_once(), "i.testing_service.get_test_builds should be called once"
                    logger.debug(f"Checking if key {cache_key} is in cache...")
                    assert cache.has(cache_key), "The key should be in cache"
                    cache_size = cache.size()
                    logger.debug("Current cache size: %r", cache_size)
                    assert i.cache.get_current_transaction() == t, "Unexpected transaction"

                    logger.debug("\n\nGetting latest builds (second call)...")
                    builds = i.get_test_builds()
                    logger.debug("Getting latest builds (second call): %r\n", builds)
                    i.testing_service.get_test_builds.assert_called_once(), "i.testing_service.get_test_builds should be called once"
                    logger.debug(f"Checking if key {cache_key} is in cache...")
                    assert cache.has(cache_key), "The key should be in cache"
                    assert cache.size() == cache_size, "Unexpected cache size"
                    assert i.cache.get_current_transaction() == t, "Unexpected transaction"

                    logger.debug("\n\nGetting latest builds (third call)...")
                    builds = i.get_test_builds()
                    logger.debug("Getting latest builds (third call): %r\n", builds)
                    i.testing_service.get_test_builds.assert_called_once(), "i.testing_service.get_test_builds should be called once"
                    logger.debug(f"Checking if key {cache_key} is in cache...")
                    assert cache.has(cache_key), "The key should be in cache"
                    assert cache.size() == cache_size, "Unexpected cache size"
                    assert i.cache.get_current_transaction() == t, "Unexpected transaction"

                    logger.debug("\n\nPreparing data to test builds...")
                    b_data = []
                    for b in builds:
                        b_data.append(i.testing_service.get_test_build(i, b.id))
                    logger.debug("\n\nPreparing data to test builds... DONE")

                    logger.debug("\n\nChecking test builds...")
                    i.testing_service.get_test_build = SerializableMock()
                    for count in range(0, len(b_data)):
                        b = b_data[count]
                        i.testing_service.get_test_build.return_value = b

                        cache_key = make_cache_key(i.get_test_build, client_scope=False, args=[i, b.id])

                        logger.debug("\n\nChecking build (first call): buildID=%r", b.id)
                        logger.debug("Build data: %r", i.get_test_build(b.id))
                        i.testing_service.get_test_build.call_count == count + 1, "i.testing_service.get_test_build should be called once"
                        logger.debug(f"Checking if key {cache_key} is in cache...")
                        assert cache.has(cache_key), f"The key {cache_key} should be in cache"
                        cache_size = cache.size()
                        logger.debug("Current cache size: %r", cache_size)

                        logger.debug("\n\nChecking build (second call): buildID=%r", b.id)
                        logger.debug("Build data: %r", i.get_test_build(b.id))
                        i.testing_service.get_test_build.call_count == count + 1, "i.testing_service.get_test_build should be called once"
                        logger.debug(f"Checking if key {cache_key} is in cache...")
                        assert cache.has(cache_key), f"The key {cache_key} should be in cache"
                        assert cache.size() == cache_size, "Unexpected cache size"

                        logger.debug("\n\nChecking build (third call): buildID=%r", b.id)
                        logger.debug("Build data: %r", i.get_test_build(b.id))
                        i.testing_service.get_test_build.call_count == count + 1, "i.testing_service.get_test_build should be called once"
                        logger.debug(f"Checking if key {cache_key} is in cache...")
                        assert cache.has(cache_key), f"The key {cache_key} should be in cache"
                        assert cache.size() == cache_size, "Unexpected cache size"

                    logger.debug("\n\nGetting latest build: %r", i.last_test_build)
                    i.testing_service.get_test_builds.assert_called_once(), "i.testing_service.get_test_builds should be called once"
                    logger.debug("\n\nGetting latest build... DONE\n\n")

                    transaction_keys = t.keys()
                    logger.debug("Transaction keys (# %r): %r", len(transaction_keys), transaction_keys)
                    assert len(transaction_keys) == t.size(), "Unexpected transaction size"

                # check the cache after the transaction is completed
                cache_size = cache.size()
                assert len(transaction_keys) == cache_size, "Unpexpected cache size: it should be equal to the transaction size"

                # check latest build
                logger.debug("\n\nGetting latest build: %r", i.last_test_build)
                assert cache.size() == cache_size, "Unexpected cache size"

    except Exception as e:
        logger.error("Error when executing task 'check_last_build': %s", str(e))
        if logger.isEnabledFor(logging.DEBUG):
            logger.exception(e)

    sleep(2)
    assert cache.size() > 0, "Cache should not be empty"
    logger.debug(cache.keys())
    assert len(cache.backend.keys("lock*")) == 0, "No lock should be set"


def test_cache_task_last_build(app_context, redis_cache, user1):
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
