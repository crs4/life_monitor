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


def _make_name(fname) -> str:
    from lifemonitor.auth import current_registry, current_user
    result = fname
    if current_user and not current_user.is_anonymous:
        result += "-{}-{}".format(current_user.username, current_user.id)
    if current_registry:
        result += "-{}".format(current_registry.uuid)
    logger.debug("Calculated function name: %r", result)

    return result


def clear_cache(func=None, *args, **kwargs):
    try:
        if func:
            cache.delete_memoized(func, *args, **kwargs)
        else:
            cache.clear()
    except Exception as e:
        logger.error("Error deleting cache: %r", e)


def cached(timeout=Timeout.REQUEST, unless=False):
    def decorator(function):

        @cache.memoize(timeout=timeout, unless=unless, make_name=_make_name)
        @functools.wraps(function)
        def wrapper(*args, **kwargs):
            logger.debug("Cache arguments: %r", args)
            logger.debug("Caghe kwargs: %r", kwargs)
            # wrap concrete function
            return function(*args, **kwargs)

        return wrapper
    return decorator


def cached_method(timeout=None, unless=False):
    def decorator(function):

        def unless_wrapper(func, obj, *args, **kwargs):
            f = getattr(obj, unless)
            return f(obj, func, *args, **kwargs)

        @cache.memoize(timeout=timeout, unless=unless_wrapper, make_name=_make_name)
        @functools.wraps(function)
        def wrapper(*args, **kwargs):
            logger.debug("Cache arguments: %r", args)
            logger.debug("Caghe kwargs: %r", kwargs)
            # wrap concrete function
            return function(*args, **kwargs)

        return wrapper
    return decorator


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
        return cache.get(key) if self.cache_enabled and not self.ignore_cache_values else None
