from __future__ import annotations
import os
import logging
import uuid as _uuid
from abc import ABC, abstractmethod
from enum import Enum
from typing import Optional

import jenkins
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.dialects.postgresql import UUID, JSONB
from lifemonitor.common import (SpecificationNotValidException, EntityNotFoundException,
                                SpecificationNotDefinedException, TestingServiceNotSupportedException,
                                NotImplementedException, LifeMonitorException)
from lifemonitor.utils import download_url, to_camel_case

# set DB instance
db = SQLAlchemy()

# set module level logger
logger = logging.getLogger(__name__)


def db_uri():
    """
    Build URI to connect to the DataBase
    :return:
    """
    if os.getenv('DATABASE_URI'):
        uri = os.getenv('DATABASE_URI')
    else:
        uri = "postgresql://{user}:{passwd}@{host}:{port}/{dbname}".format(
            user=os.getenv('POSTGRESQL_USERNAME'),
            passwd=os.getenv('POSTGRESQL_PASSWORD', ''),
            host=os.getenv('POSTGRESQL_HOST'),
            port=os.getenv('POSTGRESQL_PORT'),
            dbname=os.getenv('POSTGRESQL_DATABASE'))
    return uri


def config_db_access(flask_app):
    """
    Initialize DB
    :param flask_app:
    :return:
    """
    flask_app.config['SQLALCHEMY_DATABASE_URI'] = db_uri()
    # FSADeprecationWarning: SQLALCHEMY_TRACK_MODIFICATIONS adds significant
    # overhead and will be disabled by default in the future.  Set it to True
    # or False to suppress this warning.
    flask_app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    db.init_app(flask_app)
    db.create_all()


class WorkflowRegistry(object):
    __instance = None

    @classmethod
    def get_instance(cls) -> WorkflowRegistry:
        if not cls.__instance:
            cls.__instance = cls()
        return cls.__instance

    def __init__(self):
        if self.__instance:
            raise Exception("WorkflowRegistry instance already exists!")
        self.__instance = self
        self._url = os.environ["WORKFLOW_REGISTRY_URL"]
        self._token = os.environ["WORKFLOW_REGISTRY_TOKEN"]

    @property
    def url(self):
        return self._url

    def build_ro_link(self, w: Workflow) -> str:
        return "{}?version={}".format(os.path.join(self._url, "workflow", w.uuid), w.version)

    def download_url(self, url, target_path=None):
        return download_url(url, target_path, self._token)


class Workflow(db.Model):
    _id = db.Column('id', db.Integer, primary_key=True)
    uuid = db.Column(UUID)
    version = db.Column(db.Text)
    name = db.Column(db.Text, nullable=True)
    roc_metadata = db.Column(JSONB, nullable=True)
    test_suites = db.relationship("TestSuite", back_populates="workflow", cascade="all, delete")
    _registry = None
    # additional relational specs
    __tablename__ = "workflow"
    __table_args__ = tuple(
        db.UniqueConstraint(uuid, version)
    )

    def __init__(self, uuid, version, roc_metadata=None, name=None) -> None:
        self.uuid = uuid
        self.version = version
        self.roc_metadata = roc_metadata
        self.name = name
        self._registry = None

    @property
    def registry(self):
        if not self._registry:
            self._registry = WorkflowRegistry.get_instance()
        return self._registry

    @property
    def roc_link(self):
        if self.registry:
            return self.registry.build_ro_link(self)
        return ""

    def __repr__(self):
        return '<Workflow ({}, {}); name: {}; link: {}>'.format(
            self.uuid, self.version, self.name, self.roc_link)

    @property
    def is_healthy(self) -> bool:
        for suite in self.test_suites:
            for test_configuration in suite.test_configurations:
                testing_service = test_configuration.testing_service
                if not testing_service.last_test_build.is_successful():
                    return False
        return True

    def to_dict(self, test_suite=False, test_output=False):
        return {
            'uuid': str(self.uuid),
            'version': self.version,
            'name': self.name,
            'roc_link': self.roc_link,
            'isHealthy': self.is_healthy,
            'test_suite': [s.to_dict(test_output) for s in self.test_suites] if test_suite else None
        }

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
    def find_by_id(cls, uuid, version):
        return cls.query.filter(Workflow.uuid == uuid) \
            .filter(Workflow.version == version).first()


