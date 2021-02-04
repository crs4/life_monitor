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
from lifemonitor.api import registries

from lifemonitor.common import (SpecificationNotValidException, EntityNotFoundException,
                                SpecificationNotDefinedException, TestingServiceNotSupportedException,
                                NotImplementedException, TestingServiceException)
from lifemonitor.utils import download_url, to_camel_case
from lifemonitor.auth.oauth2.client.models import OAuthIdentity
import lifemonitor.test_metadata as tm
from urllib.parse import urljoin, urlencode

# set module level logger
logger = logging.getLogger(__name__)


class WorkflowRegistryClient(ABC):

    def __init__(self, registry: WorkflowRegistry):
        self._registry = registry
        try:
            self._oauth2client: RemoteApp = getattr(oauth2_registry, self.registry.name)
        except AttributeError:
            raise RuntimeError(f"Unable to find a OAuth2 client for the {self.name} service")

    @property
    def registry(self):
        return self._registry

    def _get_access_token(self, user_id):
        # get the access token related with the user of this client registry
        return OAuthIdentity.find_by_user_id(user_id, self.registry.name).token

    def _get(self, user, *args, **kwargs):
        # update token
        self._oauth2client.token = self._get_access_token(user.id)
        return self._oauth2client.get(*args, **kwargs)

    def download_url(self, url, user, target_path=None):
        return download_url(url, target_path, self._get_access_token(user.id)["access_token"])

    def get_external_id(self, uuid, version, user: User) -> str:
        """ Return CSV of uuid and version"""
        return ",".join([str(uuid), str(version)])

    @abstractmethod
    def build_ro_link(self, w: Workflow) -> str:
        pass

    @abstractmethod
    def get_workflows_metadata(self, user, details=False):
        pass

    @abstractmethod
    def get_workflow_metadata(self, user, w: Union[Workflow, str]):
        pass

    @abstractmethod
    def filter_by_user(workflows: list, user: User):
        pass


class WorkflowRegistry(db.Model):

    uuid = db.Column(UUID(as_uuid=True), primary_key=True, default=_uuid.uuid4)
    uri = db.Column(db.Text, unique=True)
    type = db.Column(db.String, nullable=False)
    _client_id = db.Column(db.Integer, db.ForeignKey('client.id', ondelete='CASCADE'))
    _server_id = db.Column(db.Integer, db.ForeignKey('oauth2_identity_provider.id', ondelete='CASCADE'))
    client_credentials = db.relationship("Client", uselist=False, cascade="all, delete")
    server_credentials = db.relationship("OAuth2IdentityProvider", uselist=False, cascade="all, delete")
    registered_workflows = db.relationship("Workflow",
                                           back_populates="workflow_registry", cascade="all, delete")
    client_id = association_proxy('client_credentials', 'client_id')
    name = association_proxy('server_credentials', 'name')
    # _uri = association_proxy('server_credentials', 'api_base_url')

    _client = None

    __mapper_args__ = {
        'polymorphic_identity': 'workflow_registry',
        'polymorphic_on': type,
    }

    def __init__(self, client_credentials, server_credentials):
        self.__instance = self
        self.uri = server_credentials.api_base_url
        self.client_credentials = client_credentials
        self.server_credentials = server_credentials
        self._client = None

    @property
    def name(self):
        return self.server_credentials.name

    @name.setter
    def name(self, value):
        self.server_credentials.name = value

    @property
    def client(self) -> WorkflowRegistryClient:
        if self._client is None:
            return registries.get_registry_client_class(self.type)(self)
        return self._client

    def build_ro_link(self, w: Workflow) -> str:
        return self.client.build_ro_link(w)

    def download_url(self, url, user, target_path=None):
        return self.client.download_url(url, user, target_path=target_path)

    @property
    def users(self) -> List[User]:
        return self.get_users()

    def get_user(self, user_id) -> User:
        for u in self.users:
            logger.debug(f"Checking {u.id} {user_id}")
            if u.id == user_id:
                return u
        raise EntityNotFoundException(User, entity_id=user_id)

    def get_users(self) -> List[User]:
        try:
            return [i.user for i in OAuthIdentity.query
                    .filter(OAuthIdentity.provider == self.server_credentials).all()]
        except Exception as e:
            raise EntityNotFoundException(e)

    def add_workflow(self, workflow_uuid, workflow_version,
                     workflow_submitter: User,
                     roc_link, roc_metadata=None,
                     external_id=None, name=None):
        if external_id is None:
            try:
                external_id = self.client.get_external_id(
                    workflow_uuid, workflow_version, workflow_submitter)
            except Exception as e:
                logger.exception(e)

        return Workflow(self, workflow_submitter,
                        workflow_uuid, workflow_version, roc_link,
                        roc_metadata=roc_metadata,
                        external_id=external_id, name=name)

    def save(self):
        db.session.add(self)
        db.session.commit()

    def delete(self):
        db.session.delete(self)
        db.session.commit()

    def get_workflow(self, uuid, version=None):
        try:
            if not version:
                return Workflow.query.with_parent(self)\
                    .filter(Workflow.uuid == uuid).order_by(Workflow.version.desc()).first()
            return Workflow.query.with_parent(self)\
                .filter(Workflow.uuid == uuid).filter(Workflow.version == version).first()
        except Exception as e:
            raise EntityNotFoundException(e)

    def get_workflow_versions(self, uuid):
        try:
            workflows = Workflow.query.with_parent(self)\
                .filter(Workflow.uuid == uuid).order_by(Workflow.version.desc())
            return {w.version: w for w in workflows}
        except Exception as e:
            raise EntityNotFoundException(e)

    def get_user_workflows(self, user: User):
        return self.client.filter_by_user(self.registered_workflows, user)

    @classmethod
    def all(cls):
        return cls.query.all()

    @classmethod
    def find_by_id(cls, uuid) -> WorkflowRegistry:
        try:
            return cls.query.get(uuid)
        except Exception as e:
            raise EntityNotFoundException(WorkflowRegistry, entity_id=uuid, exception=e)

    @classmethod
    def find_by_name(cls, name):
        try:
            return cls.query.filter(WorkflowRegistry.server_credentials.has(name=name)).one()
        except Exception as e:
            raise EntityNotFoundException(WorkflowRegistry, entity_id=name, exception=e)

    @classmethod
    def find_by_uri(cls, uri):
        try:
            return cls.query.filter(WorkflowRegistry.uri == uri).one()
        except Exception as e:
            raise EntityNotFoundException(WorkflowRegistry, entity_id=uri, exception=e)

    @classmethod
    def find_by_client_id(cls, client_id):
        try:
            return cls.query.filter_by(client_id=client_id).first()
        except Exception as e:
            raise EntityNotFoundException(WorkflowRegistry, entity_id=client_id, exception=e)

    @staticmethod
    def new_instance(registry_type, client_credentials, server_credentials):
        return registries.get_registry_class(registry_type)(client_credentials,
                                                            server_credentials)


