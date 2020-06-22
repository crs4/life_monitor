
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


class Workflow(db.Model):
    _id = db.Column('id', db.Integer, primary_key=True)
    uuid = db.Column(UUID)
    version = db.Column(db.Text)
    name = db.Column(db.Text, nullable=True)
    roc_metadata = db.Column(JSONB, nullable=True)
    # additional relational specs
    __tablename__ = "workflow"
    __table_args__ = tuple(
        db.UniqueConstraint(uuid, version)
    )

    def __repr__(self):
        return '<Workflow ({:r}, {:r}); name: {:r}; link: {:r}>'.format(
            self.workflow_id, self.version,
            self.name, self.roc_link)


class TestingProject(db.Model):
    uuid = db.Column(UUID(as_uuid=True), primary_key=True, default=_uuid.uuid4)
    _workflow_id = db.Column("workflow_id", db.Integer, db.ForeignKey(Workflow._id), nullable=False)
    test_definition = db.Column(JSONB, nullable=True)
    # additional relational specs
    __table_args__ = tuple(
        # db.ForeignKeyConstraint([workflow_uuid, workflow_version], [Workflow.uuid, Workflow.version])
    )





class TestInstance(db.Model):
    test_instance_id = db.Column(UUID(as_uuid=True), primary_key=True)
    test_proj_id = \
       db.Column(UUID(as_uuid=True), db.ForeignKey(TestingProject.testing_project_id), nullable=False)
    url = db.Column(db.Text(), nullable=False)
    service_type = db.Column(db.Text(), db.ForeignKey(TestServiceType.service_type), nullable=False)
    instance_parameters = db.Column(JSONB(), nullable=True)


class TestInstanceToken(db.Model):
    testing_instance_id = db.Column(UUID(as_uuid=True),
        db.ForeignKey(TestInstance.test_instance_id), primary_key=True)
    key = db.Column(db.Text(), nullable=False)
    secret = db.Column(db.Text(), nullable=False)
class TestingService(db.Model):
    uuid = db.Column("uuid", UUID(as_uuid=True), db.ForeignKey(TestInstance.uuid), primary_key=True)
    _type = db.Column("type", db.String, nullable=False)
    _key = db.Column("key", db.Text, nullable=True)
    _secret = db.Column("secret", db.Text, nullable=True)
    url = db.Column(db.Text, nullable=False)
    __mapper_args__ = {
        'polymorphic_on': _type,
        'polymorphic_identity': 'testing_service'
    }
class JenkinsTestingService(TestingService):
    __mapper_args__ = {
        'polymorphic_identity': 'jenkins_testing_service'
    }
