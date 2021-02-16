from __future__ import annotations


import logging
import uuid as _uuid
from abc import ABC, abstractmethod
from enum import Enum
from typing import Optional
from sqlalchemy.dialects.postgresql import UUID, JSONB
from lifemonitor.db import db
from lifemonitor.auth.models import User
from lifemonitor.common import (SpecificationNotDefinedException, SpecificationNotValidException, EntityNotFoundException)


import lifemonitor.test_metadata as tm


import lifemonitor.api.models as models

# set module level logger
logger = logging.getLogger(__name__)


class Test:

    def __init__(self,
                 project: TestSuite,
                 name: str, specification: object) -> None:
        self.name = name
        self.project = project
        self.specification = specification

    def __repr__(self):
        return '<Test {} of testing project {} (workflow {}, version {})>'.format(
            self.name, self.project, self.project.workflow.uuid, self.project.workflow.version)

    @property
    def instances(self) -> list:
        return self.project.get_test_instance_by_name(self.name)


class TestSuite(db.Model):
    uuid = db.Column(UUID(as_uuid=True), primary_key=True, default=_uuid.uuid4)
    _workflow_id = db.Column("workflow_id", db.Integer,
                             db.ForeignKey(models.workflows.Workflow._id), nullable=False)
    workflow = db.relationship("Workflow", back_populates="test_suites")
    test_definition = db.Column(JSONB, nullable=False)
    submitter_id = db.Column(db.Integer,
                             db.ForeignKey(User.id), nullable=False)
    submitter = db.relationship("User", uselist=False)
    test_instances = db.relationship("TestInstance",
                                     back_populates="test_suite",
                                     cascade="all, delete")

    def __init__(self,
                 w: models.workflows.Workflow, submitter: User,
                 test_definition: object) -> None:
        self.workflow = w
        self.submitter = submitter
        self.test_definition = test_definition
        self._parse_test_definition()

    def __repr__(self):
        return '<TestSuite {} of workflow {} (version {})>'.format(
            self.uuid, self.workflow.uuid, self.workflow.version)

    def _parse_test_definition(self):
        try:
            for test in self.test_definition["test"]:
                test = tm.Test.from_json(test)
                for instance in test.instance:
                    logger.debug("Instance: %r", instance)
                    testing_service = models.TestingService.get_instance(
                        instance.service.type,
                        instance.service.url
                    )
                    assert testing_service, "Testing service not initialized"
                    logger.debug("Created TestService: %r", testing_service)
                    test_instance = TestInstance(self, self.submitter,
                                                 test.name, instance.service.resource,
                                                 testing_service)
                    logger.debug("Created TestInstance: %r", test_instance)
        except KeyError as e:
            raise SpecificationNotValidException(f"Missing property: {e}")

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

    def add_test_instance(self, submitter: User,
                          test_name, testing_service_type, testing_service_url, testing_service_resource):
        testing_service = \
            models.TestingService.get_instance(testing_service_type, testing_service_url)
        test_instance = TestInstance(self, submitter, test_name, testing_service_resource, testing_service)
        logger.debug("Created TestInstance: %r", test_instance)
        return test_instance

    @property
    def tests(self) -> Optional[dict]:
        if not self.test_definition:
            raise SpecificationNotDefinedException('Not test definition for the test suite {}'.format(self.uuid))
        if "test" not in self.test_definition:
            raise SpecificationNotValidException("'test' property not found")
        # TODO: implement a caching mechanism: with a custom setter for the test_definition collection
        result = {}
        for test in self.test_definition["test"]:
            result[test["name"]] = Test(self, test["name"],
                                        test["specification"] if "specification" in test else None)
        return result

    def save(self):
        db.session.add(self)
        db.session.commit()

    def delete(self):
        db.session.delete(self)
        db.session.commit()

    @classmethod
    def all(cls):
        return cls.query.all()

    @classmethod
    def find_by_id(cls, uuid) -> TestSuite:
        return cls.query.get(uuid)


class TestInstance(db.Model):
    uuid = db.Column(UUID(as_uuid=True), primary_key=True, default=_uuid.uuid4)
    _test_suite_uuid = \
        db.Column("test_suite_uuid", UUID(as_uuid=True), db.ForeignKey(TestSuite.uuid), nullable=False)
    name = db.Column(db.Text, nullable=False)
    resource = db.Column(db.Text, nullable=False)
    parameters = db.Column(JSONB, nullable=True)
    submitter_id = db.Column(db.Integer,
                             db.ForeignKey(User.id), nullable=False)
    # configure relationships
    submitter = db.relationship("User", uselist=False)
    test_suite = db.relationship("TestSuite", back_populates="test_instances")
    testing_service = db.relationship("TestingService",
                                      back_populates="test_instances",
                                      uselist=False,
                                      cascade="save-update, merge, delete, delete-orphan")

    def __init__(self, testing_suite: TestSuite, submitter: User,
                 test_name, test_resource, testing_service: models.TestingService) -> None:
        self.test_suite = testing_suite
        self.submitter = submitter
        self.name = test_name
        self.resource = test_resource
        self.testing_service = testing_service

    def __repr__(self):
        return '<TestInstance {} on TestSuite {}>'.format(self.uuid, self.test_suite.uuid)

    @property
    def test(self):
        if not self.test_suite:
            raise EntityNotFoundException(Test)
        return self.test_suite.tests[self.name]

    @property
    def last_test_build(self):
        return self.testing_service.get_last_test_build(self)

    def get_test_builds(self, limit=10):
        return self.testing_service.get_test_builds(self, limit=limit)

    def get_test_build(self, build_number):
        return self.testing_service.get_test_build(self, build_number)

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

    def save(self):
        db.session.add(self)
        db.session.commit()

    def delete(self):
        db.session.delete(self)
        db.session.commit()

    @classmethod
    def all(cls):
        return cls.query.all()

    @classmethod
    def find_by_id(cls, uuid) -> TestInstance:
        return cls.query.get(uuid)


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

    def __init__(self, testing_service: models.TestingService, test_instance: TestInstance, metadata) -> None:
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