class Test(object):

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
    _workflow_id = db.Column("workflow_id", db.Integer, db.ForeignKey(Workflow._id), nullable=False)
    workflow = db.relationship("Workflow", back_populates="test_suites")
    test_definition = db.Column(JSONB, nullable=True)
    test_configurations = db.relationship("TestConfiguration",
                                          back_populates="test_suite", cascade="all, delete")
    # additional relational specs
    __table_args__ = tuple(
        # db.ForeignKeyConstraint([workflow_uuid, workflow_version], [Workflow.uuid, Workflow.version])
    )

    def __init__(self, w: Workflow, test_definition: object = None) -> None:
        self.workflow = w
        self.test_definition = test_definition

    def __repr__(self):
        return '<TestSuite {} of workflow {} (version {})>'.format(
            self.uuid, self.workflow.uuid, self.workflow.version)

    def get_test_instance_by_name(self, name) -> list:
        result = []
        for ti in self.test_configurations:
            if ti.name == name:
                result.append(ti)
        return result

    def to_dict(self, test_output=False) -> dict:
        return {
            'uuid': str(self.uuid),
            'test': [t.to_dict(test_output) for t in self.test_configurations]
        }

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


class TestConfiguration(db.Model):
    uuid = db.Column(UUID(as_uuid=True), primary_key=True, default=_uuid.uuid4)
    _test_suite_uuid = \
        db.Column("test_suite_uuid", UUID(as_uuid=True), db.ForeignKey(TestSuite.uuid), nullable=False)
    test_name = db.Column(db.Text, nullable=False)
    test_instance_name = db.Column(db.Text, nullable=True)
    url = db.Column(db.Text, nullable=True)
    parameters = db.Column(JSONB, nullable=True)
    # configure relationships
    test_suite = db.relationship("TestSuite", back_populates="test_configurations")
    testing_service = db.relationship("TestingService", uselist=False, back_populates="test_configuration",
                                      cascade="all, delete")

    def __init__(self, testing_suite: TestSuite,
                 test_name, test_instance_name=None, url: str = None) -> None:
        self.test_suite = testing_suite
        self.test_name = test_name
        self.test_instance_name = test_instance_name
        self.url = url

    def __repr__(self):
        return '<TestConfiguration {} on TestSuite {}>'.format(self.uuid, self.test_suite.uuid)

    @property
    def test(self):
        if not self.test_suite:
            raise EntityNotFoundException(Test)
        return self.test_suite.tests[self.test_name]

    def to_dict(self, test_output=False):
        return {
            'uuid': str(self.uuid),
            'name': self.test_instance_name or self.test_name,
            'url': self.url,
            'parameters': self.parameters,
            'testing_service': self.testing_service.to_dict(test_output)
        }

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
    def find_by_id(cls, uuid) -> TestConfiguration:
        return cls.query.get(uuid)


class TestingServiceToken(object):
    def __init__(self, key, secret):
        self.key = key
        self.secret = secret

    def __composite_values__(self):
        return self.key, self.secret

    def __repr__(self):
        return "<TestingServiceToken (key=%r, secret=****)>" % self.key

    def __eq__(self, other):
        return isinstance(other, TestingServiceToken) and \
               other.key == self.key and \
               other.secret == self.secret

    def __ne__(self, other):
        return not self.__eq__(other)


class TestingService(db.Model):
    uuid = db.Column("uuid", UUID(as_uuid=True), db.ForeignKey(TestConfiguration.uuid), primary_key=True)
    _type = db.Column("type", db.String, nullable=False)
    _key = db.Column("key", db.Text, nullable=True)
    _secret = db.Column("secret", db.Text, nullable=True)
    url = db.Column(db.Text, nullable=False)
    # configure nested object
    token = db.composite(TestingServiceToken, _key, _secret)
    # configure relationships
    test_configuration = db.relationship("TestConfiguration", back_populates="testing_service",
                                         cascade="all, delete")

    __mapper_args__ = {
        'polymorphic_on': _type,
        'polymorphic_identity': 'testing_service'
    }

    def __init__(self, test_configuration: TestConfiguration, url: str) -> None:
        self.test_configuration = test_configuration
        self.url = url

    def __repr__(self):
        return '<TestingService {} for the TestConfiguration {}>'.format(self.uuid, self.test_configuration.uuid)

    @property
    def test_instance_name(self):
        return self.test_configuration.test_instance_name

    @property
    def is_workflow_healthy(self) -> bool:
        raise NotImplementedException()

    @property
    def last_test_build(self) -> TestBuild:
        raise NotImplementedException()

    @property
    def last_successful_test_build(self) -> TestBuild:
        raise NotImplementedException()

    @property
    def last_failed_test_build(self) -> TestBuild:
        raise NotImplementedException()

    @property
    def test_builds(self) -> list:
        raise NotImplementedException()

    def to_dict(self, test_output=False) -> dict:
        last_test_build = self.last_test_build
        last_successful_test_build = self.last_successful_test_build
        last_failed_test_build = self.last_failed_test_build
        return {
            'uuid': str(self.uuid),
            'url': self.url,
            'workflow_healthy': self.is_workflow_healthy,
            'last_test_build': last_test_build.to_dict(test_output) if last_test_build else None,
            'last_successful_test_build':
                last_successful_test_build.to_dict(test_output) if last_successful_test_build else None,
            'last_failed_test_build':
                last_failed_test_build.to_dict(test_output) if last_failed_test_build else None,
            "test_builds": [t.to_dict(test_output) for t in self.test_builds]
        }

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
    def find_by_id(cls, uuid) -> TestingService:
        return cls.query.get(uuid)

    @classmethod
    def new_instance(cls, test_instance: TestConfiguration, service_type, url: str):
        try:
            service_class = globals()["{}TestingService".format(to_camel_case(service_type))]
            return service_class(test_instance, url)
        except Exception as e:
            raise TestingServiceNotSupportedException(e)


