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
from abc import ABC, abstractmethod
from enum import Enum

import lifemonitor.api.models as models
from lifemonitor.cache import CacheMixin

# set module level logger
logger = logging.getLogger(__name__)


class BuildStatus:
    PASSED = "passed"
    FAILED = "failed"
    ERROR = "error"
    RUNNING = "running"
    WAITING = "waiting"
    ABORTED = "aborted"


class TestBuild(ABC, CacheMixin):
    class Result(Enum):
        SUCCESS = 0
        FAILED = 1

    def __init__(self, testing_service: models.TestingService, test_instance: models.TestInstance, metadata) -> None:
        self.testing_service = testing_service
        self.test_instance = test_instance
        self._metadata = metadata
        self._output = None

    def __repr__(self) -> str:
        return f"TestBuild '{self.id}' @ instance '{self.test_instance.uuid}'"

    def __eq__(self, other):
        return isinstance(other, TestBuild) \
            and self.id == other.id and self.test_instance == other.test_instance

    def is_successful(self):
        return self.result == TestBuild.Result.SUCCESS

    @property
    @abstractmethod
    def id(self) -> str:
        pass

    @property
    def status(self):
        pass

    @property
    def metadata(self):
        return self._metadata

    @property
    @abstractmethod
    def build_number(self) -> int:
        pass

    @property
    @abstractmethod
    def revision(self):
        pass

    @property
    @abstractmethod
    def timestamp(self) -> int:
        pass

    @property
    @abstractmethod
    def duration(self) -> int:
        pass

    @property
    def output(self) -> str:
        if not self._output:
            self._output = self.testing_service.get_test_build_output(self.test_instance, self.id, offset_bytes=0, limit_bytes=0)
        return self._output

    @property
    @abstractmethod
    def result(self) -> TestBuild.Result:
        pass

    @property
    @abstractmethod
    def url(self) -> str:
        pass

    @property
    def external_link(self) -> str:
        logger.debug("Getting external link...")
        key = f"{str(self)}_external_link"
        link = self.cache.get(key)
        if link is None:
            logger.debug("Getting external link from testing service...")
            link = self.testing_service.get_test_build_external_link(self)
            if link is not None:
                self.cache.set(key, link)
        else:
            logger.debug("Reusing external link from cache...")
        return link

    def get_output(self, offset_bytes=0, limit_bytes=131072):
        return self.testing_service.get_test_build_output(self.test_instance, self.id, offset_bytes, limit_bytes)

    def to_dict(self, test_output=False) -> dict:
        data = {
            'success': self.is_successful(),
            'build_number': self.build_number,
            'last_build_revision': self.revision,
            'duration': self.duration
        }
        if test_output:
            data['output'] = self.output
        return data
