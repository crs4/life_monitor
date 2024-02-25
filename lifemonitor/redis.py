# Copyright (c) 2020-2024 CRS4
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

from flask import Flask
from redis import Redis

__redis__ = None


def get_connection() -> Redis:
    global __redis__
    return __redis__


def init(app: Flask) -> Redis:
    global __redis__
    if not __redis__:
        # Connessione a Redis su localhost, porta 6379, database 0
        __redis__ = Redis(host=app.config.get("REDIS_HOST", "redis"),
                          port=int(app.config.get("REDIS_PORT_NUMBER", 6379)),
                          password=app.config.get("REDIS_PASSWORD", "foobar"),
                          db=0)

    # fix logger level
    import logging

    import redis_lock

    redis_lock_logger_level = logging.ERROR
    redis_lock.logger_for_acquire.setLevel(redis_lock_logger_level)
    redis_lock.logger_for_release.setLevel(redis_lock_logger_level)
    redis_lock.logger_for_acquire.setLevel(redis_lock_logger_level)
    redis_lock.logger_for_refresh_thread.setLevel(redis_lock_logger_level)
    redis_lock.logger_for_refresh_start.setLevel(redis_lock_logger_level)
    redis_lock.logger_for_refresh_shutdown.setLevel(redis_lock_logger_level)
    redis_lock.logger_for_refresh_exit.setLevel(redis_lock_logger_level)
    redis_lock.logger_for_release.setLevel(redis_lock_logger_level)
    return __redis__
