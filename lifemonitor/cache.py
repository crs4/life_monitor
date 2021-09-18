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

import logging
import functools
from flask_caching import Cache

# Set module logger
logger = logging.getLogger(__name__)

# Instantiate cache manager
cache = Cache()


def _make_name(fname) -> str:
    from lifemonitor.auth import current_user, current_registry
    result = fname
    if current_user and not current_user.is_anonymous:
        result += "-{}-{}".format(current_user.username, current_user.id)
    if current_registry:
        result += "-{}".format(current_registry.uuid)
    logger.debug("Calculated function name: %r", result)

    return result


def clear_cache(func, *args, **kwargs):
    cache.delete_memoized(func, *args, **kwargs)


def cached(timeout=None, unless=False):
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
