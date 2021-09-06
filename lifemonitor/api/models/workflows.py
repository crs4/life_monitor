# Copyright (c) 2020-2021 CRS4
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

from __future__ import annotations

import logging
from typing import List, Union

import lifemonitor.api.models as models
import lifemonitor.exceptions as lm_exceptions
from lifemonitor import utils as lm_utils
from lifemonitor.api.models import db
from lifemonitor.api.models.registries.registry import WorkflowRegistry
from lifemonitor.api.models.rocrate import ROCrate
from lifemonitor.auth.models import Permission, Resource, User, HostingService
from lifemonitor.auth.oauth2.client.models import OAuthIdentity
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm.collections import (MappedCollection,
                                        attribute_mapped_collection,
                                        collection)
from sqlalchemy.orm.exc import NoResultFound

# set module level logger
logger = logging.getLogger(__name__)


class Workflow(Resource):
    id = db.Column(db.Integer, db.ForeignKey(Resource.id), primary_key=True)

    external_ns = "external-id:"

    __mapper_args__ = {
        'polymorphic_identity': 'workflow'
    }

    def __init__(self, uri=None, uuid=None, identifier=None, version=None, name=None) -> None:
        super().__init__(uri=uri or f"{self.external_ns}",
                         uuid=uuid, version=version, name=name)
        if identifier is not None:
            self.external_id = identifier

    def __repr__(self):
        return '<Workflow ({}), name: {}>'.format(
            self.uuid, self.name)

    @hybrid_property
    def external_id(self):
        r = self.uri.replace(self.external_ns, "")
        return r if len(r) > 0 else None

    @external_id.setter
    def external_id(self, value):
        self.uri = f"{self.external_ns}{value}"

    @hybrid_property
    def latest_version(self) -> WorkflowVersion:
        return max(self.versions.values(), key=lambda v: v.version)

    def add_version(self, version, uri, submitter: User, uuid=None, name=None,
                    hosting_service: models.WorkflowRegistry = None):
        if hosting_service:
            if self.external_id and hasattr(hosting_service, 'get_external_uuid'):
                try:
                    self.uuid = hosting_service.get_external_uuid(self.external_id, version, submitter)
                except RuntimeError as e:
                    raise lm_exceptions.NotAuthorizedException(details=str(e))
            elif not self.external_id and hasattr(hosting_service, 'get_external_id'):
                try:
                    self.external_id = hosting_service.get_external_id(self.uuid, version, submitter)
                except lm_exceptions.EntityNotFoundException:
                    logger.warning("Unable to associate an external ID to the workflow")
        return WorkflowVersion(self, uri, version, submitter, uuid=uuid, name=name,
                               hosting_service=hosting_service)

    def remove_version(self, version: WorkflowVersion):
        self.versions.remove(version)

    def get_user_versions(self, user: models.User) -> List[models.WorkflowVersion]:
        return models.WorkflowVersion.query\
            .join(Permission, Permission.resource_id == models.WorkflowVersion.id)\
            .filter(models.WorkflowVersion.workflow_id == self.id)\
            .filter(Permission.user_id == user.id)\
            .all()

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
                .filter(cls.uuid == lm_utils.uuid_param(uuid)).one()
        except NoResultFound as e:
            logger.debug(e)
            return None
        except Exception as e:
            raise lm_exceptions.LifeMonitorException(detail=str(e), stack=str(e))

    @classmethod
    def get_user_workflows(cls, owner: User) -> List[Workflow]:
        return cls.query.join(Permission)\
            .filter(Permission.user_id == owner.id).all()


class WorkflowVersionCollection(MappedCollection):

    def __init__(self) -> None:
        super().__init__(lambda wv: wv.workflow.uuid)

    @collection.internally_instrumented
    def __setitem__(self, key, value, _sa_initiator=None):
        current_value = self.get(key, set())
        current_value.add(value)
        super(WorkflowVersionCollection, self).__setitem__(key, current_value, _sa_initiator)

    @collection.internally_instrumented
    def __delitem__(self, key, _sa_initiator=None):
        super(WorkflowVersionCollection, self).__delitem__(key, _sa_initiator)


