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

from __future__ import annotations

import functools
import logging
import os

import redis_lock
from flask.app import Flask
from flask_caching import Cache
from flask_caching.backends.nullcache import NullCache

# Set prefix
CACHE_PREFIX = "flask_cache"


class Timeout:
    # Set default timeouts
    NONE = 0
    DEFAULT = os.environ.get('CACHE_DEFAULT_TIMEOUT', 60)
    REQUEST = os.environ.get('CACHE_REQUEST_TIMEOUT', 300)
    SESSION = os.environ.get('CACHE_SESSION_TIMEOUT', 600)
    BUILDS = os.environ.get('CACHE_SESSION_TIMEOUT', 84600)


# Set module logger
logger = logging.getLogger(__name__)

# Instantiate cache manager
cache = Cache()


def init_cache(app: Flask):
    cache_type = app.config.get(
        'CACHE_TYPE',
        'flask_caching.backends.simplecache.SimpleCache'
    )
    logger.debug("Cache type detected: %s", cache_type)
    if cache_type == 'flask_caching.backends.rediscache.RedisCache':
        logger.debug("Configuring cache...")
        app.config.setdefault('CACHE_REDIS_HOST', os.environ.get('REDIS_HOST', 'redis'))
        app.config.setdefault('CACHE_REDIS_PORT', os.environ.get('REDIS_PORT_NUMBER', 6379))
        app.config.setdefault('CACHE_REDIS_PASSWORD', os.environ.get('REDIS_PASSWORD', ''))
        app.config.setdefault('CACHE_REDIS_DB', int(os.environ.get('CACHE_REDIS_DB', 0)))
        app.config.setdefault('CACHE_REDIS_URL', "redis://:{0}@{1}:{2}/{3}".format(
            app.config.get('CACHE_REDIS_PASSWORD'),
            app.config.get('CACHE_REDIS_HOST'),
            app.config.get('CACHE_REDIS_PORT'),
            app.config.get('CACHE_REDIS_DB')
        ))
        logger.debug("RedisCache connection url: %s", app.config.get('CACHE_REDIS_URL'))
    cache.init_app(app)
    logger.debug(f"Cache initialised (type: {cache_type})")


class CacheMixin(object):

    _helper: CacheHelper = None

    @property
    def cache(self) -> CacheHelper:
        if self._helper is None:
            self._helper = CacheHelper()
        return self._helper


class CacheHelper(object):

    # Enable/Disable cache
    cache_enabled = True
    # Ignore cache values even if cache is enabled
    ignore_cache_values = False

    @staticmethod
    def redis_client():
        try:
            return cache.cache._read_clients
        except Exception:
            return None

    @staticmethod
    def size():
        return len(cache.get_dict())

    @staticmethod
    def to_dict():
        return cache.get_dict()

    @staticmethod
    def lock(key: str):
        return redis_lock.Lock(cache.cache._read_clients, key)

    def set(self, key: str, value, timeout: int = Timeout.NONE):
        val = None
        if not isinstance(cache.cache, NullCache):
            if key is not None and self.cache_enabled:
                lock = self.lock(key)
                if lock.acquire(blocking=True):
                    try:
                        val = cache.get(key)
                        if not val:
                            cache.set(key, value, timeout=timeout)
                    finally:
                        lock.release()
        return val

    def get(self, key: str):
        return cache.get(key) \
            if not isinstance(cache.cache, NullCache) \
            and self.cache_enabled \
            and not self.ignore_cache_values \
            else None

    @classmethod
    def delete_keys(cls, pattern: str):
        redis = cls.redis_client()
        logger.debug(f"Deleting keys by pattern: {pattern}")
        for key in redis.scan_iter(f"{CACHE_PREFIX}{pattern}"):
            logger.debug("Delete key: %r", key)
            redis.delete(key)


# global cache helper instance
helper: CacheHelper = CacheHelper()


def _make_key(func=None, *args, **kwargs) -> str:
    from lifemonitor.auth import current_registry, current_user
    logger.debug("Cache arguments: %r", args)
    logger.debug("Caghe kwargs: %r", kwargs)
    result = ""
    if current_user and not current_user.is_anonymous:
        result += "{}-{}_".format(current_user.username, current_user.id)
    if current_registry:
        result += "{}_".format(current_registry.uuid)
    if func:
        result += func if isinstance(func, str) else func.__name__ if callable(func) else str(func)
    if args:
        result += "_" + "-".join([str(_) for _ in args])
    if kwargs:
        result += "_" + "-".join([f"{str(k)}={str(v)}" for k, v in kwargs.items()])
    logger.debug("Calculated key: %r", result)
    return result


def clear_cache(func=None, *args, **kwargs):
    try:
        if func:
            key = _make_key(func)
            helper.delete_keys(f"{key}*")
            if args or kwargs:
                key = _make_key(func, *args, **kwargs)
                helper.delete_keys(f"{key}*")
        else:
            key = _make_key()
            helper.delete_keys(f"{key}*")
    except Exception as e:
        logger.error("Error deleting cache: %r", e)


def cached(timeout=Timeout.REQUEST, unless=False):
    def decorator(function):

        @functools.wraps(function)
        def wrapper(*args, **kwargs):
            logger.debug("Function: %r", str(function.__name__))
            logger.debug("Cache arguments: %r", args)
            logger.debug("Caghe kwargs: %r", kwargs)
            key = _make_key(function.__name__, *args, **kwargs)
            logger.debug("Calculated key: %r", key)
            result = helper.get(key)
            if result is None:
                logger.debug(f"Getting value from the actual function for key {key}...")
                result = function(*args, **kwargs)
                helper.set(key, result, timeout=timeout)
            else:
                logger.debug(f"Reusing value from cache key '{key}'...")
            return result

        return wrapper
    return decorator
