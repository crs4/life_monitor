from __future__ import annotations

import logging
import uuid as _uuid
from typing import Optional

import lifemonitor.api.models as models
import lifemonitor.exceptions as lm_exceptions
import lifemonitor.test_metadata as tm
from lifemonitor.api.models import db
from lifemonitor.auth.models import User
from sqlalchemy.dialects.postgresql import JSONB, UUID

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
                    test_instance = models.TestInstance(self, self.submitter,
                                                        test.name, instance.service.resource,
                                                        testing_service)
                    logger.debug("Created TestInstance: %r", test_instance)
        except KeyError as e:
            raise lm_exceptions.SpecificationNotValidException(f"Missing property: {e}")

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
        test_instance = models.TestInstance(self, submitter, test_name, testing_service_resource, testing_service)
        logger.debug("Created TestInstance: %r", test_instance)
        return test_instance

    @property
    def tests(self) -> Optional[dict]:
        if not self.test_definition:
            raise lm_exceptions.SpecificationNotDefinedException('Not test definition for the test suite {}'.format(self.uuid))
        if "test" not in self.test_definition:
            raise lm_exceptions.SpecificationNotValidException("'test' property not found")
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