class AggregateTestStatus:
    ALL_PASSING = "all_passing"
    SOME_PASSING = "some_passing"
    ALL_FAILING = "all_failing"
    NOT_AVAILABLE = "not_available"


class Status:

    def __init__(self) -> None:
        self._status = AggregateTestStatus.NOT_AVAILABLE
        self._latest_builds = None
        self._availability_issues = None

    @property
    def aggregated_status(self):
        return self._status

    @property
    def latest_builds(self):
        return self._latest_builds.copy()

    @property
    def availability_issues(self):
        return self._availability_issues.copy()

    @staticmethod
    def _update_status(current_status, build_passing):
        status = current_status
        if status == AggregateTestStatus.NOT_AVAILABLE:
            if build_passing:
                status = AggregateTestStatus.ALL_PASSING
            elif not build_passing:
                status = AggregateTestStatus.ALL_FAILING
        elif status == AggregateTestStatus.ALL_PASSING:
            if not build_passing:
                status = AggregateTestStatus.SOME_PASSING
        elif status == AggregateTestStatus.ALL_FAILING:
            if build_passing:
                status = AggregateTestStatus.SOME_PASSING
        return status

    @staticmethod
    def check_status(suites):
        status = AggregateTestStatus.NOT_AVAILABLE
        latest_builds = []
        availability_issues = []

        if len(suites) == 0:
            availability_issues.append({
                "issue": "No test suite configured for this workflow"
            })

        for suite in suites:
            if len(suite.test_instances) == 0:
                availability_issues.append({
                    "issue": f"No test instances configured for suite {suite}"
                })
            for test_instance in suite.test_instances:
                try:
                    testing_service = test_instance.testing_service
                    latest_build = testing_service.last_test_build
                    if latest_build is None:
                        availability_issues.append({
                            "service": testing_service.uri,
                            "instance": test_instance,  # WHAT?
                            "issue": "No build found"
                        })
                    else:
                        latest_builds.append(latest_build)
                        status = WorkflowStatus._update_status(status, latest_build.is_successful())
                except TestingServiceException as e:
                    availability_issues.append({
                        "service": testing_service.uri,
                        "issue": str(e)
                    })
                    logger.exception(e)
        # update the current status
        return status, latest_builds, availability_issues


