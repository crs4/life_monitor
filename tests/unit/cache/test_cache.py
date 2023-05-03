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

import logging
import threading
from multiprocessing import Manager, Process
from time import sleep
from unittest.mock import MagicMock

import pytest

import lifemonitor.api.models as models
from lifemonitor.cache import (IllegalStateException, Timeout, cache,
                               init_cache, make_cache_key)
from tests import utils
from tests.utils import SerializableMock

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


def setup_test_cache_last_build_update(app_context, redis_cache, user1):
    valid_workflow = 'sort-and-change-case'
    logger.debug("Cache content: %r", cache.keys)
    cache.clear()
    assert cache.size() == 0, "Cache should be empty"
    _, w = utils.pick_and_register_workflow(user1, valid_workflow)
    assert w, "Workflow should be set"
    return w


def test_cache_last_build_update(app_context, redis_cache, user1):
    w = setup_test_cache_last_build_update(app_context, redis_cache, user1)
    cache.reset_locks()
    sleep(2)
    cache_last_build_update(app_context.app, w, user1, check_cache_size=True)


def cache_last_build_update(app, w, user1, check_cache_size=True, index=0,
                            multithreaded=False, results=None):
    transactions = []
    logger.debug("Params of thread %r", index)
    logger.debug("%r %r %r %r", check_cache_size, index, multithreaded, results)
    if not multithreaded:
        assert len(cache.backend.keys("lock*")) == 0, "No lock should be set"
    with app.app_context():
        transaction_keys = None
        with cache.transaction(f"T{index}") as t:
            logger.debug("Current transaction: %r", t)
            logger.debug("Current workflow: %r", w)
            transactions.append(t)

            assert cache.get_current_transaction() == t, "Unexpected transaction"
            for s in w.test_suites:
                logger.info("[t#%r] Updating workflow (): %r", index, w)
                for i in s.test_instances:
                    get_test_builds_method = i.testing_service.get_test_builds
                    builds_data = i.testing_service.get_test_builds(i)
                    i.testing_service.get_test_builds = SerializableMock()
                    i.testing_service.get_test_builds.return_value = builds_data

                    assert cache.get_current_transaction() == t, "Unexpected transaction"
                    assert i.cache.get_current_transaction() == t, "Unexpected transaction"

                    cache_key = make_cache_key(i.get_test_builds, client_scope=False, args=[i], kwargs={'limit': 10})
                    logger.debug("The cache key: %r", cache_key)

                    #############################################################################
                    # latest builds (first call)
                    #############################################################################
                    logger.debug("\n\nGetting latest builds (first call)...")
                    builds = i.get_test_builds(limit=10)
                    logger.debug("Getting latest builds (first call): %r\n", builds)
                    assert t.has(cache_key), "The key should be in the current transaction"
                    cache_size = cache.size()
                    logger.debug("Current cache size: %r", cache_size)
                    assert i.cache.get_current_transaction() == t, "Unexpected transaction"
                    # check cache
                    if not multithreaded:
                        i.testing_service.get_test_builds.assert_called_once(), "i.testing_service.get_test_builds should be called once"
                        logger.debug(f"Checking if key {cache_key} is in cache...")
                        assert not cache.has(cache_key), "The key should not be in cache"

                    #############################################################################
                    # latest builds (second call)
                    #############################################################################
                    logger.debug("\n\nGetting latest builds (second call)...")
                    builds = i.get_test_builds(limit=10)
                    logger.debug("Getting latest builds (second call): %r\n", builds)
                    assert i.cache.get_current_transaction() == t, "Unexpected transaction"
                    assert t.has(cache_key), "The key should be in the current transaction"
                    if not multithreaded:
                        i.testing_service.get_test_builds.assert_called_once(), "i.testing_service.get_test_builds should be called once"
                        logger.debug(f"Checking if key {cache_key} is in cache...")
                        assert not cache.has(cache_key), "The key should not be in cache"
                    if check_cache_size:
                        assert cache.size() == cache_size, "Unexpected cache size"

                    #############################################################################
                    # latest builds (third call)
                    #############################################################################
                    logger.debug("\n\nGetting latest builds (third call)...")
                    builds = i.get_test_builds(limit=10)
                    logger.debug("Getting latest builds (third call): %r\n", builds)
                    assert i.cache.get_current_transaction() == t, "Unexpected transaction"
                    assert t.has(cache_key), "The key should be in the current transaction"
                    if not multithreaded:
                        i.testing_service.get_test_builds.assert_called_once(), "i.testing_service.get_test_builds should be called once"
                        logger.debug(f"Checking if key {cache_key} is in cache...")
                        assert not cache.has(cache_key), "The key should not be in cache"
                    if check_cache_size:
                        assert cache.size() == cache_size, "Unexpected cache size"

                    #############################################################################
                    # Check builds
                    #############################################################################
                    logger.debug("\n\nPreparing data to test builds...")
                    b_data = []
                    for b in builds:
                        b_data.append(i.testing_service.get_test_build(i, b.id))
                    logger.debug("\n\nPreparing data to test builds... DONE")

                    assert len(b_data) == 4, "Unexpected number of builds"

                    logger.debug("\n\nChecking test builds...")
                    get_test_build_method = i.testing_service.get_test_build

                    for count in range(0, len(b_data)):
                        b = b_data[count]
                        i.testing_service.get_test_build = SerializableMock()
                        i.testing_service.get_test_build.return_value = b

                        cache_key = make_cache_key(i.get_test_build, client_scope=False, args=[i, b.id])

                    # first call #############################################################
                        logger.debug("\n\nChecking build (first call): buildID=%r", b.id)
                        logger.debug("Build data: %r", i.get_test_build(b.id))
                        assert t.has(cache_key), "The key should be in the current transaction"
                        if not multithreaded:
                            i.testing_service.get_test_build.call_count == count + 1, "i.testing_service.get_test_build should be called once"
                            logger.debug(f"Checking if key {cache_key} is in cache...")
                            assert not cache.has(cache_key), "The key should not be in cache"
                        cache_size = cache.size()
                        logger.debug("Current cache size: %r", cache_size)

                    # second call #############################################################
                        logger.debug("\n\nChecking build (second call): buildID=%r", b.id)
                        logger.debug("Build data: %r", i.get_test_build(b.id))
                        assert t.has(cache_key), "The key should be in the current transaction"
                        if not multithreaded:
                            i.testing_service.get_test_build.call_count == count + 1, "i.testing_service.get_test_build should be called once"
                            logger.debug(f"Checking if key {cache_key} is in cache...")
                            assert not cache.has(cache_key), "The key should not be in cache"
                        if check_cache_size:
                            assert cache.size() == cache_size, "Unexpected cache size"
                    # third call #############################################################
                        logger.debug("\n\nChecking build (third call): buildID=%r", b.id)
                        logger.debug("Build data: %r", i.get_test_build(b.id))
                        assert t.has(cache_key), "The key should be in the current transaction"
                        if not multithreaded:
                            i.testing_service.get_test_build.call_count == count + 1, "i.testing_service.get_test_build should be called once"
                            logger.debug(f"Checking if key {cache_key} is in cache...")
                            assert not cache.has(cache_key), "The key should not be in cache"
                        if check_cache_size:
                            assert cache.size() == cache_size, "Unexpected cache size"

                    # check last test build
                    logger.debug("\n\nGetting latest build: %r", i.last_test_build)
                    if not multithreaded:
                        i.testing_service.get_test_builds.assert_called_once(), "i.testing_service.get_test_builds should be called once"
                    logger.debug("\n\nGetting latest build... DONE\n\n")

                    # restore original method
                    i.testing_service.get_test_build = get_test_build_method
                    i.testing_service.get_test_builds = get_test_builds_method

                    ############################################################################
                    # check latest build
                    ############################################################################
                    logger.debug("\n\nGetting latest build: %r", i.last_test_build)
                    if check_cache_size:
                        assert cache.size() == cache_size, "Unexpected cache size"

        # check transactions
        transaction_keys = t.keys()
        logger.debug("Transaction keys (# %r): %r", len(transaction_keys), transaction_keys)
        assert len(transaction_keys) == t.size(), "Unexpected transaction size"

        # check the cache after the transaction is completed
        if check_cache_size:
            cache_size = cache.size()
            assert len(transaction_keys) + 1 == cache_size, "Unpexpected cache size: it should be equal to the transaction size"
        sleep(2)
        assert cache.size() > 0, "Cache should not be empty"
        logger.debug(cache.keys())

        # prepare return value
        return_value = []
        for tr in transactions:
            return_value.append({
                'transaction': str(tr),
                'keys': tr.keys()
            })
        if not multithreaded:
            assert len(cache.backend.keys("lock*")) == 0, "No lock should be set"
        else:
            if results:
                assert results, "Results should not be none"
                results[index]['result'].extend(return_value)
        logger.debug("Return value: %r", return_value)
        return return_value


