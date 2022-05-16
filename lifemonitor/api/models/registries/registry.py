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
from abc import ABC, abstractmethod
from typing import List, Tuple, Union

import lifemonitor.api.models as models
import lifemonitor.exceptions as lm_exceptions
import requests
from authlib.integrations.base_client import RemoteApp
from lifemonitor import utils as lm_utils
from lifemonitor.api.models import db
from lifemonitor.api.models.repositories.base import WorkflowRepository
from lifemonitor.auth import models as auth_models
from lifemonitor.auth.models import Resource
from lifemonitor.auth.oauth2.client.models import OAuthIdentity
from lifemonitor.auth.oauth2.client.services import oauth2_registry
from lifemonitor.utils import ClassManager, download_url
from sqlalchemy.orm.collections import attribute_mapped_collection
from sqlalchemy.orm.exc import NoResultFound

# set module level logger
logger = logging.getLogger(__name__)


class RegistryWorkflow(object):
    _registry: WorkflowRegistry
    _uuid: str
    _identifier: str
    _name: str
    _latest_version: str
    _versions: List[str] = None
    _metadata: dict = None

    def __init__(self,
                 registry: WorkflowRegistry,
                 uuid: str,
                 identifier: str,
                 name: str,
                 latest_version: str = None,
                 versions: List[str] = None,
                 metadata: dict = None) -> None:
        self._registry = registry
        self._uuid = uuid
        self._identifier = identifier
        self._name = name
        self._latest_version = latest_version
        if versions:
            self._versions = versions.copy()
        self._metadata = metadata

    def __repr__(self) -> str:
        return f"RegistryWorkflow: {self.name} (id: {self.identifier}, uuid: {self.uuid})"

    @property
    def registry(self) -> WorkflowRegistry:
        return self._registry

    @property
    def uuid(self) -> str:
        return self._uuid

    @property
    def identifier(self) -> str:
        return self._identifier

    @property
    def name(self) -> str:
        return self._name

    @property
    def latest_version(self) -> str:
        return self._latest_version

    @property
    def versions(self) -> List[str]:
        return self._versions.copy()

    @property
    def external_link(self) -> str:
        return self._registry.get_external_link(self._identifier, self._latest_version)

    @property
    def metadata(self):
        return self._metadata


class RegistryWorkflowVersion(Resource):

    id = db.Column(db.Integer, db.ForeignKey(Resource.id), primary_key=True)
    workflow_version_id = db.Column(db.Integer, db.ForeignKey("workflow_version.id"), nullable=True)
    workflow_version: models.WorkflowVersion = db.relationship("WorkflowVersion", uselist=False,
                                                               backref=db.backref("registry_workflow_versions", cascade="all, delete-orphan",
                                                                                  collection_class=attribute_mapped_collection('registry.name')),
                                                               foreign_keys=[workflow_version_id])

    registry_id = db.Column(db.Integer, db.ForeignKey("workflow_registry.id"), nullable=True)
    registry: WorkflowRegistry = db.relationship("WorkflowRegistry", uselist=False,
                                                 backref=db.backref("workflow_versions",
                                                                    cascade="all, delete-orphan"),
                                                 foreign_keys=[registry_id])
    external_ns = "external-id:"
    _registry_workflow = None

    __mapper_args__ = {
        'polymorphic_identity': 'registry_workflow_version'
    }

    def __init__(self, registry: WorkflowRegistry, workflow_version: models.WorkflowVersion, identifier: str, version: str = None,
                 registry_workflow: RegistryWorkflow = None) -> None:
        super().__init__(self.external_ns, version=version or workflow_version.version)
        self.registry = registry
        self.identifier = identifier
        self.workflow_version = workflow_version
        self._registry_workflow = registry_workflow
        self.uuid = self.registry_workflow.uuid

    @property
    def identifier(self):
        r = self.uri.replace(self.external_ns, "")
        return r if len(r) > 0 else None

    @identifier.setter
    def identifier(self, value):
        self.uri = f"{self.external_ns}{value}"

    @property
    def registry_workflow(self) -> RegistryWorkflow:
        if not self._registry_workflow:
            self._registry_workflow = self.registry.get_index_workflow(self.workflow_version.submitter, self.identifier)
        return self._registry_workflow

    @property
    def link(self) -> str:
        return self.registry.get_external_link(self.identifier, self.version)


