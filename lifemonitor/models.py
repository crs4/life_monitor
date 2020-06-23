
import os

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.dialects.postgresql import UUID, JSONB

db = SQLAlchemy()


def db_uri():
    if os.getenv('DATABASE_URI'):
        uri = os.getenv('DATABASE_URI')
    else:
        uri = "postgresql://{user}:{passwd}@{host}/{dbname}".format(
            user=os.getenv('POSTGRESQL_USERNAME'),
            passwd=os.getenv('POSTGRESQL_PASSWORD', ''),
            host=os.getenv('POSTGRESQL_HOST'),
            dbname=os.getenv('POSTGRESQL_DATABASE'))
    return uri


def config_db_access(flask_app):
    flask_app.config['SQLALCHEMY_DATABASE_URI'] = db_uri()
    # FSADeprecationWarning: SQLALCHEMY_TRACK_MODIFICATIONS adds significant
    # overhead and will be disabled by default in the future.  Set it to True
    # or False to suppress this warning.
    flask_app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    db.init_app(flask_app)
    db.create_all()


class WorkflowRepository(object):
    __instance = None

    @classmethod
    def get_instance(cls) -> WorkflowRepository:
        if not cls.__instance:
            cls.__instance = cls()
        return cls.__instance

    def __init__(self):
        if self.__instance:
            raise Exception("WorkflowRepository instance already exists!")
        self.__instance = self
        self._url = os.environ["WORKFLOW_REPOSITORY_URL"]
        self._token = os.environ["WORKFLOW_REPOSITORY_TOKEN"]

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
        self.repository = WorkflowRepository.get_instance()

    @property
    def roc_link(self):
        # return self.repository.build_ro_link(self) if "repository" in self else None
        return ""

    def __repr__(self):
        return '<Workflow ({}, {}); name: {}; link: {}>'.format(
            self.uuid, self.version, self.name, self.roc_link)

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

    def is_workflow_healthy(self) -> bool:
        raise NotImplementedException()

    def last_test_build(self) -> TestBuild:
        raise NotImplementedException()

    def last_successful_test_build(self) -> TestBuild:
        raise NotImplementedException()

    def last_failed_test_build(self) -> TestBuild:
        raise NotImplementedException()

    def all_test_builds(self) -> list:
        raise NotImplementedException()

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
        return self.metadata

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
    __mapper_args__ = {
        'polymorphic_identity': 'jenkins_testing_service'
    }

    def __init__(self, test_configuration: TestConfiguration, url: str) -> None:
        super().__init__(test_configuration, url)
        self._server = jenkins.Jenkins(url)

    def is_workflow_healthy(self) -> bool:
        return self.last_test_build().is_successful()

    def last_test_build(self) -> TestBuild:
        return self.get_test_build(self.metadata['lastBuild']['number'])

    def last_successful_test_build(self) -> TestBuild:
        return self.get_test_build(self.metadata['lastSuccessfulBuild']['number'])

    def last_failed_test_build(self) -> TestBuild:
        return self.get_test_build(self.metadata['lastFailedBuild']['number'])

    def all_test_builds(self) -> list:
        builds = []
        for build_info in self.metadata['builds']:
            builds.append(self.get_test_build(build_info['number']))
        return builds

    def get_test_build(self, build_number) -> JenkinsTestBuild:
        try:
            build_metadata = self._server.get_build_info(self.test_instance_name, build_number)
            return JenkinsTestBuild(self, build_metadata)
        except jenkins.JenkinsException as e:
            raise LifeMonitorException(e)

    def get_test_build_output(self, build_number):
        try:
            return self._server.get_build_console_output(self.test_instance_name, build_number)
        except jenkins.JenkinsException as e:
            raise LifeMonitorException(e)
