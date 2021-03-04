from __future__ import annotations

import logging
from typing import List, Union

import lifemonitor.api.models as models
import lifemonitor.exceptions as lm_exceptions
from lifemonitor.api.models import db
from lifemonitor.api.models.registries.registry import WorkflowRegistry
from lifemonitor.api.models.rocrate import ROCrate
from lifemonitor.auth.models import Permission, Resource, User
from lifemonitor.auth.oauth2.client.models import OAuthIdentity
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm.collections import attribute_mapped_collection

# set module level logger
logger = logging.getLogger(__name__)


class Workflow(Resource):
    id = db.Column(db.Integer, db.ForeignKey(Resource.id), primary_key=True)

    external_ns = "external-id:"

    __mapper_args__ = {
        'polymorphic_identity': 'workflow_archive'
    }

    def __init__(self, uri=None, uuid=None, version=None, name=None) -> None:
        super().__init__(uri=uri or f"{self.external_ns}:undefined",
                         uuid=uuid, version=version, name=name)

    def __repr__(self):
        return '<Workflow ({}), name: {}>'.format(
            self.uuid, self.name)

    @hybrid_property
    def external_id(self):
        return self.uri.replace(self.external_ns, "")

    @hybrid_property
    def latest_version(self) -> WorkflowVersion:
        return max(self.versions.values(), key=lambda v: v.version)

    def add_version(self, version, uri, submitter: User, uuid=None, name=None,
                    hosting_service: models.WorkflowRegistry = None):
        try:
            uuid = self.uuid if uuid is None else uuid
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
        try:
            return cls.query\
                .join(Permission)\
                .filter(Permission.resource_id == cls.id, Permission.user_id == owner.id)\
                .filter(cls.uuid == uuid).first()
        except Exception as e:
            raise lm_exceptions.EntityNotFoundException(WorkflowRegistry,
                                                        entity_id=f"{uuid}",
                                                        exception=str(e))

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
                               backref=db.backref("versions", cascade="all, delete-orphan",
                                                  collection_class=attribute_mapped_collection('version')))
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
    def workflow_registry(self) -> models.WorkflowRegistry:
        return self.hosting_service

    @hybrid_property
    def roc_link(self) -> str:
        return self.uri

    @property
    def latest_version(self) -> bool:
        return self.workflow.latest_version.version == self.version

    @property
    def previous_versions(self) -> List[str]:
        return [w.version for w in self.workflow.versions.values() if w != self and w.version < self.version]

    @property
    def previous_workflow_versions(self) -> List[models.WorkflowVersion]:
        return [w for w in self.workflow.versions.values() if w != self and w.version < self.version]

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

    @classmethod
    def all(cls) -> List[WorkflowVersion]:
        return cls.query.all()

    @classmethod
    def get_submitter_versions(cls, submitter: User) -> List[WorkflowVersion]:
        return cls.query.filter(WorkflowVersion.submitter_id == submitter.id).all()

    @classmethod
    def get_user_workflow(cls, owner: User, uuid, version) -> WorkflowVersion:
        try:
            return cls.query\
                .join(Permission)\
                .filter(Permission.resource_id == cls.id, Permission.user_id == owner.id)\
                .filter(cls.uuid == uuid, cls.version == version).first()
        except Exception as e:
            raise lm_exceptions.EntityNotFoundException(WorkflowVersion,
                                                        entity_id=f"{uuid}_{version}",
                                                        exception=str(e))

    @classmethod
    def get_user_workflows(cls, owner: User) -> List[WorkflowVersion]:
        return cls.query\
            .join(Permission)\
            .filter(Permission.resource_id == cls.id, Permission.user_id == owner.id).all()

    @classmethod
    def get_hosted_workflow_version(cls, hosting_service: Resource, uuid, version) -> List[WorkflowVersion]:
        # TODO: replace WorkflowRegistry with a more general Entity
        try:
            return cls.query\
                .join(WorkflowRegistry, cls.hosting_service)\
                .filter(WorkflowRegistry.uuid == hosting_service.uuid)\
                .filter(cls.uuid == uuid)\
                .filter(cls.version == version)\
                .order_by(WorkflowVersion.version.desc()).one()
        except Exception as e:
            raise lm_exceptions.EntityNotFoundException(WorkflowVersion,
                                                        entity_id=f"{uuid}_{version}",
                                                        exception=str(e))

    @classmethod
    def get_hosted_workflow_versions(cls, hosting_service: Resource) -> List[WorkflowVersion]:
        # TODO: replace WorkflowRegistry with a more general Entity
        return cls.query\
            .join(WorkflowRegistry, cls.hosting_service)\
            .filter(WorkflowRegistry.uuid == hosting_service.uuid)\
            .order_by(WorkflowVersion.version.desc()).all()