class WorkflowRegistryClient(ABC):

    client_types = ClassManager('lifemonitor.api.models.registries',
                                skip=["registry", "forms", "settings"],
                                class_suffix="WorkflowRegistryClient")

    def __init__(self, registry: WorkflowRegistry):
        self._registry = registry
        try:
            self._oauth2client: RemoteApp = getattr(oauth2_registry, self.registry.client_name)
        except AttributeError:
            raise RuntimeError(f"Unable to find a OAuth2 client for the {self.registry.name} service")

    @property
    def registry(self):
        return self._registry

    def _get_access_token(self, user_id):
        # get the access token related with the user of this client registry
        return OAuthIdentity.find_by_user_id(user_id, self.registry.name).token

    def _get(self, user, *args, **kwargs):
        return self._requester(user, 'get', *args, **kwargs)

    def _patch(self, user, *args, **kwargs):
        return self._requester(user, 'patch', *args, **kwargs)

    def _post(self, user, *args, **kwargs):
        return self._requester(user, 'post', *args, **kwargs)

    def _put(self, user, *args, **kwargs):
        return self._requester(user, 'put', *args, **kwargs)

    def _delete(self, user, *args, **kwargs):
        return self._requester(user, 'delete', *args, **kwargs)

    def _requester(self, user, method: str, *args, **kwargs):
        errors = []
        authorizations = []
        if user:
            authorizations.extend([
                auth.as_http_header() for auth in self.registry.get_authorization(user)])
        authorizations.append(None)
        response = None
        for auth in authorizations:
            # cache = requests_cache.CachedSession(f'lifemonitor_registry_cache_{auth}')
            # with cache as session:
            with requests.Session() as session:
                session.headers['Authorization'] = auth
                if not kwargs.get('files', None):
                    session.headers.update({
                        "Content-type": "application/vnd.api+json",
                        "Accept": "application/vnd.api+json",
                        "Accept-Charset": "ISO-8859-1",
                    })
                logger.debug("Header: %r", session.headers)
                logger.debug("Args: %r, KwArgs: %r", args, kwargs)
                try:
                    response = getattr(session, method)(*args, **kwargs)
                    logger.debug("Response: %r", response.content)
                    response.raise_for_status()
                    return response
                except requests.HTTPError as e:
                    if logger.isEnabledFor(logging.DEBUG):
                        logger.exception(e)
                    errors.append(str(e))
        if response.status_code == 401 or response.status_code == 403:
            raise lm_exceptions.NotAuthorizedException(details=response.content)
        raise lm_exceptions.LifeMonitorException(errors=[str(e) for e in errors])

    def get_index(self, user: auth_models.User) -> List[RegistryWorkflow]:
        pass

    def get_index_workflow(self, user: auth_models.User, workflow_identifier: str) -> RegistryWorkflow:
        pass

    def download_url(self, url, user, target_path=None):
        return download_url(url, target_path,
                            authorization=f'Bearer {self._get_access_token(user.id)["access_token"]}')

    def get_external_id(self, uuid, version, user: auth_models.User) -> str:
        """ Return CSV of uuid and version"""
        return ",".join([str(uuid), str(version)])

    def get_external_uuid(self, identifier, version, user: auth_models.User) -> str:
        """ Return CSV of identifier and version"""
        return ",".join([str(identifier), str(version)])

    @abstractmethod
    def get_user_info(self, user) -> object:
        pass

    @abstractmethod
    def get_external_link(self, external_id: str, version: str) -> str:
        pass

    @abstractmethod
    def get_rocrate_external_link(self, external_id: str, version: str) -> str:
        pass

    @abstractmethod
    def get_workflows_metadata(self, user, details=False):
        pass

    @abstractmethod
    def get_workflow_metadata(self, user, w: Union[models.WorkflowVersion, str]):
        pass

    @abstractmethod
    def filter_by_user(workflows: list, user: auth_models.User):
        pass

    @abstractmethod
    def find_workflow_versions_by_remote_url(self, user, url: str) -> List[object]:
        pass

    @abstractmethod
    def register_workflow(self, user, crate_path, external_id: str = None, *args, **kwargs):
        pass

    @abstractmethod
    def delete_workflow(self, user, external_id: str):
        pass

    @classmethod
    def get_client_class(cls, client_type):
        return cls.client_types.get_class(client_type)