class WorkflowStatus(Status):

    def __init__(self, workflow: Workflow) -> None:
        self.workflow = workflow
        self._status, self._latest_builds, self._availability_issues = WorkflowStatus.check_status(self.workflow.test_suites)


class SuiteStatus(Status):

    def __init__(self, suite: TestSuite) -> None:
        self.suite = suite
        self._status, self._latest_builds, self._availability_issues = Status.check_status([suite])


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
                  db.ForeignKey(WorkflowRegistry.uuid), nullable=False)
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

    def __init__(self, registry: WorkflowRegistry, submitter: User,
                 uuid, version, rock_link,
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
                    testing_service = TestingService.new_instance(
                        instance.service.type,
                        instance.service.url,
                        instance.service.resource
                    )
                    logger.debug("Created TestService: %r", testing_service)
                    test_instance = TestInstance(self, self.submitter,
                                                 test.name, testing_service)
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
                          test_name, testing_service_type, testing_service_url):
        testing_service = \
            TestingService.new_instance(testing_service_type, testing_service_url)
        test_instance = TestInstance(self, submitter, test_name, testing_service)
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


class TestingService(db.Model):
    uuid = db.Column("uuid", UUID(as_uuid=True), db.ForeignKey(TestInstance.uuid), primary_key=True)
    _type = db.Column("type", db.String, nullable=False)
    _key = db.Column("key", db.Text, nullable=True)
    _secret = db.Column("secret", db.Text, nullable=True)
    url = db.Column(db.Text, nullable=False, unique=True)
    # configure nested object
    token = db.composite(TestingServiceToken, _key, _secret)
    # configure relationships
    test_instances = db.relationship("TestInstance", back_populates="testing_service")

    __mapper_args__ = {
        'polymorphic_on': _type,
        'polymorphic_identity': 'testing_service'
    }

    def __init__(self, url: str, token: TestingServiceToken = None) -> None:
        self.url = url
        self.token = token

    def __repr__(self):
        return f'<TestingService {self.url}, ({self.uuid})>'

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

    def get_test_builds(self, test_instance: TestInstance) -> list:
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
        try:
            service_class = globals()["{}TestingService".format(to_camel_case(service_type))]
        except KeyError:
            raise TestingServiceNotSupportedException(f"Not supported testing service type '{service_type}'")
            return service_class(url)
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

    def __init__(self, testing_service: TestingService, metadata) -> None:
        self.testing_service = testing_service
        self._metadata = metadata

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
    @abstractmethod
    def output(self) -> str:
        pass

    @property
    def last_logs(self) -> str:
        return self.output

    @property
    @abstractmethod
    def result(self) -> TestBuild.Result:
        pass

    @property
    @abstractmethod
    def url(self) -> str:
        pass

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
        return str(self.metadata['number'])

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
    _job_name = None
    __mapper_args__ = {
        'polymorphic_identity': 'jenkins_testing_service'
    }

    def __init__(self, url: str, resource: str) -> None:
        super().__init__(url, resource)
        try:
            self._server = jenkins.Jenkins(self.url)
        except Exception as e:
            raise TestingServiceException(e)

    @property
    def server(self) -> jenkins.Jenkins:
        if not self._server:
            self._server = jenkins.Jenkins(self.url)
        return self._server

    @property
    def job_name(self):
        # extract the job name from the resource path
        if self._job_name is None:
            logger.debug(f"Getting project metadata - resource: {self.resource}")
            self._job_name = re.sub("(?s:.*)/", "", self.resource.strip('/'))
            logger.debug(f"The job name: {self._job_name}")
            if not self._job_name or len(self._job_name) == 0:
                raise TestingServiceException(
                    f"Unable to get the Jenkins job from the resource {self._job_name}")
        return self._job_name

    @property
    def is_workflow_healthy(self) -> bool:
        return self.last_test_build.is_successful()

    @property
    def last_test_build(self) -> Optional[JenkinsTestBuild]:
        if self.project_metadata['lastBuild']:
            return self.get_test_build(self.project_metadata['lastBuild']['number'])
        return None

    @property
    def last_passed_test_build(self) -> Optional[JenkinsTestBuild]:
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
        return self.get_project_metadata()

    def get_project_metadata(self, fetch_all_builds=False):
        try:
            return self.server.get_job_info(self.job_name, fetch_all_builds=fetch_all_builds)
        except jenkins.JenkinsException as e:
            raise TestingServiceException(f"{self}: {e}")

    def get_test_builds(self, limit=10):
        builds = []
        project_metadata = self.get_project_metadata(fetch_all_builds=True if limit > 100 else False)
        for build_info in project_metadata['builds']:
            if len(builds) == limit:
                break
            builds.append(self.get_test_build(build_info['number']))
        return builds

    def get_test_build(self, build_number: int) -> JenkinsTestBuild:
        try:
            build_metadata = self.server.get_build_info(self.job_name, int(build_number))
            return JenkinsTestBuild(self, build_metadata)
        except jenkins.NotFoundException as e:
            raise EntityNotFoundException(TestBuild, entity_id=build_number, detail=str(e))
        except jenkins.JenkinsException as e:
            raise TestingServiceException(e)

    def get_test_build_output(self, build_number):
        try:
            return self.server.get_build_console_output(self.job_name, build_number)
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
    def output(self) -> str:
        return self.testing_service.get_test_build_output(self.build_number)

    @property
    def result(self) -> TestBuild.Result:
        return TestBuild.Result.SUCCESS \
            if self.metadata["result"] == "passed" else TestBuild.Result.FAILED

    @property
    def url(self) -> str:
        return "{}{}".format(self.testing_service.url, self.metadata['@href'])


