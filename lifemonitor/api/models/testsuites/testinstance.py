# Copyright (c) 2020-2022 CRS4
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

import datetime
import logging
import uuid as _uuid
from typing import List

import lifemonitor.api.models as models
from lifemonitor.api.models import db
from lifemonitor.cache import Timeout, cached
from lifemonitor.models import JSON, UUID, ModelMixin

from .testsuite import TestSuite

# set module level logger
logger = logging.getLogger(__name__)


class TestInstance(db.Model, ModelMixin):
    uuid = db.Column(UUID, primary_key=True, default=_uuid.uuid4)
    type = db.Column(db.String(20), nullable=False)
    _test_suite_uuid = \
        db.Column("test_suite_uuid", UUID, db.ForeignKey(TestSuite.uuid), nullable=False)
    name = db.Column(db.String, nullable=False)
    roc_instance = db.Column(db.String, nullable=True)
    resource = db.Column(db.Text, nullable=False)
    parameters = db.Column(JSON, nullable=True)
    submitter_id = db.Column(db.Integer,
                             db.ForeignKey(models.User.id), nullable=True)
    last_builds_update = db.Column(db.DateTime, default=datetime.datetime.utcnow,
                                   onupdate=datetime.datetime.utcnow)
    # configure relationships
    submitter = db.relationship("User", uselist=False)
    test_suite = db.relationship("TestSuite",
                                 back_populates="test_instances",
                                 foreign_keys=[_test_suite_uuid])
    testing_service_id = db.Column(UUID, db.ForeignKey("testing_service.uuid"), nullable=False)
    testing_service = db.relationship("TestingService",
                                      foreign_keys=[testing_service_id],
                                      backref=db.backref("test_instances", cascade="all, delete-orphan"),
                                      uselist=False)

    __mapper_args__ = {
        'polymorphic_on': type,
        'polymorphic_identity': 'unmanaged'
    }

    def __init__(self, testing_suite: TestSuite, submitter: models.User,
                 test_name, test_resource, testing_service: models.TestingService,
                 roc_instance: str = None) -> None:
        self.test_suite = testing_suite
        self.submitter = submitter
        self.name = test_name
        self.roc_instance = roc_instance
        self.resource = test_resource
        self.testing_service = testing_service

    def __repr__(self):
        return '<TestInstance {} on TestSuite {}>'.format(self.uuid, self.test_suite.uuid)

    def __eq__(self, o: object) -> bool:
        return isinstance(o, TestInstance) and o.uuid == self.uuid

    @property
    def _cache_key_prefix(self):
        return str(self)

    @property
    def is_roc_instance(self):
        return self.roc_instance is not None

    @property
    def managed(self):
        return self.type != 'unmanaged'

    @property
    def external_link(self):
        try:
            return self.get_external_link()
        except Exception:
            return None

    @cached(timeout=Timeout.BUILD, client_scope=False)
    def get_external_link(self):
        return self.testing_service.get_instance_external_link(self)

    @property
    def last_test_build(self):
        return self.get_last_test_build()

    def start_test_build(self):
        return self.testing_service.start_test_build(self)

    @cached(timeout=Timeout.NONE, client_scope=False, transactional_update=True)
    def get_last_test_build(self):
        builds = self.get_test_builds(limit=10)
        return builds[0] if builds and len(builds) > 0 else None

    @cached(timeout=Timeout.NONE, client_scope=False, transactional_update=True)
    def get_test_builds(self, limit=10):
        try:
            return self.testing_service.get_test_builds(self, limit=limit)
        finally:
            self.last_builds_updated()

    @cached(timeout=Timeout.BUILD, client_scope=False, transactional_update=True)
    def get_test_build(self, build_number):
        return self.testing_service.get_test_build(self, build_number)

    def last_builds_updated(self, when=datetime.datetime.utcnow()):
        self.last_builds_update = when

    def to_dict(self, test_build=False, test_output=False):
        data = {
            'uuid': str(self.uuid),
            'name': self.name,
            'parameters': self.parameters,
            'testing_service': self.testing_service.to_dict(test_builds=False)
        }
        if test_build:
            data.update(self.testing_service.get_test_builds_as_dict(test_output=test_output))
        return data

    @classmethod
    def all(cls) -> List[TestInstance]:
        return cls.query.all()

    @classmethod
    def find_by_uuid(cls, uuid) -> TestInstance:
        return cls.query.get(uuid)

    @classmethod
    def find_by_resource(cls, resource: str) -> List[TestInstance]:
        return cls.query.filter(cls.resource == resource).all()


class ManagedTestInstance(TestInstance):

    __mapper_args__ = {
        'polymorphic_identity': 'managed'
    }
