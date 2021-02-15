from __future__ import annotations

import logging
from typing import Union
from sqlalchemy.dialects.postgresql import UUID, JSONB
from lifemonitor.db import db
from lifemonitor.auth.models import User

from lifemonitor.common import (TestingServiceException)
from lifemonitor.auth.oauth2.client.models import OAuthIdentity

import lifemonitor.api.models as models

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
                  db.ForeignKey(models.WorkflowRegistry.uuid), nullable=True)
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
                 registry: models.WorkflowRegistry = None,
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
