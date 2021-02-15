from __future__ import annotations

import re
import logging
import jenkins
import requests
import datetime
import uuid as _uuid
from typing import Union, List
from abc import ABC, abstractmethod
from enum import Enum
from typing import Optional
from authlib.integrations.base_client import RemoteApp
from sqlalchemy.dialects.postgresql import UUID, JSONB
from lifemonitor.db import db
from lifemonitor.auth.models import User
from sqlalchemy.ext.associationproxy import association_proxy
from lifemonitor.auth.oauth2.client.services import oauth2_registry
from lifemonitor.lang import messages
from lifemonitor.api import registries

from lifemonitor.common import (SpecificationNotValidException, EntityNotFoundException,
                                SpecificationNotDefinedException, TestingServiceNotSupportedException,
                                NotImplementedException, TestingServiceException)
from lifemonitor.utils import download_url, to_camel_case
from lifemonitor.auth.oauth2.client.models import OAuthIdentity
import lifemonitor.test_metadata as tm
from urllib.parse import urljoin, urlencode

# 'status' module
from .status import Status, AggregateTestStatus, WorkflowStatus, SuiteStatus

# 'registries' package
from .registries import WorkflowRegistry, WorkflowRegistryClient

__all__ = [
    "Status", "AggregateTestStatus", "WorkflowStatus", "SuiteStatus"
]

# set module level logger
logger = logging.getLogger(__name__)


