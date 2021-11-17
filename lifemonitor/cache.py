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
from contextlib import contextmanager

import redis
import redis_lock
from flask import request
from flask.app import Flask
from flask.globals import current_app
from flask_caching import Cache as FlaskCache
from flask_caching.backends.rediscache import RedisCache

# Set prefix
CACHE_PREFIX = "lifemonitor-api-cache:"


# Set module logger
logger = logging.getLogger(__name__)


def _get_timeout(name: str, default: int = 0, config=None) -> int:
    result = None
    try:
        config = current_app.config if config is None else config
        if config is not None:
            result = config.get(name)
    except Exception as e:
        logger.debug(e)
    result = result if result is not None else os.environ.get(name, default)
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
    def update(cls, config=None):
        for t in ('DEFAULT', 'REQUEST', 'SESSION', 'BUILD', 'WORKFLOW'):
            try:
                key = _get_timeout_key(t)
                setattr(cls, t, _get_timeout(key, config=config))
            except Exception:
                logger.debug("Error when updating timeout %r", t)


class IllegalStateException(RuntimeError):
    pass


class CacheTransaction(object):
    def __init__(self, cache: Cache):
        self.__cache__ = cache
        self.__locks__ = {}
        self.__closed__ = False

    def get_lock(blocking: bool = True, timeout: int = Timeout.REQUEST):
        pass

    def has_lock(self, lock: str) -> bool:
        return lock in self.__locks__

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        print("Exception has been handled")
        self.close()
        return True

    def close(self):
        if self.__closed__:
            logger.debug("Transaction already closed")
        else:
            logger.debug("Closing transaction")
            try:
                for k in list(self.__locks__.keys()):
                    logger.debug("Releasing lock %r", k)
                    l = self.__locks__.pop(k)
                    try:
                        l.release()
                    except redis_lock.NotAcquired as e:
                        logger.debug(e)
                logger.debug("All lock released")
                logger.debug("Transaction closed")
            finally:
                self.__closed__ = True


