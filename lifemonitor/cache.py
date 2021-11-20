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
import pickle
import threading
import time
from contextlib import contextmanager

import redis
import redis_lock
from flask import request
from flask.app import Flask
from flask.globals import current_app

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

    _current_transaction = threading.local()

    @classmethod
    def get_current_transaction(cls) -> CacheTransaction:
        try:
            return cls._current_transaction.value
        except AttributeError:
            return None

    @classmethod
    def set_current_transaction(cls, t: CacheTransaction):
        cls._current_transaction.value = t

    def __init__(self, cache: Cache, name=None):
        self.__name = name or f"T-{id(self)}"
        self.__cache__ = cache
        self.__locks__ = {}
        self.__data__ = {}
        self.__started__ = False
        self.__closed__ = False

    def __repr__(self) -> str:
        return f"CacheTransaction#{self.name}"

    @property
    def cache(self):
        return self.__cache__

    @property
    def name(self):
        return self.__name

    def make_key(self, key: str, prefix: str = CACHE_PREFIX) -> str:
        return self.__cache__._make_key(key, prefix=prefix)

    def set(self, key: str, value, timeout: int = Timeout.REQUEST, prefix: str = CACHE_PREFIX):
        self.__data__[self.make_key(key, prefix=prefix)] = (value, timeout)

    def get(self, key: str, prefix: str = CACHE_PREFIX):
        data = self.__data__.get(self.make_key(key, prefix=prefix), None)
        return data[0] if data is not None else None

    def keys(self):
        return list(self.__data__.keys())

    def has(self, key: str) -> bool:
        if key is None:
            return False
        return self.make_key(key) in self.keys()

    @contextmanager
    def lock(self, key: str,
             timeout: int = Timeout.REQUEST,
             expire=15, retry=1, auto_renewal=True):
        logger.debug("Getting lock for key %r...", key)
        if key in self.__locks__:
            yield self.__locks__[key]
        else:
            lock = redis_lock.Lock(self.cache.backend, key, expire=expire, auto_renewal=auto_renewal, id=self.name)
            while not lock.acquire(blocking=False, timeout=timeout if timeout > 0 else None):
                logger.debug("Waiting for lock key '%r'... (retry in %r secs)", lock, retry)
                time.sleep(retry)
            logger.debug("Lock for key '%r' acquired: %r", key, lock.locked)
            self.__locks__[key] = lock
            logger.debug("Lock for key '%r' added to transaction %r: %r", key, self.name, self.has_lock(key))
            try:
                yield lock
            finally:
                logger.debug("Releasing transactional lock context for key '%s'", key)

    def has_lock(self, key: str) -> bool:
        return key in self.__locks__

    def size(self) -> int:
        return len(self.__data__.keys())

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, type, value, traceback):
        self.close()
        return True

    def is_started(self) -> bool:
        return self.__started__

    def start(self):
        logger.debug(f"Starting {self} ...")
        self.__data__.clear()
        self.__locks__.clear()
        self.__started__ = True
        self.__closed__ = False

    def close(self):
        if self.__closed__:
            logger.debug(f"{self} already closed")
        else:
            logger.debug(f"Stopping {self}...")
            try:
                logger.debug("Finalizing transaction...")
                pipeline = self.__cache__.backend.pipeline()
                for k, data in self.__data__.items():
                    logger.debug(f"Setting key {k} on transaction pipeline (timeout: {data[1]}")
                    pipeline.set(k, pickle.dumps(data[0]), ex=data[1] if data[1] > 0 else None)
                pipeline.execute()
                logger.debug("Transaction finalized!")
                for k in list(self.__locks__.keys()):
                    lk = self.__locks__.pop(k)
                    if lk:
                        if lk.locked:
                            logger.debug("Releasing lock for key '%r'...", k)
                            try:
                                lk.release()
                                logger.debug("Lock for key '%r' released: %r", k, lk.locked)
                            except redis_lock.NotAcquired as e:
                                logger.warning(e)
                        else:
                            logger.warning("Lock for key '%s' not acquired or expired")
                    else:
                        logger.warning("No lock for key %r", k)
                logger.debug(f"All lock of {self} released")
                logger.debug(f"{self} closed")
            except Exception as e:
                logger.exception(e)
            finally:
                self.__closed__ = True
                self.__cache__._set_current_transaction(None)
        logger.debug(f"{self} finished")


_current_transaction = threading.local()


