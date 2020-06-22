
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
    def __repr__(self):
        return '<Workflow ({}, {}); name: {}; link: {}>'.format(
            self.uuid, self.version, self.name, self.roc_link)
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
                                          back_populates="testing_suite", cascade="all, delete")
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



class TestConfiguration(db.Model):
    uuid = db.Column(UUID(as_uuid=True), primary_key=True, default=_uuid.uuid4)
    _test_suite_uuid = \
        db.Column("test_suite_uuid", UUID(as_uuid=True), db.ForeignKey(TestSuite.uuid), nullable=False)
    test_name = db.Column(db.Text, nullable=False)
    test_instance_name = db.Column(db.Text, nullable=True)
    url = db.Column(db.Text, nullable=True)
    parameters = db.Column(JSONB, nullable=True)
    # configure relationships
    testing_suite = db.relationship("TestSuite", back_populates="test_configurations")
    testing_service = db.relationship("TestingService", uselist=False, back_populates="test_configuration",
                                      cascade="all, delete")

    def __init__(self, testing_suite: TestSuite,
                 test_name, test_instance_name=None, url: str = None) -> None:
        self.testing_suite = testing_suite
        self.test_name = test_name
        self.test_instance_name = test_instance_name
        self.url = url

    def __repr__(self):
        return '<TestConfiguration {} on TestSuite {}>'.format(self.uuid, self.testing_suite.uuid)
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
class JenkinsTestingService(TestingService):
    __mapper_args__ = {
        'polymorphic_identity': 'jenkins_testing_service'
    }