class Cache(object):

    # Enable/Disable cache
    cache_enabled = True
    # Ignore cache values even if cache is enabled
    _ignore_cache_values = False
    # Reference to the Flask cache manager
    __cache__ = None

    @classmethod
    def __get_flask_cache(cls) -> FlaskCache:
        if cls.__cache__ is None:
            cls.__cache__ = FlaskCache()
        return cls.__cache__

    @classmethod
    def init_app(cls, app: Flask):
        cls.__get_flask_cache().init_app(app)
        cls.reset_locks()

    def __init__(self, cache: FlaskCache = None, parent: Cache = None) -> None:
        self._cache = cache or self.__get_flask_cache()
        self._current_transaction = None
        self._parent = parent

    @property
    def parent(self) -> Cache:
        return self._parent

    @property
    def ignore_cache_values(self):
        return self._ignore_cache_values is True and \
            (self.parent and self.parent.ignore_cache_values is True)

    @ignore_cache_values.setter
    def ignore_cache_values(self, value: bool):
        self._ignore_cache_values = True if value is True else False

    @property
    def cache(self) -> RedisCache:
        return self.get_redis_cache(self._cache)

    @contextmanager
    def transaction(self, name) -> CacheTransaction:
        if self._current_transaction is not None:
            raise IllegalStateException("Transaction already started")
        t = CacheTransaction(self)
        if self.parent is not None:
            self.parent._current_transaction = t
        else:
            self._current_transaction = t
        try:
            yield t
        except Exception as e:
            logger.exception(e)
        finally:
            logger.debug("Finally closing transaction")
            try:
                t.close()
            except Exception as fe:
                logger.debug(fe)
            if self.parent is not None:
                self.parent._current_transaction = None
            else:
                self._current_transaction = None

    @property
    def backend(self) -> redis.Redis:
        return self.get_backend(self.cache)

    def get_current_transaction(self):
        if self._current_transaction is None and self.parent is not None:
            return self.parent.get_current_transaction()
        return self._current_transaction

    def keys(self, pattern: str = None):
        query = f"{CACHE_PREFIX}"
        if pattern is not None:
            query = f"{query}{pattern}"
        else:
            query = f"{query}*"
        return self.backend.keys(query)

    def size(self, pattern=None):
        return len(self.keys(pattern=pattern))

    def to_dict(self, pattern=None):
        return {k: self.backend.get(k) for k in self.keys(pattern=pattern)}

    @contextmanager
    def lock(self, key: str, blocking: bool = True,
             timeout: int = Timeout.REQUEST,
             expire=60, auto_renewal=True):
        logger.debug("Getting lock for key %r...", key)
        lock = redis_lock.Lock(self.backend, key, expire=expire, auto_renewal=auto_renewal)
        try:
            yield lock.acquire(blocking=blocking)
        finally:
            try:
                logger.debug("Auto release of lock for key=%s", key)
                transaction = self.get_current_transaction()
                if transaction is None:
                    logger.debug("No transaction in progress...")
                    lock.release()
                else:
                    logger.debug("Transaction %r in progress...", transaction)
                    transaction.__locks__[key] = lock
                    logger.debug("Added lock to transaction: %r", transaction.has_lock(key))
            except redis_lock.NotAcquired as e:
                logger.debug(e)

    def set(self, key: str, value, timeout: int = Timeout.NONE):
        if key is not None and self.cache_enabled:
            logger.debug("Setting cache value for key %r.... (timeout: %r)", key, timeout)
            self.cache.set(key, value, timeout=timeout)

    def has(self, key: str) -> bool:
        return self.get(key) is not None

    def _get_status(self) -> dict:
        return {
            "self": self,
            "enabled": self.cache_enabled,
            "ignore_values": self.ignore_cache_values,
            "current_transaction": self.get_current_transaction(),
            "transaction locks": self.get_current_transaction().__locks__ if self.get_current_transaction() else None
        }

    def get(self, key: str):
        logger.debug("Getting value from cache...")
        logger.debug("Cache status: %r", self._get_status())
        return self.cache.get(key) \
            if isinstance(self.cache, RedisCache) \
            and self.cache_enabled \
            and not self.ignore_cache_values \
            and (self.get_current_transaction() is None
                 or self.get_current_transaction().has_lock(key)) \
            else None

    def delete_keys(self, pattern: str, prefix: str = CACHE_PREFIX):
        logger.debug(f"Deleting keys by pattern: {pattern}")
        if isinstance(self.cache, RedisCache):
            logger.debug("Redis backend detected!")
            logger.debug(f"Pattern: {prefix}{pattern}")
            for key in self.backend.scan_iter(f"{prefix}{pattern}"):
                logger.debug("Delete key: %r", key)
                self.backend.delete(key)

    def clear(self):
        for key in self.backend.scan_iter(f"{CACHE_PREFIX}*"):
            self.backend.delete(key)
        self.reset_locks()

    @classmethod
    def reset_locks(cls):
        redis_lock.reset_all(cls.get_backend())

    @classmethod
    def get_redis_cache(cls, cache: FlaskCache = None) -> RedisCache:
        rc = cache or cls.__get_flask_cache()
        return rc.cache if isinstance(rc, FlaskCache) else None

    @classmethod
    def get_backend(cls, cache: RedisCache = None) -> redis.Redis:
        rc = cache or cls.get_redis_cache()
        return rc._read_clients if isinstance(rc, RedisCache) else None


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
                        with hc.lock(key, blocking=True):
                            result = hc.get(key)
                            if not result:
                                logger.debug("Cache empty: getting value from the actual function...")
                                result = function(*args, **kwargs)
                                logger.debug("Checking unless function: %r", unless)
                                if unless is None or unless is True or callable(unless) and not unless(result):
                                    hc.set(key, result, timeout=timeout)
                                else:
                                    logger.debug("Don't set value in cache due to unless=%r", "None" if unless is None else "True")
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

    _cache: Cache = None

    @property
    def cache(self) -> Cache:
        if self._cache is None:
            self._cache = Cache(parent=cache)
        return self._cache