def test_cache_task_last_build(app_context, redis_cache, user1):
    valid_workflow = 'sort-and-change-case'
    logger.debug("Cache content: %r", cache.keys)
    cache.clear()
    assert cache.size() == 0, "Cache should be empty"
    _, workflow = utils.pick_and_register_workflow(user1, valid_workflow)
    assert workflow, "Workflow should be set"

    from lifemonitor.tasks.jobs.builds import check_last_build
    check_last_build()

    sleep(2)
    assert cache.size() > 0, "Cache should not be empty"
    logger.debug(cache.keys())
    assert len(cache.backend.keys("lock*")) == 0, "No lock should be set"


def check_results(results):
    logger.debug("\n\n\nResults: %r", results)
    assert len(cache.backend.keys(pattern="locks*")) == 0, "Locks should not be in cache"
    for i in range(0, len(results)):
        if i == len(results) - 1:
            break
        p1 = results[i]
        p2 = results[i + 1]
        r1 = p1['result']
        r2 = p2['result']
        processes = f"'{p1['index']}' and '{p2['index']}'"
        logger.debug(f"Checking process/thread {processes}")
        logger.debug("Number of transactions: %r => %r ||| %r => %r", p1['index'], len(r1), p2['index'], len(r2))
        assert len(r1) == len(r2), f"Process/thread {processes} should have the same number of transactions"
        for tdx in range(0, len(r1)):
            logger.debug("Checking transactions %r and %r",
                         r1[tdx]['transaction'], r2[tdx]['transaction'])
            assert len(r1[tdx]['keys']) == len(r2[tdx]['keys']), \
                f"Transactions {r1[tdx]['transaction']} and {r2[tdx]['transaction']} should have the same number of keys"
    logger.debug("\n\nChecking Results DONE\n\n\n",)


