from __future__ import annotations

import logging
from typing import List, Union

import lifemonitor.api.models as models
import lifemonitor.exceptions as lm_exceptions
from lifemonitor.api.models import db
from lifemonitor.api.models.registries.registry import WorkflowRegistry
from lifemonitor.api.models.rocrate import ROCrate
from lifemonitor.auth.models import Resource, User, Permission
from lifemonitor.auth.oauth2.client.models import OAuthIdentity
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy.ext.hybrid import hybrid_property

# set module level logger
logger = logging.getLogger(__name__)


class Workflow(Resource):
    id = db.Column(db.Integer, db.ForeignKey(Resource.id), primary_key=True)

    external_ns = "external-id:"

    __mapper_args__ = {
        'polymorphic_identity': 'workflow_archive'
    }

    def __init__(self, uri=None, uuid=None, version=None, name=None) -> None:
        super().__init__(self.__class__.__name__,
                         uri=uri or f"{self.external_ns}:undefined",
                         uuid=uuid, version=version, name=name)

    def __repr__(self):
        return '<Workflow ({}, {}), name: {}>'.format(
            self.uuid, self.version, self.name)

    @hybrid_property
    def external_id(self):
        return self.uuid.replace(self.external_ns, "")

    @property
    def latest_version(self):
        return WorkflowVersion.find_latest_by_id(self.uuid)

    def add_version(self, version, uri, submitter: User, uuid=None, name=None,
                    hosting_service: models.WorkflowRegistry = None):
        try:
            if hosting_service and hasattr(hosting_service, 'get_external_id'):
                self.uri = f"{self.external_ns}{hosting_service.get_external_id(self.uuid, version, submitter)}"
        except lm_exceptions.EntityNotFoundException as e:
            raise lm_exceptions.NotAuthorizedException(details=str(e))
        return WorkflowVersion(self, uri, version, submitter, uuid=uuid, name=name,
                               hosting_service=hosting_service)

    def remove_version(self, version: WorkflowVersion):
        self.versions.remove(version)

    def check_health(self) -> dict:
        health = {'healthy': True, 'issues': []}
        for suite in self.test_suites:
            for test_instance in suite.test_instances:
                try:
                    testing_service = test_instance.testing_service
                    if not testing_service.last_test_build.is_successful():
                        health["healthy"] = False
                except lm_exceptions.TestingServiceException as e:
                    health["issues"].append(str(e))
                    health["healthy"] = "Unknown"
        return health

    @classmethod
    def get_user_workflow(cls, owner: User, uuid) -> Workflow:
        return cls.query\
            .join(Permission)\
            .filter(Permission.resource_id == cls.id, Permission.user_id == owner.id)\
            .filter(cls.uuid == uuid).first()

    @classmethod
    def get_user_workflows(cls, owner: User) -> List[Workflow]:
        return cls.query.join(Permission)\
            .filter(Permission.user_id == owner.id).all()


