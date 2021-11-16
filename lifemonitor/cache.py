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

import redis
import redis_lock
from flask import request
from flask.app import Flask
from flask_caching import Cache as FlaskCache
from flask_caching.backends.rediscache import RedisCache

# Set prefix
CACHE_PREFIX = "lifemonitor-api-cache:"


# Set module logger
logger = logging.getLogger(__name__)


def _get_timeout(name: str, default: int = 0, config=None) -> int:
    result = None
    if config is not None:
        try:
            result = config.get(name)
        except Exception as e:
            logger.debug(e)
    result = result or os.environ.get(name, default)
    logger.debug("Getting timeout %r: %r", name, result)
    return int(result)


def _get_timeout_key(n: str) -> str:
    return f"CACHE_{n}_TIMEOUT"


class Timeout:
    # Set default timeouts
    NONE = 0
    DEFAULT = _get_timeout(_get_timeout_key('DEFAULT'), default=300)
    REQUEST = _get_timeout(_get_timeout_key('REQUEST'), default=30)
    SESSION = _get_timeout(_get_timeout_key('SESSION'), default=3600)
    WORKFLOW = _get_timeout(_get_timeout_key('WORKFLOW'), default=1800)
    BUILD = _get_timeout(_get_timeout_key('BUILD'), default=300)

    @classmethod
    def update(cls, config):
        for t in ('DEFAULT', 'REQUEST', 'SESSION', 'BUILD', 'WORKFLOW'):
            try:
                key = _get_timeout_key(t)
                setattr(cls, key, _get_timeout(key, config=config))
            except Exception:
                logger.debug("Error when updating timeout %r", t)


class Cache(object):

    # Enable/Disable cache
    cache_enabled = True
    # Ignore cache values even if cache is enabled
    ignore_cache_values = False
    # Reference to the Flask cache manager
    __cache__ = None

    @classmethod
    def __get_flask_cache(cls):
        if cls.__cache__ is None:
            cls.__cache__ = FlaskCache()
        return cls.__cache__

    @classmethod
    def init_app(cls, app: Flask):
        cls.__get_flask_cache().init_app(app)

    def __init__(self, cache: FlaskCache = None) -> None:
        self._cache = cache or self.__get_flask_cache()

    @property
    def cache(self) -> RedisCache:
        return self._cache.cache

    @property
    def backend(self) -> redis.Redis:
        if isinstance(self.cache, RedisCache):
            return self.cache._read_clients
        logger.warning("No cache backend found")
        return None

    def size(self):
        return len(self.cache.get_dict())

    def to_dict(self):
        return self.cache.get_dict()

    def lock(self, key: str):
        logger.debug("Getting lock for key %r...", key)
        return redis_lock.Lock(self.backend, key) if self.backend else False

    def set(self, key: str, value, timeout: int = Timeout.NONE):
        if key is not None and self.cache_enabled and isinstance(self.cache, RedisCache):
            logger.debug("Setting cache value for key %r.... ", key)
            self.cache.set(key, value, timeout=timeout)

    def get(self, key: str):
        logger.debug("Getting value from cache...")
        return self.cache.get(key) \
            if isinstance(self.cache, RedisCache) \
            and self.cache_enabled \
            and not self.ignore_cache_values \
            and not cache.ignore_cache_values \
            else None

    def delete_keys(self, pattern: str, prefix: str = CACHE_PREFIX):
        logger.debug(f"Deleting keys by pattern: {pattern}")
        if isinstance(self.cache, RedisCache):
            logger.debug("Redis backend detected!")
            logger.debug(f"Pattern: {prefix}{pattern}")
            for key in self.backend.scan_iter(f"{prefix}{pattern}"):
                logger.debug("Delete key: %r", key)
                self.backend.delete(key)


# global cache instance
cache: Cache = Cache()


def init_cache(app: Flask):
    cache_type = app.config.get(
        'CACHE_TYPE',
        'flask_caching.backends.simplecache.SimpleCache'
    )
    logger.debug("Cache type detected: %s", cache_type)
    if cache_type == 'flask_caching.backends.rediscache.RedisCache':
        logger.debug("Configuring cache...")
        app.config.setdefault('CACHE_REDIS_HOST', os.environ.get('REDIS_HOST', '127.0.0.1'))
        app.config.setdefault('CACHE_REDIS_PORT', os.environ.get('REDIS_PORT_NUMBER', 6379))
        app.config.setdefault('CACHE_REDIS_PASSWORD', os.environ.get('REDIS_PASSWORD', 'foobar'))
        app.config.setdefault('CACHE_REDIS_DB', int(os.environ.get('CACHE_REDIS_DB', 0)))
        app.config.setdefault("CACHE_KEY_PREFIX", CACHE_PREFIX)
        app.config.setdefault('CACHE_REDIS_URL', "redis://:{0}@{1}:{2}/{3}".format(
            app.config.get('CACHE_REDIS_PASSWORD'),
            app.config.get('CACHE_REDIS_HOST'),
            app.config.get('CACHE_REDIS_PORT'),
            app.config.get('CACHE_REDIS_DB')
        ))
        logger.debug("RedisCache connection url: %s", app.config.get('CACHE_REDIS_URL'))
    cache.init_app(app)
    Timeout.update(app.config)
    logger.debug(f"Cache initialised (type: {cache_type})")