class WorkflowVersion(ROCrate):
    id = db.Column(db.Integer, db.ForeignKey(ROCrate.id), primary_key=True)
    submitter_id = db.Column(db.Integer, db.ForeignKey(User.id), nullable=True)
    workflow_id = \
        db.Column(db.Integer, db.ForeignKey("workflow.id"), nullable=False)
    workflow = db.relationship("Workflow", foreign_keys=[workflow_id], cascade="all",
                               backref=db.backref("versions", cascade="all, delete-orphan",
                                                  collection_class=attribute_mapped_collection('version')))
    test_suites = db.relationship("TestSuite", back_populates="workflow_version",
                                  cascade="all, delete")
    submitter = db.relationship("User", uselist=False,
                                backref=db.backref("workflows", cascade="all, delete-orphan",
                                                   collection_class=WorkflowVersionCollection))
    roc_link = association_proxy('ro_crate', 'uri')

    __mapper_args__ = {
        'polymorphic_identity': 'workflow_version'
    }

    def __init__(self, workflow: Workflow,
                 uri, version, submitter: User, uuid=None, name=None,
                 hosting_service: HostingService = None) -> None:
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

    @property
    def external_link(self) -> str:
        if self.hosting_service is None:
            return self.uri
        return self.hosting_service.get_external_link(self)

    @hybrid_property
    def authorizations(self):
        auths = [a for a in self._authorizations]
        if self.hosting_service and self.submitter:
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
    def is_latest(self) -> bool:
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

    def add_test_suite(self, submitter: User,
                       name: str = None, roc_suite: str = None, definition: object = None):
        return models.TestSuite(self, submitter, name=name, roc_suite=roc_suite, definition=definition)

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

    def delete(self):
        if len(self.workflow.versions) > 1:
            workflow = self.workflow
            self.workflow.remove_version(self)
            workflow.save()
        else:
            self.workflow.delete()

    @classmethod
    def all(cls) -> List[WorkflowVersion]:
        return cls.query.all()

    @classmethod
    def get_submitter_versions(cls, submitter: User) -> List[WorkflowVersion]:
        return cls.query.filter(WorkflowVersion.submitter_id == submitter.id).all()

    @classmethod
    def get_user_workflow_version(cls, owner: User, uuid, version) -> WorkflowVersion:
        try:
            return cls.query\
                .join(Workflow, Workflow.id == cls.workflow_id)\
                .join(Permission, Permission.resource_id == cls.id)\
                .filter(Workflow.uuid == lm_utils.uuid_param(uuid))\
                .filter(Permission.user_id == owner.id)\
                .filter(cls.version == version).one()
        except NoResultFound as e:
            logger.exception(e)
            return None
        except Exception as e:
            raise lm_exceptions.LifeMonitorException(detail=str(e), stack=str(e))

    @classmethod
    def get_user_workflow_versions(cls, owner: User) -> List[WorkflowVersion]:
        return cls.query\
            .join(Permission)\
            .filter(Permission.resource_id == cls.id, Permission.user_id == owner.id).all()

    @classmethod
    def get_hosted_workflow_version(cls, hosting_service: HostingService, uuid, version) -> List[WorkflowVersion]:
        try:
            return cls.query\
                .join(HostingService, cls.hosting_service)\
                .join(Workflow, Workflow.id == cls.workflow_id)\
                .filter(HostingService.uuid == lm_utils.uuid_param(hosting_service.uuid))\
                .filter(Workflow.uuid == lm_utils.uuid_param(uuid))\
                .filter(cls.version == version)\
                .order_by(WorkflowVersion.version.desc()).one()
        except NoResultFound as e:
            logger.debug(e)
            return None
        except Exception as e:
            raise lm_exceptions.LifeMonitorException(detail=str(e), stack=str(e))

    @classmethod
    def get_hosted_workflow_versions(cls, hosting_service: HostingService) -> List[WorkflowVersion]:
        return cls.query\
            .join(HostingService, cls.hosting_service)\
            .filter(HostingService.uuid == lm_utils.uuid_param(hosting_service.uuid))\
            .order_by(WorkflowVersion.version.desc()).all()