class WorkflowVersion(ROCrate):
    id = db.Column(db.Integer, db.ForeignKey(ROCrate.id), primary_key=True)
    submitter_id = db.Column(db.Integer, db.ForeignKey(User.id), nullable=False)
    workflow_id = \
        db.Column(db.Integer, db.ForeignKey("workflow.id"), nullable=True)
    workflow = db.relationship("Workflow", foreign_keys=[workflow_id], cascade="all",
                               backref=db.backref("versions", cascade="all, delete-orphan"))
    test_suites = db.relationship("TestSuite", back_populates="workflow",
                                  cascade="all, delete")
    submitter = db.relationship("User", uselist=False)
    roc_link = association_proxy('ro_crate', 'uri')

    __mapper_args__ = {
        'polymorphic_identity': 'workflow'
    }

    # TODO: Set additional constraint which cannot be expressed
    # with __table_args__ due to the usage of inheritance
    # db.UniqueConstraint("workflow.id", "workflow.version")
    # db.UniqueConstraint("workflow._registry_id", "workflow.external_id", "workflow.version")
    # __table_args__ = (
    #     db.UniqueConstraint(workflow_id, ROCrate.version, submitter_id),
    # )

    def __init__(self, workflow: Workflow,
                 uri, version, submitter: User, uuid=None, name=None,
                 hosting_service: models.WorkflowRegistry = None) -> None:
        super().__init__(uri, uuid=uuid, name=name,
                         version=version, hosting_service=hosting_service)
        self.submitter = submitter
        self.workflow = workflow

    def __repr__(self):
        return '<WorkflowVersion ({}, {}), name: {}, ro_crate link {}>'.format(
            self.uuid, self.version, self.name, self.roc_link)

    def check_health(self) -> dict:
        health = {'healthy': True, 'issues': []}
        for suite in self.test_suites:
            for test_instance in suite.test_instances:
                try:
                    testing_service = test_instance.testing_service
                    if not testing_service.last_test_build.is_successful():
                        health["healthy"] = False
                except lm_exceptions.TestingServiceException as e:
                    health["issues"].append(str(e))
                    health["healthy"] = "Unknown"
        return health

    @hybrid_property
    def authorizations(self):
        auths = [a for a in self._authorizations]
        if self.hosting_service:
            for auth in self.submitter.get_authorization(self.hosting_service):
                auths.append(auth)
        return auths

    @hybrid_property
    def workflow_registry(self):
        return self.hosting_service

    @hybrid_property
    def roc_link(self):
        return self.uri

    @property
    def previous_versions(self):
        return [w.version for w in self.workflow.versions if w != self and w.version < self.version]

    @property
    def previous_workflow_versions(self):
        return [w for w in self.workflow.versions if w != self and w.version < self.version]

    @property
    def status(self) -> models.WorkflowStatus:
        return models.WorkflowStatus(self)

    @property
    def is_healthy(self) -> Union[bool, str]:
        return self.check_health()["healthy"]

    def add_test_suite(self, submitter: User, test_suite_metadata):
        return models.TestSuite(self, submitter, test_suite_metadata)

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
        return cls.query.filter(WorkflowVersion.uuid == uuid) \
            .filter(WorkflowVersion.version == version).first()

    @classmethod
    def find_latest_by_id(cls, uuid):
        return cls.query.filter(WorkflowVersion.uuid == uuid) \
            .order_by(WorkflowVersion.version.desc()).first()

    @classmethod
    def find_by_submitter(cls, submitter: User):
        return cls.query.filter(WorkflowVersion.submitter_id == submitter.id).first()

    @classmethod
    def find_by_owner(cls, owner: User, uuid, version):
        return cls.query\
            .join(User, WorkflowVersion.owners)\
            .filter(User.id == owner.id)\
            .filter(WorkflowVersion.uuid == uuid)\
            .filter(WorkflowVersion.version == version).first()

    @classmethod
    def get_user_workflow(cls, owner: User, uuid, version):
            return cls.query\
            .join(Permission)\
            .filter(Permission.resource_id == cls.id, Permission.user_id == owner.id)\
            .filter(cls.uuid == uuid, cls.version == version).first()

    @classmethod
    def get_user_workflows(cls, owner: User):
        return cls.query\
            .join(Permission)\
            .filter(Permission.resource_id == cls.id, Permission.user_id == owner.id).all()

    @classmethod
    def get_registry_workflow(cls, registry_uuid, uuid, version=None):
        if version:
            return cls.query\
                .join(WorkflowRegistry, cls.hosting_service)\
                .filter(WorkflowRegistry.uuid == registry_uuid)\
                .filter(cls.uuid == uuid)\
                .filter(cls.version == version)\
                .order_by(cls.version.desc()).first()
        return cls.query\
            .join(WorkflowRegistry, cls.hosting_service)\
            .filter(WorkflowRegistry.uuid == registry_uuid)\
            .filter(cls.uuid == uuid)\
            .order_by(WorkflowVersion.version.desc()).first()