def test_cache_last_build_update_multi_thread(app_context, redis_cache, user1):
    # set up a workflow
    w = setup_test_cache_last_build_update(app_context, redis_cache, user1)
    logger.debug("Workflow %r", w)
    # set up threads
    results = []
    number_of_threads = 3
    for index in range(number_of_threads):
        t = threading.Thread(
            target=cache_last_build_update, name=f"T{index}", args=(app_context.app, w, user1),
            kwargs={
                "check_cache_size": False,
                "index": index,
                "multithreaded": True,
                "results": results})
        results.append({
            't': t,
            'index': str(index),
            "result": []
        })
        t.start()
        sleep(2)

    # wait for results
    for tdata in results:
        t = tdata['t']
        t.join()
    # check results
    sleep(2)
    check_results(results)


def test_cache_last_build_update_multi_process(app_context, redis_cache, user1):
    # set up a workflow
    w = setup_test_cache_last_build_update(app_context, redis_cache, user1)
    # set up processes
    processes = 3
    results = []
    manager = Manager()
    for index in range(processes):
        p = Process(target=cache_last_build_update, args=(app_context.app, w, user1),
                    kwargs={"check_cache_size": False,
                            "index": index,
                            "multithreaded": True,
                            "results": results})
        results.append({
            'p': p,
            'index': str(index),
            'result': manager.list()
        })
        p.start()
        sleep(1)
    # wait for results
    for pdata in results:
        p = pdata['p']
        p.join()
    # check results
    sleep(4)
    check_results(results)


def cache_transaction(transaction, index, name, results):
    sleep(5)
    logger.debug(f"Cache transaction: {name}")
    with cache.transaction(f"T-{index}") as t:
        current_transaction = cache.get_current_transaction()
        logger.debug("Current transaction: %r", current_transaction)
        assert current_transaction != transaction, "Unexpected transaction: transaction should be defferent from that on the main process"
        assert t == current_transaction, "Unexpected transaction"

        with cache.transaction() as tx:
            assert tx == t, "Unexpected transaction: it should be the same started in this thread"

            key = "TEST"
            result = transaction.get(key)
            if result is None:
                logger.debug(f"Value {key} not set in cache...")
                with tx.lock(key, blocking=True, timeout=Timeout.NONE):
                    result = transaction.get(key)
                    if not result:
                        logger.debug("Cache empty: getting value from the actual function...")
                        sleep(5)
                        result = f"result-of-index: {index}"
                        if index != -1:
                            result = cache_transaction(transaction, -1, f"{index}-NONE", results)
                        unless = None
                        logger.debug("Checking unless function: %r", unless)
                        if unless is None or unless is False or callable(unless) and not unless(result):
                            transaction.set(key, result, timeout=Timeout.NONE)
                        else:
                            logger.debug("Don't set value in cache due to unless=%r", "None" if unless is None else "True")


def test_cache_transaction_multi_thread(app_context, redis_cache, user1):
    # set up threads
    logger.debug("Test cache transaction...")
    number_of_threads = 4
    results = []
    with cache.transaction() as transaction:
        print("The transaction: %r" % transaction)

        for index in range(number_of_threads):
            t = threading.Thread(
                target=cache_transaction, name=f"T{index}", args=(transaction, index, f"{index}", results),
                kwargs={})
            results.append({
                "t": t,
                "result": []
            })
            t.start()
        # wait for results
        for tdata in results:
            t = tdata['t']
            t.join()
        # check results
        sleep(2)
        # check_results(results)

        logger.debug("Test cache transaction... DONE")
