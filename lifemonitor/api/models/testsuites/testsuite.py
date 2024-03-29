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

from __future__ import annotations

import logging
import uuid as _uuid
from typing import List


import lifemonitor.api.models as models
from lifemonitor.api.models import db
from lifemonitor.auth.models import User
from lifemonitor.models import JSON, UUID, ModelMixin

# set module level logger
logger = logging.getLogger(__name__)


class TestSuite(db.Model, ModelMixin):
    uuid = db.Column(UUID, primary_key=True, default=_uuid.uuid4)
    name = db.Column(db.String, nullable=True)
    roc_suite = db.Column(db.String, nullable=True)
    definition = db.Column(JSON, nullable=True)
    _workflow_version_id = db.Column("workflow_version_id", db.Integer,
                                     db.ForeignKey(models.workflows.WorkflowVersion.id), nullable=False)
    workflow_version = db.relationship("WorkflowVersion", back_populates="test_suites")
    submitter_id = db.Column(db.Integer,
                             db.ForeignKey(User.id), nullable=True)
    submitter = db.relationship("User", uselist=False)
    test_instances = db.relationship("TestInstance",
                                     back_populates="test_suite",
                                     cascade="all, delete-orphan")

    def __init__(self,
                 w: models.workflows.WorkflowVersion, submitter: User,
                 name: str = None, roc_suite: str = None, definition: object = None) -> None:
        self.workflow_version = w
        self.submitter = submitter
        self.name = name
        self.roc_suite = roc_suite
        self.definition = definition

    def __repr__(self):
        return '<TestSuite {} of workflow {} (version {})>'.format(
            self.uuid, self.workflow_version.uuid, self.workflow_version.version)

    @property
    def status(self) -> models.SuiteStatus:
        return models.SuiteStatus(self)

    def get_test_instance_by_name(self, name) -> list:
        result = []
        for ti in self.test_instances:
            if ti.name == name:
                result.append(ti)
        return result

    def to_dict(self, test_build=False, test_output=False) -> dict:
        return {
            'uuid': str(self.uuid),
            'test': [t.to_dict(test_build=test_build, test_output=test_output)
                     for t in self.test_instances]
        }

    def add_test_instance(self, submitter: User, managed: bool, test_name: str,
                          testing_service_type, testing_service_url, testing_service_resource,
                          roc_instance: str = None):
        testing_service = \
            models.TestingService.get_instance(testing_service_type, testing_service_url)
        assert testing_service, "Testing service not initialized"
        instance_cls = models.TestInstance if not managed else models.ManagedTestInstance
        test_instance = instance_cls(self, submitter, test_name, testing_service_resource, testing_service, roc_instance)
        logger.debug("Created TestInstance: %r", test_instance)
        return test_instance

    @classmethod
    def all(cls) -> List[TestSuite]:
        return cls.query.all()

    @classmethod
    def find_by_uuid(cls, uuid) -> TestSuite:
        return cls.query.get(uuid)