class Cache(object):

    # Enable/Disable cache
    cache_enabled = True
    # Ignore cache values even if cache is enabled
    _ignore_cache_values = False
    # Reference to Redis back-end
    __cache__ = None

    @classmethod
    def init_backend(cls, config):
        logger.debug("Initialising cache back-end...")
        logger.debug("Cache type detected: %r", config.get("CACHE_TYPE", None))
        if config.get("CACHE_TYPE", None) == "flask_caching.backends.rediscache.RedisCache":
            logger.debug("Configuring Redis back-end...")
            cls.__cache__ = redis.Redis.from_url(config.get("CACHE_REDIS_URL"))
            cls.cache_enabled = True
        else:
            logger.debug("No cache")
            cls.__cache__ = None
            cls.cache_enabled = False
        return cls.__cache__

    @classmethod
    def get_backend(cls) -> redis.Redis:
        if cls.__cache__ is None:
            raise IllegalStateException("Back-end not initialized!")
        return cls.__cache__

    @classmethod
    def init_app(cls, app: Flask):
        cls.init_backend(app.config)
        if cls.__cache__ is not None:
            cls.reset_locks()

    def __init__(self, parent: Cache = None) -> None:
        self._local = _current_transaction
        self._parent = parent

    @staticmethod
    def _make_key(key: str, prefix: str = CACHE_PREFIX) -> str:
        return f"{prefix}{key}"

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

    def _set_current_transaction(self, t: CacheTransaction):
        CacheTransaction.set_current_transaction(t)

    def get_current_transaction(self) -> CacheTransaction:
        return CacheTransaction.get_current_transaction()

    @contextmanager
    def transaction(self, name=None) -> CacheTransaction:
        new_transaction = False
        t = self.get_current_transaction()
        if t is None:
            logger.debug("Creating a new transaction...")
            t = CacheTransaction(self, name=name)
            self._set_current_transaction(t)
            new_transaction = True
        else:
            logger.debug("Reusing transaction in the current thread: %r", t)
        try:
            yield t
        except Exception as e:
            logger.exception(e)
        finally:
            logger.debug("Finally closing transaction")
            if not new_transaction:
                logger.debug("Transaction not initialized in this context: it should continue")
            else:
                try:
                    t.close()
                except Exception as fe:
                    logger.debug(fe)
                self._set_current_transaction(None)

    @property
    def backend(self) -> redis.Redis:
        return self.get_backend()

    def keys(self, pattern: str = None):
        query = f"{CACHE_PREFIX}"
        if pattern is not None:
            query = f"{query}{pattern}"
        else:
            query = f"{query}*"
        logger.debug("Keys pattern: %r", query)
        return self.backend.keys(query)

    def size(self, pattern=None):
        return len(self.keys(pattern=pattern))

    def to_dict(self, pattern=None):
        return {k: self.backend.get(k) for k in self.keys(pattern=pattern)}

    @contextmanager
    def lock(self, key: str,
             timeout: int = Timeout.REQUEST,
             expire=15, retry=1, auto_renewal=True):
        logger.debug("Getting lock for key %r...", key)
        lock = redis_lock.Lock(self.backend, key, expire=expire, auto_renewal=auto_renewal)
        try:
            while not lock.acquire(blocking=False, timeout=timeout if timeout > 0 else None):
                logger.debug("Waiting to acquire the lock for '%r'... (retry in %r secs)", lock, retry)
                time.sleep(retry)
            logger.debug(f"Lock for key '{key}' acquired: {lock.locked}")
            yield lock
        finally:
            try:
                logger.debug("Exiting from transactional lock context for key '%s'", key)
                if not lock.locked:
                    logger.warning("Lock for key '%s' not acquired", key)
                else:
                    logger.debug("Auto release of lock for key '%s'", key)
                    lock.release()
                    logger.debug("Lock for key='%s' released: %r", key, lock.locked)
            except redis_lock.NotAcquired as e:
                logger.debug(e)

    def set(self, key: str, value, timeout: int = Timeout.NONE, prefix: str = CACHE_PREFIX):
        if key is not None and self.cache_enabled:
            key = self._make_key(key, prefix=prefix)
            logger.debug("Setting cache value for key %r.... (timeout: %r)", key, timeout)
            self.backend.set(key, pickle.dumps(value), ex=timeout if timeout > 0 else None)

    def has(self, key: str, prefix: str = CACHE_PREFIX) -> bool:
        return self.get(key, prefix=prefix) is not None

    def _get_status(self) -> dict:
        return {
            "self": self,
            "enabled": self.cache_enabled,
            "ignore_values": self.ignore_cache_values,
            "current_transaction": self.get_current_transaction(),
            "transaction locks": self.get_current_transaction().__locks__ if self.get_current_transaction() else None
        }

    def get(self, key: str, prefix: str = CACHE_PREFIX):
        logger.debug("Getting value from cache...")
        logger.debug("Cache status: %r", self._get_status())
        if not self.cache_enabled or self.ignore_cache_values:
            return None
        data = self.backend.get(self._make_key(key, prefix=prefix))
        logger.debug("Current cache data: %r", data is not None)
        return pickle.loads(data) if data is not None else data

    def delete_keys(self, pattern: str, prefix: str = CACHE_PREFIX):
        logger.debug(f"Deleting keys by pattern: {pattern}")
        if self.cache_enabled:
            logger.debug("Redis backend detected!")
            logger.debug(f"Pattern: {prefix}{pattern}")
            for key in self.backend.scan_iter(self._make_key(pattern, prefix=prefix)):
                logger.debug("Delete key: %r", key)
                self.backend.delete(key)

    def clear(self):
        for key in self.backend.scan_iter(f"{CACHE_PREFIX}*"):
            self.backend.delete(key)
        self.reset_locks()

    @classmethod
    def reset_locks(cls):
        redis_lock.reset_all(cls.get_backend())


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
            if hc and hc.cache_enabled:
                key = make_cache_key(function, client_scope, args=args, kwargs=kwargs)
                if hc.get_current_transaction() is None:
                    value = hc.get(key)
                    if value is not None:
                        return value

                with hc.transaction() as transaction:
                    result = transaction.get(key)
                    if result is None:
                        logger.debug(f"Value {key} not set in cache...")
                        # if hc.backend:
                        with transaction.lock(key, timeout=Timeout.NONE):
                            result = transaction.get(key)
                            if not result:
                                logger.debug("Cache empty: getting value from the actual function...")
                                result = function(*args, **kwargs)
                                logger.debug("Checking unless function: %r", unless)
                                if unless is None or unless is False or callable(unless) and not unless(result):
                                    transaction.set(key, result, timeout=timeout)
                                else:
                                    logger.debug("Don't set value in cache due to unless=%r", "None" if unless is None else "True")
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
