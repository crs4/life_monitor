from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from enum import Enum

import lifemonitor.api.models as models

# set module level logger
logger = logging.getLogger(__name__)


class BuildStatus:
    PASSED = "passed"
    FAILED = "failed"
    ERROR = "error"
    RUNNING = "running"
    WAITING = "waiting"
    ABORTED = "aborted"


class TestBuild(ABC):
    class Result(Enum):
        SUCCESS = 0
        FAILED = 1

    def __init__(self, testing_service: models.TestingService, test_instance: models.TestInstance, metadata) -> None:
        self.testing_service = testing_service
        self.test_instance = test_instance
        self._metadata = metadata
        self._output = None

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
