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


from typing import Any, Dict, List

from lifemonitor import exceptions as lm_exceptions
from lifemonitor.api import models


class RateLimitExceededTestingService(models.TestingService):

    __mapper_args__ = {
        'polymorphic_identity': 'unknown'
    }

    @property
    def token(self) -> models.TestingServiceToken:
        return None

    def initialize(self):
        pass

    def check_connection(self) -> bool:
        raise lm_exceptions.RateLimitExceededException()

    def is_workflow_healthy(self, test_instance: models.TestInstance) -> bool:
        raise lm_exceptions.RateLimitExceededException()

    def get_instance_external_link(self, test_instance: models.TestInstance) -> str:
        raise lm_exceptions.RateLimitExceededException()

    def get_last_test_build(self, test_instance: models.TestInstance) -> models.TestBuild:
        raise lm_exceptions.RateLimitExceededException()

    def get_last_passed_test_build(self, test_instance: models.TestInstance) -> models.TestBuild:
        raise lm_exceptions.RateLimitExceededException()

    def get_last_failed_test_build(self, test_instance: models.TestInstance) -> models.TestBuild:
        raise lm_exceptions.RateLimitExceededException()

    def get_test_build(self, test_instance: models.TestInstance, build_number: int) -> models.TestBuild:
        raise lm_exceptions.RateLimitExceededException()

    def get_test_build_external_link(self, test_build: models.TestBuild) -> str:
        raise lm_exceptions.RateLimitExceededException()

    def get_test_builds(self, test_instance: models.TestInstance, limit: int = 10) -> list:
        raise lm_exceptions.RateLimitExceededException()

    def get_test_builds_as_dict(self, test_instance: models.TestInstance, test_output) -> Dict[str, Any]:
        raise lm_exceptions.RateLimitExceededException()

    def to_dict(self, test_builds: bool = False, test_output: bool = False) -> dict:
        raise lm_exceptions.RateLimitExceededException()

    @classmethod
    def all(cls) -> List[models.TestingService]:
        raise lm_exceptions.RateLimitExceededException()

    @classmethod
    def find_by_uuid(cls, uuid) -> models.TestingService:
        raise lm_exceptions.RateLimitExceededException()

    @classmethod
    def find_by_url(cls, url) -> models.TestingService:
        raise lm_exceptions.RateLimitExceededException()