class WorkflowRegistry(auth_models.HostingService):

    id = db.Column(db.Integer, db.ForeignKey(auth_models.HostingService.id), primary_key=True)
    registry_type = db.Column(db.String, nullable=False)

    registry_types = ClassManager('lifemonitor.api.models.registries',
                                  skip=["registry", "forms", "settings"],
                                  class_suffix="WorkflowRegistry")

    __mapper_args__ = {
        'polymorphic_identity': 'workflow_registry'
    }

    def __init__(self, registry_type, client_credentials, server_credentials, name: str = None):
        super().__init__(server_credentials.api_base_url, name=name or server_credentials.name)
        self.registry_type = registry_type
        self.client_credentials = client_credentials
        self.server_credentials = server_credentials
        self._client = None

    def __repr__(self):
        return '<WorkflowRegistry ({}) -- name {}, client_name: {}, url {}>'.format(
            self.uuid, self.name, self.client_name, self.uri)

    @property
    def api(self) -> auth_models.Resource:
        return self.server_credentials.api_resource

    @property
    def read_write_scopes(self) -> Tuple[str]:
        return None

    def get_external_uuid(self, external_id, version, user: auth_models.User) -> str:
        return self.client.get_external_uuid(external_id, version, user)

    def get_external_id(self, uuid, version, user: auth_models.User) -> str:
        return self.client.get_external_id(uuid, version, user)

    def get_external_link(self, external_id: str, version: str) -> str:
        return self.client.get_external_link(external_id, version)

    def get_rocrate_external_link(self, external_id: str, version: str) -> str:
        return self.client.get_rocrate_external_link(external_id, version)

    def download_url(self, url, user, target_path=None):
        return self.client.download_url(url, user, target_path=target_path)

    def get_registry_user_id(self, user) -> str:
        try:
            return user.oauth_identity[self.name].provider_user_id
        except Exception as e:
            logger.warning("Unable to find an identity for user %r on registry %r", user, self)
            logger.debug(str(e))
            return None

    def get_registry_user_info(self, user) -> object:
        return self.client.get_user_info(user)

    @property
    def users(self) -> List[auth_models.User]:
        return self.get_users()

    def get_authorization(self, user: auth_models.User):
        auths = auth_models.ExternalServiceAccessAuthorization.find_by_user_and_resource(user, self)
        # add user authorization related with the registry as Identity provider
        identity = user.oauth_identity.get(self.server_credentials.client_name, None)
        if identity:
            token = identity.fetch_token()
            auths.append(auth_models.ExternalServiceAuthorizationHeader(user, f"{token['token_type']} {identity.token['access_token']}"))
        else:
            logger.warning(f"No '{self.server_credentials.name}' identity for the user {user}")
        return auths

    def get_user(self, user_id) -> auth_models.User:
        for u in self.users:
            logger.debug(f"Checking {u.id} {user_id}")
            if u.id == user_id:
                return u
        return None

    def get_users(self) -> List[auth_models.User]:
        try:
            return [i.user for i in OAuthIdentity.query
                    .filter(OAuthIdentity.provider == self.server_credentials).all()]
        except Exception as e:
            raise lm_exceptions.EntityNotFoundException(e)

    def add_workflow_version(self, workflow_version: models.WorkflowVersion, identifier: str, version: str,
                             registry_workflow: RegistryWorkflow = None) -> RegistryWorkflowVersion:
        return RegistryWorkflowVersion(self, workflow_version, identifier=identifier, version=version, registry_workflow=registry_workflow)

    def remove_workflow_version(self, workflow_version: models.WorkflowVersion):
        assert isinstance(workflow_version, models.WorkflowVersion), workflow_version
        registry_workflow = workflow_version.registries.get(self.name, None)
        if registry_workflow:
            self.workflow_versions.remove(registry_workflow)

    def get_workflows(self) -> List[models.Workflow]:
        return list({w.workflow_version.workflow for w in self.workflow_versions})

    def get_workflow_by_external_id(self, identifier) -> models.Workflow:
        try:
            w = next((w for w in self.workflow_versions if w.identifier == identifier), None)
            return w.workflow if w is not None else None
        except Exception:
            if models.Workflow.find_by_uuid(identifier) is not None:
                raise lm_exceptions.NotAuthorizedException()

    def get_workflow(self, uuid_or_identifier) -> models.Workflow:
        try:
            w = next((w for w in self.workflow_versions if w.workflow_version.workflow.uuid == lm_utils.uuid_param(uuid_or_identifier)), None)
            if not w:
                w = next((w for w in self.workflow_versions if w.identifier == uuid_or_identifier), None)
            return w.workflow_version.workflow if w is not None else None
        except Exception:
            if models.Workflow.find_by_uuid(uuid_or_identifier) is not None:
                raise lm_exceptions.NotAuthorizedException()

    def get_user_workflows(self, user: auth_models.User) -> List[models.Workflow]:
        return self.client.filter_by_user(self.get_workflows(), user)

    def get_user_workflow_versions(self, user: auth_models.User) -> List[models.WorkflowVersion]:
        return self.client.filter_by_user(self.workflow_versions, user)

    def get_index(self, user: auth_models.User) -> List[RegistryWorkflow]:
        return self.client.get_index(user)

    def get_index_workflow(self, user: auth_models.User, workflow_identifier: str) -> RegistryWorkflow:
        return self.client.get_index_workflow(user, workflow_identifier)

    def find_workflow_versions_by_remote_url(self, user, url: str, user_as_submitter: bool = True) -> List[object]:
        return self.client.find_workflow_versions_by_remote_url(user, url)

    def register_workflow_version(self, submitter: auth_models.User,
                                  repository: WorkflowRepository, external_id: str = None):
        pass

    def delete_workflow(self, submitter: auth_models.User, external_id: str) -> bool:
        pass

    @property
    def client(self) -> WorkflowRegistryClient:
        if self._client is None:
            rtype = self.__class__.__name__.replace("WorkflowRegistry", "").lower()
            return WorkflowRegistryClient.get_client_class(rtype)(self)
        return self._client

    @classmethod
    def all(cls) -> List[WorkflowRegistry]:
        return cls.query.all()

    @classmethod
    def find_by_uuid(cls, uuid) -> WorkflowRegistry:
        try:
            return cls.query.filter(WorkflowRegistry.uuid == lm_utils.uuid_param(uuid)).one()
        except NoResultFound as e:
            logger.debug(e)
            return None
        except Exception as e:
            raise lm_exceptions.LifeMonitorException(detail=str(e), stack=str(e))

    @classmethod
    def find_by_client_name(cls, name) -> WorkflowRegistry:
        return cls.find_by_provider_client_name(name)

    @classmethod
    def find_by_name(cls, name) -> List[WorkflowRegistry]:
        try:
            return cls.query.filter(WorkflowRegistry.name == name).all()
        except Exception as e:
            raise lm_exceptions.EntityNotFoundException(WorkflowRegistry, entity_id=name, exception=e)

    @classmethod
    def find_by_uri(cls, uri) -> WorkflowRegistry:
        try:
            return cls.query.filter(WorkflowRegistry.uri == uri).one()
        except Exception as e:
            raise lm_exceptions.EntityNotFoundException(WorkflowRegistry, entity_id=uri, exception=e)

    @classmethod
    def get_registry_class(cls, registry_type):
        return cls.registry_types.get_class(registry_type)

    @classmethod
    def new_instance(cls, registry_type, client_credentials, server_credentials, name: str = None):
        return cls.get_registry_class(registry_type)(client_credentials,
                                                     server_credentials, name=name)