class TravisTestingService(TestingService):
    _server = None
    _job_name = None
    __mapper_args__ = {
        'polymorphic_identity': 'travis_testing_service'
    }

    def __init__(self, url: str, resource: str, token: TestingServiceToken) -> None:
        super().__init__(url, resource)
        self.token = token

    def _build_headers(self, token: TestingServiceToken = None):
        token = token or self.token
        return {
            'Travis-API-Version': '3',
            'Authorization': 'token {}'.format(token.secret)
        }

    def _build_url(self, path, params=None):
        query = "?" + urlencode(params) if params else ""
        return urljoin(self.url, path + query)

    def _get(self, path, token: TestingServiceToken = None, params=None) -> object:
        logger.debug("Getting resource: %r", self._build_url(path, params))
        response = requests.get(self._build_url(path, params), headers=self._build_headers(token))
        return response.json() if response.status_code == 200 else response

    @property
    def repo_id(self):
        # extract the job name from the resource path
        if self._job_name is None:
            logger.debug(f"Getting project metadata - resource: {self.resource}")
            self._job_name = re.sub("(?s:.*)/", "", self.resource.strip('/'))
            logger.debug(f"The job name: {self._job_name}")
            if not self._job_name or len(self._job_name) == 0:
                raise TestingServiceException(
                    f"Unable to get the Jenkins job from the resource {self._job_name}")
        return self._job_name

    @property
    def is_workflow_healthy(self) -> bool:
        return self.last_test_build.is_successful()

    def _get_last_test_build(self, state=None) -> Optional[TravisTestBuild]:
        try:
            params = {'limit': 1, 'sort_by': 'number:desc'}
            if state:
                params['state'] = state
            response = self._get("/repo/{}/builds".format(self.repo_id), params=params)
            if isinstance(response, requests.Response):
                if response.status_code == 404:
                    raise EntityNotFoundException(TestBuild)
                else:
                    raise TestingServiceException(status=response.status_code,
                                                  detail=str(response.content))
            if 'builds' not in response or len(response['builds']) == 0:
                raise EntityNotFoundException(TestBuild)
            return TravisTestBuild(self, response['builds'][0])
        except Exception as e:
            raise TestingServiceException(e)

    @property
    def last_test_build(self) -> Optional[TravisTestBuild]:
        return self._get_last_test_build()

    @property
    def last_passed_test_build(self) -> Optional[TravisTestBuild]:
        return self._get_last_test_build(state='passed')

    @property
    def last_failed_test_build(self) -> Optional[TravisTestBuild]:
        return self._get_last_test_build(state='failed')

    @property
    def project_metadata(self):
        try:
            return self._get("/repo/{}".format(self.repo_id))
        except Exception as e:
            raise TestingServiceException(f"{self}: {e}")

    def get_test_builds(self, limit=10):
        try:
            builds = []
            response = self._get("/repo/{}/builds".format(self.repo_id), params={'limit': limit})
            if isinstance(response, requests.Response):
                logger.debug(response)
                raise TestingServiceException(status=response.status_code,
                                              detail=str(response.content))
            for build_info in response['builds']:
                builds.append(TravisTestBuild(self, build_info))
            return builds
        except Exception as e:
            raise TestingServiceException(details=f"{e}")

    def get_test_build(self, build_number: int) -> JenkinsTestBuild:
        try:
            response = self._get("/build/{}".format(build_number))
            if isinstance(response, requests.Response):
                if response.status_code == 404:
                    raise EntityNotFoundException(TestBuild, entity_id=build_number)
                else:
                    raise TestingServiceException(status=response.status_code,
                                                  detail=str(response.content))
            return TravisTestBuild(self, response)
        except Exception as e:
            raise TestingServiceException(details=f"{e}")