def make_cache_key(func=None, client_scope=True, args=None, kwargs=None) -> str:
    from lifemonitor.auth import current_registry, current_user

    hash_enabled = not logger.isEnabledFor(logging.DEBUG)
    fname = "" if func is None \
        else func if isinstance(func, str) \
        else f"{func.__module__}.{func.__name__}" if callable(func) else str(func)
    logger.debug("make_key func: %r", fname)
    logger.debug("make_key args: %r", args)
    logger.debug("make_key kwargs: %r", kwargs)
    logger.debug("make_key hash enabled: %r", hash_enabled)
    result = ""
    if client_scope:
        client_id = ""
        if current_user and not current_user.is_anonymous:
            client_id += "{}-{}_".format(current_user.username, current_user.id)
        if current_registry:
            client_id += "{}_".format(current_registry.uuid)
        if not current_registry and (not current_user or current_user.is_anonymous):
            client_id += "anonymous"
        if request:
            client_id += f"@{request.remote_addr}"
        result += f"{hash(client_id) if hash_enabled else client_id}::"
    if func:
        result += fname
    if args:
        args_str = "-".join([str(_) for _ in args])
        result += f"#{hash(args_str) if hash_enabled else args_str}"
    if kwargs:
        kwargs_str = "-".join([f"{k}={str(v)}" for k, v in kwargs.items()])
        result += f"#{hash(kwargs_str) if hash_enabled else kwargs_str}"
    logger.debug("make_key calculated key: %r", result)
    return result


def clear_cache(func=None, client_scope=True, prefix=CACHE_PREFIX, *args, **kwargs):
    try:
        if func:
            key = make_cache_key(func, client_scope)
            cache.delete_keys(f"{key}*")
            if args or kwargs:
                key = make_cache_key(func, client_scope=client_scope, args=args, kwargs=kwargs)
                cache.delete_keys(f"{key}*", prefix=prefix)
        else:
            key = make_cache_key(client_scope=client_scope)
            cache.delete_keys(f"{key}*", prefix=prefix)
    except Exception as e:
        logger.error("Error deleting cache: %r", e)


def cached(timeout=Timeout.REQUEST, client_scope=True, unless=None):
    def decorator(function):

        @functools.wraps(function)
        def wrapper(*args, **kwargs):
            logger.debug("Args: %r", args)
            logger.debug("KwArgs: %r", kwargs)
            obj: CacheMixin = args[0] if len(args) > 0 and isinstance(args[0], CacheMixin) else None
            logger.debug("Wrapping a method of a CacheMixin instance: %r", obj is not None)
            hc = cache if obj is None else obj.cache
            if hc.cache_enabled:
                key = make_cache_key(function, client_scope, args=args, kwargs=kwargs)
                result = hc.get(key)
                if result is None:
                    logger.debug(f"Value {key} not set in cache...")
                    if hc.backend:
                        lock = hc.lock(key)
                        if lock:
                            try:
                                if lock.acquire(blocking=True, timeout=timeout * 3 / 4):
                                    result = hc.get(key)
                                    if not result:
                                        logger.debug("Cache empty: getting value from the actual function...")
                                        result = function(*args, **kwargs)
                                        logger.debug("Checking unless function: %r", unless)
                                        if unless is None or unless is True or callable(unless) and not unless(result):
                                            hc.set(key, result, timeout=timeout)
                                        else:
                                            logger.debug("Don't set value in cache due to unless=%r", "None" if unless is None else "True")
                            finally:
                                try:
                                    lock.release()
                                except redis_lock.NotAcquired as e:
                                    logger.debug(e)
                    else:
                        logger.warning("Using unsupported cache backend: cache will not be used")
                        result = function(*args, **kwargs)
                else:
                    logger.debug(f"Reusing value from cache key '{key}'...")
            else:
                logger.debug("Cache disabled: getting value from the actual function...")
                result = function(*args, **kwargs)
            return result

        return wrapper
    return decorator


class CacheMixin(object):

    _helper: Cache = None

    @property
    def cache(self) -> Cache:
        if self._helper is None:
            self._helper = Cache()
        return self._helper
