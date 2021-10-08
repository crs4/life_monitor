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
from typing import List, Union

import lifemonitor.api.models as models
import lifemonitor.exceptions as lm_exceptions
import requests
from authlib.integrations.base_client import RemoteApp
from lifemonitor import utils as lm_utils
from lifemonitor.api.models import db
from lifemonitor.auth import models as auth_models
from lifemonitor.auth.oauth2.client.models import OAuthIdentity
from lifemonitor.auth.oauth2.client.services import oauth2_registry
from lifemonitor.utils import ClassManager, download_url
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy.orm.exc import NoResultFound

# set module level logger
logger = logging.getLogger(__name__)


class WorkflowRegistryClient(ABC):

    client_types = ClassManager('lifemonitor.api.models.registries', class_suffix="WorkflowRegistryClient", skip=["registry"])

    def __init__(self, registry: WorkflowRegistry):
        self._registry = registry
        try:
            self._oauth2client: RemoteApp = getattr(oauth2_registry, self.registry.name)
        except AttributeError:
            raise RuntimeError(f"Unable to find a OAuth2 client for the {self.registry.name} service")

    @property
    def registry(self):
        return self._registry

    def _get_access_token(self, user_id):
        # get the access token related with the user of this client registry
        return OAuthIdentity.find_by_user_id(user_id, self.registry.name).token

    def _get(self, user, *args, **kwargs):
        authorizations = []
        if user:
            authorizations.extend([
                auth.as_http_header() for auth in user.get_authorization(self.registry)])
        authorizations.append(None)
        response = None
        for auth in authorizations:
            with requests.Session() as session:
                session.headers['Authorization'] = auth
                response = session.get(*args, **kwargs)
                if response.status_code == 200:
                    break
        if response.status_code == 401 or response.status_code == 403:
            raise lm_exceptions.NotAuthorizedException(details=response.content)
        response.raise_for_status()
        return response

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

    @classmethod
    def get_client_class(cls, client_type):
        return cls.client_types.get_class(client_type)


class WorkflowRegistry(auth_models.HostingService):

    id = db.Column(db.Integer, db.ForeignKey(auth_models.HostingService.id), primary_key=True)
    registry_type = db.Column(db.String, nullable=False)
    _client_id = db.Column(db.Integer, db.ForeignKey('oauth2_client.id', ondelete='CASCADE'))
    _server_id = db.Column(db.Integer, db.ForeignKey('oauth2_identity_provider.id', ondelete='CASCADE'))
    client_credentials = db.relationship("Client", uselist=False, cascade="all, delete")
    server_credentials = db.relationship("OAuth2IdentityProvider",
                                         uselist=False, cascade="all, delete",
                                         foreign_keys=[_server_id],
                                         backref="workflow_registry")
    client_id = association_proxy('client_credentials', 'client_id')

    _client = None

    registry_types = ClassManager('lifemonitor.api.models.registries', class_suffix="WorkflowRegistry", skip=["registry"])

    __mapper_args__ = {
        'polymorphic_identity': 'workflow_registry'
    }

    def __init__(self, registry_type, client_credentials, server_credentials):
        super().__init__(server_credentials.api_base_url, name=server_credentials.name)
        self.registry_type = registry_type
        self.client_credentials = client_credentials
        self.server_credentials = server_credentials
        self._client = None

    def __repr__(self):
        return '<WorkflowRegistry ({}) -- name {}, url {}>'.format(
            self.uuid, self.name, self.uri)

    @property
    def api(self) -> auth_models.Resource:
        return self.server_credentials.api_resource

    def set_name(self, name):
        self.name = name
        self.server_credentials.name = name

    def set_uri(self, uri):
        self.uri = uri
        self.server_credentials.api_resource.uri = uri
        self.client_credentials.api_base_url = uri

    def update_client(self, client_id=None, client_secret=None,
                      redirect_uris=None, client_auth_method=None):
        if client_id:
            self.server_credentials.client_id = client_id
        if client_secret:
            self.server_credentials.client_secret = client_secret
        if redirect_uris:
            self.client_credentials.redirect_uris = redirect_uris
        if client_auth_method:
            self.client_credentials.auth_method = client_auth_method

    @property
    def client(self) -> WorkflowRegistryClient:
        if self._client is None:
            rtype = self.__class__.__name__.replace("WorkflowRegistry", "").lower()
            return WorkflowRegistryClient.get_client_class(rtype)(self)
        return self._client

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

    @property
    def users(self) -> List[auth_models.User]:
        return self.get_users()

    @property
    def registered_workflow_versions(self) -> List[models.WorkflowVersion]:
        return self.ro_crates

    def get_authorization(self, user: auth_models.User):
        auths = auth_models.ExternalServiceAccessAuthorization.find_by_user_and_resource(user, self)
        # check for sub-resource authorizations
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

    def get_workflows(self) -> List[models.Workflow]:
        return list({w.workflow for w in self.registered_workflow_versions})

    def get_workflow(self, uuid_or_identifier) -> models.Workflow:
        try:
            w = next((w for w in self.registered_workflow_versions if w.workflow.uuid == lm_utils.uuid_param(uuid_or_identifier)), None)
            return w.workflow if w is not None else None
        except ValueError:
            w = next((w for w in self.registered_workflow_versions if w.workflow.external_id == uuid_or_identifier), None)
            return w.workflow if w is not None else None
        except Exception:
            if models.Workflow.find_by_uuid(uuid_or_identifier) is not None:
                raise lm_exceptions.NotAuthorizedException()

    def get_user_workflows(self, user: auth_models.User) -> List[models.Workflow]:
        return self.client.filter_by_user(self.get_workflows(), user)

    def get_user_workflow_versions(self, user: auth_models.User) -> List[models.WorkflowVersion]:
        return self.client.filter_by_user(self.registered_workflow_versions, user)

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
    def find_by_name(cls, name):
        try:
            return cls.query.filter(WorkflowRegistry.name == name).one()
        except Exception as e:
            raise lm_exceptions.EntityNotFoundException(WorkflowRegistry, entity_id=name, exception=e)

    @classmethod
    def find_by_uri(cls, uri):
        try:
            return cls.query.filter(WorkflowRegistry.uri == uri).one()
        except Exception as e:
            raise lm_exceptions.EntityNotFoundException(WorkflowRegistry, entity_id=uri, exception=e)

    @classmethod
    def find_by_client_id(cls, client_id):
        try:
            return cls.query.filter_by(client_id=client_id).one()
        except NoResultFound as e:
            logger.debug(e)
            return None
        except Exception as e:
            raise lm_exceptions.LifeMonitorException(detail=str(e), stack=str(e))

    @classmethod
    def get_registry_class(cls, registry_type):
        return cls.registry_types.get_class(registry_type)

    @classmethod
    def new_instance(cls, registry_type, client_credentials, server_credentials):
        return cls.get_registry_class(registry_type)(client_credentials,
                                                     server_credentials)