class TestBuild(ABC):
    class Result(Enum):
        SUCCESS = 0
        FAILED = 1

    def __init__(self, testing_service: TestingService, metadata) -> None:
        self.testing_service = testing_service
        self._metadata = metadata

    def is_successful(self):
        return self.result == TestBuild.Result.SUCCESS

    @property
    def metadata(self):
        return self._metadata

    @property
    @abstractmethod
    def build_number(self) -> int:
        pass

    @property
    @abstractmethod
    def last_built_revision(self):
        pass

    @property
    @abstractmethod
    def duration(self) -> int:
        pass

    @property
    @abstractmethod
    def output(self) -> str:
        pass

    @property
    @abstractmethod
    def result(self) -> TestBuild.Result:
        pass

    @property
    @abstractmethod
    def url(self) -> str:
        pass

    def to_dict(self, test_output=False) -> dict:
        return {
            'success': self.is_successful(),
            'build_number': self.build_number,
            'last_build_revision': self.last_built_revision,
            'duration': self.duration,
            'output': self.output if test_output else ''
        }


class JenkinsTestBuild(TestBuild):

    @property
    def build_number(self) -> int:
        return self.metadata['number']

    @property
    def last_built_revision(self):
        rev_info = list(map(lambda x: x["lastBuiltRevision"],
                            filter(lambda x: "lastBuiltRevision" in x, self.metadata["actions"])))
        return rev_info[0] if len(rev_info) == 1 else None

    @property
    def duration(self) -> int:
        return self.metadata['duration']

    @property
    def output(self) -> str:
        return self.testing_service.get_test_build_output(self.build_number)

    @property
    def result(self) -> TestBuild.Result:
        return TestBuild.Result.SUCCESS \
            if self.metadata["result"] == "SUCCESS" else TestBuild.Result.FAILED

    @property
    def url(self) -> str:
        return self.metadata['url']


class JenkinsTestingService(TestingService):
    _server = None
    __mapper_args__ = {
        'polymorphic_identity': 'jenkins_testing_service'
    }

    def __init__(self, test_configuration: TestConfiguration, url: str) -> None:
        super().__init__(test_configuration, url)
        self._server = jenkins.Jenkins(self.url)

    @property
    def server(self):
        if not self._server:
            self._server = jenkins.Jenkins(self.url)
        return self._server

    @property
    def is_workflow_healthy(self) -> bool:
        return self.last_test_build.is_successful()

    @property
    def last_test_build(self) -> Optional[JenkinsTestBuild]:
        if self.project_metadata['lastBuild']:
            return self.get_test_build(self.project_metadata['lastBuild']['number'])
        return None

    @property
    def last_successful_test_build(self) -> Optional[JenkinsTestBuild]:
        if self.project_metadata['lastSuccessfulBuild']:
            return self.get_test_build(self.project_metadata['lastSuccessfulBuild']['number'])
        return None

    @property
    def last_failed_test_build(self) -> Optional[JenkinsTestBuild]:
        if self.project_metadata['lastFailedBuild']:
            return self.get_test_build(self.project_metadata['lastFailedBuild']['number'])
        return None

    @property
    def test_builds(self) -> list:
        builds = []
        for build_info in self.project_metadata['builds']:
            builds.append(self.get_test_build(build_info['number']))
        return builds

    @property
    def project_metadata(self):
        try:
            return self.server.get_job_info(self.test_instance_name)
        except jenkins.JenkinsException as e:
            raise LifeMonitorException(e)

    def get_test_build(self, build_number) -> JenkinsTestBuild:
        try:
            build_metadata = self.server.get_build_info(self.test_instance_name, build_number)
            return JenkinsTestBuild(self, build_metadata)
        except jenkins.JenkinsException as e:
            raise LifeMonitorException(e)

    def get_test_build_output(self, build_number):
        try:
            return self.server.get_build_console_output(self.test_instance_name, build_number)
        except jenkins.JenkinsException as e:
            raise LifeMonitorException(e)
