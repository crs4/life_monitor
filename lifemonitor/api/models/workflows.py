from __future__ import annotations
from lifemonitor.api.models.rocrate import ROCrate

import logging
from typing import Union

import lifemonitor.api.models as models
import lifemonitor.exceptions as lm_exceptions
from lifemonitor.api.models import db
from lifemonitor.auth.models import ExternalResource, User
from lifemonitor.auth.oauth2.client.models import OAuthIdentity
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy.ext.hybrid import hybrid_property

# set module level logger
logger = logging.getLogger(__name__)


class WorkflowVersion(ROCrate):
    external_id = db.Column(db.String, nullable=True)
    workflow_registry_id = \
        db.Column(db.Integer, db.ForeignKey("workflow_registry.id"), nullable=True)

    workflow_registry = db.relationship("WorkflowRegistry",
                                        foreign_keys=[workflow_registry_id],
                                        backref="registered_workflows")
    name = db.Column(db.Text, nullable=True)
    test_suites = db.relationship("TestSuite", back_populates="workflow", cascade="all, delete")
    submitter = db.relationship("User", uselist=False)
    ro_crate = db.relationship("ExternalResource", uselist=False)
    roc_link = association_proxy('ro_crate', 'uri')

    __mapper_args__ = {
        'polymorphic_identity': 'workflow'
    }

    # TODO: Set additional constraint which cannot be expressed
    # with __table_args__ due to the usage of inheritance
    # db.UniqueConstraint("workflow.id", "workflow.version")
    # db.UniqueConstraint("workflow._registry_id", "workflow.external_id", "workflow.version")

    def __init__(self,
                 uuid, version, submitter: User, roc_link,
                 registry: models.WorkflowRegistry = None,
                 roc_metadata=None, external_id=None, name=None) -> None:
        super().__init__(self.__class__.__name__,
                         roc_link, uuid=uuid, name=name, version=version)
        self.roc_metadata = roc_metadata
        self.external_id = external_id
        self.workflow_registry = registry
        self.submitter = submitter

    def __repr__(self):
        return '<Workflow ({}, {}), name: {}, ro_crate link {}>'.format(
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
    def roc_link(self):
        return self.uri

    @property
    def previous_versions(self):
        return list(self.previous_workflow_versions.keys())

    @property
    def previous_workflow_versions(self):
        return {k: v
                for k, v in self.workflow_registry.get_workflow_versions(self.uuid).items()
                if k != self.version}

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
        return cls.query.filter(Workflow.uuid == uuid) \
            .filter(Workflow.version == version).first()

    @classmethod
    def find_latest_by_id(cls, uuid):
        return cls.query.filter(Workflow.uuid == uuid) \
            .order_by(Workflow.version.desc()).first()

    @classmethod
    def find_by_submitter(cls, submitter: User):
        return cls.query.filter(Workflow.submitter_id == submitter.id).first()