class Workflow(db.Model):
    _id = db.Column('id', db.Integer, primary_key=True)
    uuid = db.Column(UUID)
    version = db.Column(db.Text, nullable=False)
    roc_link = db.Column(db.Text, nullable=False)
    roc_metadata = db.Column(JSONB, nullable=True)
    submitter_id = db.Column(db.Integer,
                             db.ForeignKey(User.id), nullable=False)
    _registry_id = \
        db.Column("registry_id", UUID(as_uuid=True),
                  db.ForeignKey(WorkflowRegistry.uuid), nullable=True)
    external_id = db.Column(db.String, nullable=True)
    workflow_registry = db.relationship("WorkflowRegistry", uselist=False, back_populates="registered_workflows")
    name = db.Column(db.Text, nullable=True)
    test_suites = db.relationship("TestSuite", back_populates="workflow", cascade="all, delete")
    submitter = db.relationship("User", uselist=False)

    # additional relational specs
    __tablename__ = "workflow"
    __table_args__ = (
        db.UniqueConstraint(uuid, version),
        db.UniqueConstraint(_registry_id, external_id, version),
    )

    def __init__(self,
                 uuid, version, submitter: User, rock_link,
                 registry: WorkflowRegistry = None,
                 roc_metadata=None, external_id=None, name=None) -> None:
        self.uuid = uuid
        self.version = version
        self.roc_link = rock_link
        self.roc_metadata = roc_metadata
        self.name = name
        self.external_id = external_id
        self.workflow_registry = registry
        self.submitter = submitter

    def __repr__(self):
        return '<Workflow ({}, {}); name: {}; link: {}>'.format(
            self.uuid, self.version, self.name, self.roc_link)

    def check_health(self) -> dict:
        health = {'healthy': True, 'issues': []}
        for suite in self.test_suites:
            for test_instance in suite.test_instances:
                try:
                    testing_service = test_instance.testing_service
                    if not testing_service.last_test_build.is_successful():
                        health["healthy"] = False
                except TestingServiceException as e:
                    health["issues"].append(str(e))
                    health["healthy"] = "Unknown"
        return health

    @property
    def previous_versions(self):
        return list(self.previous_workflow_versions.keys())

    @property
    def previous_workflow_versions(self):
        return {k: v
                for k, v in self.workflow_registry.get_workflow_versions(self.uuid).items()
                if k != self.version}

    @property
    def status(self) -> WorkflowStatus:
        return WorkflowStatus(self)

    @property
    def is_healthy(self) -> Union[bool, str]:
        return self.check_health()["healthy"]

    def add_test_suite(self, submitter: User, test_suite_metadata):
        return TestSuite(self, submitter, test_suite_metadata)

    @property
    def submitter_identity(self):
        # Return the submitter identity wrt the registry
        identity = OAuthIdentity.find_by_user_id(self.submitter.id, self.workflow_registry.name)
        return identity.provider_user_id

    def to_dict(self, test_suite=False, test_build=False, test_output=False):
        health = self.check_health()
        data = {
            'uuid': str(self.uuid),
            'version': self.version,
            'name': self.name,
            'roc_link': self.roc_link,
            'isHealthy': health["healthy"],
            'issues': health["issues"]
        }
        if test_suite:
            data['test_suite'] = [s.to_dict(test_build=test_build, test_output=test_output)
                                  for s in self.test_suites]
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
    def find_by_id(cls, uuid, version):
        return cls.query.filter(Workflow.uuid == uuid) \
            .filter(Workflow.version == version).first()

    @classmethod
    def find_latest_by_id(cls, uuid):
        return cls.query.filter(Workflow.uuid == uuid) \
            .order_by(Workflow.version.desc()).first()

    @classmethod
    def find_by_submitter(cls, submitter: User):
        return cls.query.filter(Workflow.submitter_id == submitter.id).first()


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
                             db.ForeignKey(Workflow._id), nullable=False)
    workflow = db.relationship("Workflow", back_populates="test_suites")
    test_definition = db.Column(JSONB, nullable=False)
    submitter_id = db.Column(db.Integer,
                             db.ForeignKey(User.id), nullable=False)
    submitter = db.relationship("User", uselist=False)
    test_instances = db.relationship("TestInstance",
                                     back_populates="test_suite",
                                     cascade="all, delete")

    def __init__(self,
                 w: Workflow, submitter: User,
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
                    testing_service = TestingService.get_instance(
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
    def status(self) -> SuiteStatus:
        return SuiteStatus(self)

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
            TestingService.get_instance(testing_service_type, testing_service_url)
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
                 test_name, test_resource, testing_service: TestingService) -> None:
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


class TestingServiceToken:
    def __init__(self, key, secret):
        self.key = key
        self.secret = secret

    def __composite_values__(self):
        return self.key, self.secret

    def __repr__(self):
        return "<TestingServiceToken (key=%r, secret=****)>" % self.key

    def __eq__(self, other):
        return isinstance(other, TestingServiceToken) and other.key == self.key and other.secret == self.secret

    def __ne__(self, other):
        return not self.__eq__(other)


class TestingServiceTokenManager:
    __instance = None

    @classmethod
    def get_instance(cls) -> TestingServiceTokenManager:
        if not cls.__instance:
            cls.__instance = cls()
        return cls.__instance

    def __init__(self):
        if self.__instance:
            raise RuntimeError("TestingServiceTokenManager instance already exists!")
        self.__instance = self
        self.__token_registry = {}

    def add_token(self, service_url, token: TestingServiceToken):
        self.__token_registry[service_url] = token

    def remove_token(self, service_url):
        try:
            del self.__token_registry[service_url]
        except KeyError:
            logger.info("No token for the service '{}'", service_url)

    def get_token(self, service_url) -> TestingServiceToken:
        return self.__token_registry[service_url] if service_url in self.__token_registry else None


class TestingService(db.Model):
    uuid = db.Column("uuid", UUID(as_uuid=True), db.ForeignKey(TestInstance.uuid), primary_key=True)
    _type = db.Column("type", db.String, nullable=False)
    url = db.Column(db.Text, nullable=False, unique=True)
    _token = None

    # configure relationships
    test_instances = db.relationship("TestInstance", back_populates="testing_service")

    __mapper_args__ = {
        'polymorphic_on': _type,
        'polymorphic_identity': 'testing_service'
    }

    def __init__(self, url: str, token: TestingServiceToken = None) -> None:
        self.url = url
        self._token = token

    def __repr__(self):
        return f'<TestingService {self.url}, ({self.uuid})>'

    @property
    def token(self):
        if not self._token:
            logger.debug("Querying the token registry for the service %r...", self.url)
            self._token = TestingServiceTokenManager.get_instance().get_token(self.url)
        logger.debug("Set token for the testing service %r (type: %r): %r", self.url, self._type, self._token is not None)
        return self._token

    def check_connection(self) -> bool:
        raise NotImplementedException()

    def is_workflow_healthy(self, test_instance: TestInstance) -> bool:
        raise NotImplementedException()

    def get_last_test_build(self, test_instance: TestInstance) -> TestBuild:
        raise NotImplementedException()

    def get_last_passed_test_build(self, test_instance: TestInstance) -> TestBuild:
        raise NotImplementedException()

    def get_last_failed_test_build(self, test_instance: TestInstance) -> TestBuild:
        raise NotImplementedException()

    def get_test_build(self, test_instance: TestInstance, build_number) -> TestBuild:
        raise NotImplementedException()

    def get_test_builds(self, test_instance: TestInstance, limit=10) -> list:
        raise NotImplementedException()

    def get_test_builds_as_dict(self, test_instance: TestInstance, test_output):
        last_test_build = self.last_test_build
        last_passed_test_build = self.last_passed_test_build
        last_failed_test_build = self.last_failed_test_build
        return {
            'last_test_build': last_test_build.to_dict(test_output) if last_test_build else None,
            'last_passed_test_build':
                last_passed_test_build.to_dict(test_output) if last_passed_test_build else None,
            'last_failed_test_build':
                last_failed_test_build.to_dict(test_output) if last_failed_test_build else None,
            "test_builds": [t.to_dict(test_output) for t in self.test_builds]
        }

    def to_dict(self, test_builds=False, test_output=False) -> dict:
        data = {
            'uuid': str(self.uuid),
            'testing_service_url': self.url,
            'workflow_healthy': self.is_workflow_healthy,
        }
        if test_builds:
            data["test_build"] = self.get_test_builds_as_dict(test_output=test_output)
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
    def find_by_id(cls, uuid) -> TestingService:
        return cls.query.get(uuid)

    @classmethod
    def find_by_url(cls, url) -> TestingService:
        return cls.query.filter(TestingService.url == url).first()

    @classmethod
    def get_instance(cls, service_type, url: str):
        try:
            # return the service obj if the service has already been registered
            instance = cls.find_by_url(url)
            logger.debug("Found service instance: %r", instance)
            if instance:
                return instance
            # try to instanciate the service if the it has not been registered yet
            service_class = globals()["{}TestingService".format(to_camel_case(service_type))]
            return service_class(url)
        except KeyError:
            raise TestingServiceNotSupportedException(f"Not supported testing service type '{service_type}'")
        except Exception as e:
            raise TestingServiceException(detail=str(e))


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

    def __init__(self, testing_service: TestingService, test_instance: TestInstance, metadata) -> None:
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


class JenkinsTestBuild(TestBuild):

    @property
    def id(self) -> str:
        return self.metadata['number']

    @property
    def build_number(self) -> int:
        return self.metadata['number']

    def is_running(self) -> bool:
        return self.metadata['building'] is True

    @property
    def status(self) -> str:
        if self.is_running():
            return BuildStatus.RUNNING
        if self.metadata['result']:
            if self.metadata['result'] == 'SUCCESS':
                return BuildStatus.PASSED
            elif self.metadata['result'] == 'ABORTED':
                return BuildStatus.ABORTED
            elif self.metadata['result'] == 'FAILURE':
                return BuildStatus.FAILED
        return BuildStatus.ERROR

    @property
    def revision(self):
        rev_info = list(map(lambda x: x["lastBuiltRevision"],
                            filter(lambda x: "lastBuiltRevision" in x, self.metadata["actions"])))
        return rev_info[0] if len(rev_info) == 1 else None

    @property
    def timestamp(self) -> int:
        return self.metadata['timestamp']

    @property
    def duration(self) -> int:
        return self.metadata['duration']

    @property
    def result(self) -> TestBuild.Result:
        return TestBuild.Result.SUCCESS \
            if self.metadata["result"] == "SUCCESS" else TestBuild.Result.FAILED

    @property
    def url(self) -> str:
        return self.metadata['url']


class JenkinsTestingService(TestingService):
    _server = None
    _job_name = None
    __mapper_args__ = {
        'polymorphic_identity': 'jenkins_testing_service'
    }

    def __init__(self, url: str, token: TestingServiceToken = None) -> None:
        super().__init__(url, token)
        try:
            self._server = jenkins.Jenkins(self.url)
        except Exception as e:
            raise TestingServiceException(e)

    def check_connection(self) -> bool:
        try:
            assert '_class' in self.server.get_info()
        except Exception as e:
            raise TestingServiceException(detail=str(e))

    @property
    def server(self) -> jenkins.Jenkins:
        if not self._server:
            self._server = jenkins.Jenkins(self.url)
        return self._server

    @staticmethod
    def get_job_name(resource):
        # extract the job name from the resource path
        logger.debug(f"Getting project metadata - resource: {resource}")
        job_name = re.sub("(?s:.*)/", "", resource.strip('/'))
        logger.debug(f"The job name: {job_name}")
        if not job_name or len(job_name) == 0:
            raise TestingServiceException(
                f"Unable to get the Jenkins job from the resource {job_name}")
        return job_name

    def is_workflow_healthy(self, test_instance: TestInstance) -> bool:
        return self.get_last_test_build(test_instance).is_successful()

    def get_last_test_build(self, test_instance: TestInstance) -> Optional[JenkinsTestBuild]:
        metadata = self.get_project_metadata(test_instance)
        if 'lastBuild' in metadata and metadata['lastBuild']:
            return self.get_test_build(test_instance, metadata['lastBuild']['number'])
        return None

    def get_last_passed_test_build(self, test_instance: TestInstance) -> Optional[JenkinsTestBuild]:
        metadata = self.get_project_metadata(test_instance)
        if 'lastSuccessfulBuild' in metadata and metadata['lastSuccessfulBuild']:
            return self.get_test_build(test_instance, metadata['lastSuccessfulBuild']['number'])
        return None

    def get_last_failed_test_build(self, test_instance: TestInstance) -> Optional[JenkinsTestBuild]:
        metadata = self.get_project_metadata(test_instance)
        if 'lastFailedBuild' in metadata and metadata['lastFailedBuild']:
            return self.get_test_build(metadata['lastFailedBuild']['number'])
        return None

    def test_builds(self, test_instance: TestInstance) -> list:
        builds = []
        metadata = self.get_project_metadata(test_instance)
        for build_info in metadata['builds']:
            builds.append(self.get_test_build(test_instance, build_info['number']))
        return builds

    def get_project_metadata(self, test_instance: TestInstance, fetch_all_builds=False):
        if not hasattr(test_instance, "_raw_metadata") or test_instance._raw_metadata is None:
            try:
                test_instance._raw_metadata = self.server.get_job_info(
                    self.get_job_name(test_instance.resource), fetch_all_builds=fetch_all_builds)
            except jenkins.JenkinsException as e:
                raise TestingServiceException(f"{self}: {e}")
        return test_instance._raw_metadata

    def get_test_builds(self, test_instance: TestInstance, limit=10):
        builds = []
        project_metadata = self.get_project_metadata(test_instance, fetch_all_builds=True if limit > 100 else False)
        for build_info in project_metadata['builds']:
            if len(builds) == limit:
                break
            builds.append(self.get_test_build(test_instance, build_info['number']))
        return builds

    def get_test_build(self, test_instance: TestInstance, build_number: int) -> JenkinsTestBuild:
        try:
            build_metadata = self.server.get_build_info(self.get_job_name(test_instance.resource), int(build_number))
            return JenkinsTestBuild(self, test_instance, build_metadata)
        except jenkins.NotFoundException as e:
            raise EntityNotFoundException(TestBuild, entity_id=build_number, detail=str(e))
        except jenkins.JenkinsException as e:
            raise TestingServiceException(e)

    def get_test_build_output(self, test_instance: TestInstance, build_number, offset_bytes=0, limit_bytes=131072):
        try:
            logger.debug("test_instance '%r', build_number '%r'", test_instance.name, build_number)
            logger.debug("query param: offset=%r, limit=%r", offset_bytes, limit_bytes)

            if not isinstance(offset_bytes, int) or offset_bytes < 0:
                raise ValueError(messages.invalid_log_offset)
            if not isinstance(limit_bytes, int) or limit_bytes < 0:
                raise ValueError(messages.invalid_log_limit)

            output = self.server.get_build_console_output(self.get_job_name(test_instance.resource), build_number)
            if len(output) < offset_bytes:
                raise ValueError(messages.invalid_log_offset)

            return output[offset_bytes:(offset_bytes + len(output) if limit_bytes == 0 else limit_bytes)]

        except jenkins.JenkinsException as e:
            raise TestingServiceException(e)


class TravisTestBuild(TestBuild):

    @property
    def id(self) -> str:
        return str(self.metadata['id'])

    @property
    def build_number(self) -> int:
        return self.metadata['number']

    def is_running(self) -> bool:
        return len(self.metadata['finished_at']) == 0

    @property
    def status(self) -> str:
        if self.is_running():
            return BuildStatus.RUNNING
        if self.metadata['state'] == 'passed':
            return BuildStatus.PASSED
        elif self.metadata['state'] == 'canceled':
            return BuildStatus.ABORTED
        elif self.metadata['state'] == 'failed':
            return BuildStatus.FAILED
        return BuildStatus.ERROR

    @property
    def revision(self):
        return self.metadata['commit']

    @property
    def timestamp(self) -> int:
        return datetime.datetime.strptime(
            self.metadata["started_at"], "%Y-%m-%dT%H:%M:%SZ").timestamp()

    @property
    def duration(self) -> int:
        return self.metadata['duration']

    @property
    def result(self) -> TestBuild.Result:
        return TestBuild.Result.SUCCESS \
            if self.metadata["state"] == "passed" else TestBuild.Result.FAILED

    @property
    def url(self) -> str:
        return "{}{}".format(self.testing_service.url, self.metadata['@href'])


class TravisTestingService(TestingService):
    _server = None
    _job_name = None
    __mapper_args__ = {
        'polymorphic_identity': 'travis_testing_service'
    }
    __headers__ = {
        'Travis-API-Version': '3'
    }

    def _build_headers(self, token: TestingServiceToken = None):
        headers = self.__headers__.copy()
        token = token if token else self.token
        if token:
            headers['Authorization'] = 'token {}'.format(token.secret)
        return headers

    def _build_url(self, path, params=None):
        query = "?" + urlencode(params) if params else ""
        return urljoin(self.url, path + query)

    def _get(self, path, token: TestingServiceToken = None, params=None) -> object:
        logger.debug("Getting resource: %r", self._build_url(path, params))
        response = requests.get(self._build_url(path, params), headers=self._build_headers(token))
        return response.json() if response.status_code == 200 else response

    @staticmethod
    def get_repo_id(test_instance: TestInstance):
        # extract the job name from the resource path
        logger.debug(f"Getting project metadata - resource: {test_instance.resource}")
        job_name = re.sub("(?s:.*)/", "", test_instance.resource.strip('/'))
        logger.debug(f"The repo ID: {job_name}")
        if not job_name or len(job_name) == 0:
            raise TestingServiceException(
                f"Unable to get the Jenkins job from the resource {test_instance.resource}")
        return job_name

    def is_workflow_healthy(self, test_instance: TestInstance) -> bool:
        return self.get_last_test_build(test_instance).is_successful()

    def _get_last_test_build(self, test_instance: TestInstance, state=None) -> Optional[TravisTestBuild]:
        try:
            repo_id = self.get_repo_id(test_instance)
            params = {'limit': 1, 'sort_by': 'number:desc'}
            if state:
                params['state'] = state
            response = self._get("/repo/{}/builds".format(repo_id), params=params)
            if isinstance(response, requests.Response):
                if response.status_code == 404:
                    raise EntityNotFoundException(TestBuild)
                else:
                    raise TestingServiceException(status=response.status_code,
                                                  detail=str(response.content))
            if 'builds' not in response or len(response['builds']) == 0:
                raise EntityNotFoundException(TestBuild)
            return TravisTestBuild(self, test_instance, response['builds'][0])
        except Exception as e:
            raise TestingServiceException(e)

    def get_last_test_build(self, test_instance: TestInstance) -> Optional[TravisTestBuild]:
        return self._get_last_test_build(test_instance)

    def get_last_passed_test_build(self, test_instance: TestInstance) -> Optional[TravisTestBuild]:
        return self._get_last_test_build(test_instance, state='passed')

    def get_last_failed_test_build(self, test_instance: TestInstance) -> Optional[TravisTestBuild]:
        return self._get_last_test_build(test_instance, state='failed')

    def get_project_metadata(self, test_instance: TestInstance):
        try:
            return self._get("/repo/{}".format(self.get_repo_id(test_instance)))
        except Exception as e:
            raise TestingServiceException(f"{self}: {e}")

    def get_test_builds(self, test_instance: TestInstance, limit=10):
        try:
            repo_id = self.get_repo_id(test_instance)
            response = self._get("/repo/{}/builds".format(repo_id), params={'limit': limit})
        except Exception as e:
            raise TestingServiceException(details=f"{e}")
        if isinstance(response, requests.Response):
            logger.debug(response)
            raise TestingServiceException(status=response.status_code,
                                          detail=str(response.content))
        try:
            builds = []
            for build_info in response['builds']:
                builds.append(TravisTestBuild(self, test_instance, build_info))
            return builds
        except Exception as e:
            raise TestingServiceException(details=f"{e}")

    def get_test_build(self, test_instance: TestInstance, build_number: int) -> JenkinsTestBuild:
        try:
            response = self._get("/build/{}".format(build_number))
        except Exception as e:
            raise TestingServiceException(details=f"{e}")
        if isinstance(response, requests.Response):
            if response.status_code == 404:
                raise EntityNotFoundException(TestBuild, entity_id=build_number)
            else:
                raise TestingServiceException(status=response.status_code,
                                              detail=str(response.content))
        return TravisTestBuild(self, test_instance, response)

    def get_test_build_output(self, test_instance: TestInstance, build_number, offset_bytes=0, limit_bytes=131072):
        try:
            _metadata = self._get(f"/build/{build_number}/jobs")
        except Exception as e:
            raise TestingServiceException(details=f"{e}")

        logger.debug("test_instance '%r', build_number '%r'", test_instance.name, build_number)
        logger.debug("query param: offset=%r, limit=%r", offset_bytes, limit_bytes)

        if isinstance(_metadata, requests.Response):
            if _metadata.status_code == 404:
                raise EntityNotFoundException(TestBuild, entity_id=build_number)
            else:
                raise TestingServiceException(status=_metadata.status_code,
                                              detail=str(_metadata.content))
        try:
            logger.debug("Number of jobs (test_instance '%r', build_number '%r'): %r", test_instance.name, build_number, len(_metadata['jobs']))
            if 'jobs' not in _metadata or len(_metadata['jobs']) == 0:
                logger.debug("Ops... no job found")
                return ""

            offset = 0
            output = ""
            current_job_index = 0
            while current_job_index < len(_metadata['jobs']) and \
                    (offset <= offset_bytes or limit_bytes == 0 or len(output) < limit_bytes):
                url = "/job/{}/log".format(_metadata['jobs'][current_job_index]['id'])
                logger.debug("URL: %r", url)
                response = self._get(url)
                if isinstance(response, requests.Response):
                    if response.status_code == 404:
                        raise EntityNotFoundException(TestBuild, entity_id=build_number)
                    else:
                        raise TestingServiceException(status=response.status_code,
                                                      detail=str(response.content))
                job_output = response['content']
                logger.debug("Job output length: %r", len(job_output))
                output += job_output
                offset += len(job_output)
                current_job_index += 1
            # filter output
            return output[offset_bytes:(offset_bytes + len(output) if limit_bytes == 0 else limit_bytes)]
        except Exception as e:
            logger.exception(e)
            raise TestingServiceException(details=f"{e}")
