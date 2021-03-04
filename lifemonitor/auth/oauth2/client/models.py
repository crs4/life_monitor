from __future__ import annotations

import logging
from datetime import datetime
from importlib import import_module
from typing import List
from urllib.parse import urljoin

import requests
from lifemonitor.auth import models
from lifemonitor.db import db
from lifemonitor.exceptions import (EntityNotFoundException,
                                    LifeMonitorException)
from lifemonitor.models import ModelMixin
from sqlalchemy import DateTime
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm.collections import attribute_mapped_collection
from sqlalchemy.orm.exc import NoResultFound

logger = logging.getLogger(__name__)


class OAuthIdentityNotFoundException(EntityNotFoundException):
    def __init__(self, entity_id=None) -> None:
        super().__init__(entity_class=self.__class__)
        self.entity_id = entity_id


class OAuthUserProfile:

    def __init__(self, sub=None, name=None, email=None, mbox_sha1sum=None,
                 preferred_username=None, profile=None, picture=None, website=None) -> None:
        self.sub = sub
        self.name = name
        self.email = email
        self.mbox_sha1sum = mbox_sha1sum
        self.preferred_username = preferred_username
        self.profile = profile
        self.picture = picture
        self.website = website

    def to_dict(self):
        res = {}
        for k in ['sub', 'name', 'email', 'mbox_sha1sum', 'preferred_username', 'profile', 'picture', 'website']:
            res[k] = getattr(self, k)
        return res

    @staticmethod
    def from_dict(data: dict):
        profile = OAuthUserProfile()
        for k, v, in data.items():
            setattr(profile, k, v)
        return profile


class OAuthIdentity(models.ExternalServiceAccessAuthorization, ModelMixin):
    id = db.Column(db.Integer, db.ForeignKey('external_service_access_authorization.id'), primary_key=True)
    provider_user_id = db.Column(db.String(256), nullable=False)
    provider_id = db.Column(db.Integer, db.ForeignKey("oauth2_identity_provider.id"), nullable=False)
    created_at = db.Column(DateTime, default=datetime.utcnow, nullable=False)
    token = db.Column(JSONB, nullable=True)
    _user_info = None
    provider = db.relationship("OAuth2IdentityProvider", uselist=False, back_populates="identities")
    user = db.relationship(
        models.User,
        # This `backref` thing sets up an `oauth` property on the User model,
        # which is a dictionary of OAuth models associated with that user,
        # where the dictionary key is the OAuth provider name.
        backref=db.backref(
            "oauth_identity",
            collection_class=attribute_mapped_collection("provider.name"),
            cascade="all, delete-orphan",
        ),
    )

    __table_args__ = (db.UniqueConstraint("provider_id", "provider_user_id"),)
    __tablename__ = "oauth2_identity"
    __mapper_args__ = {
        'polymorphic_identity': 'oauth2_identity'
    }

    def __init__(self, provider, user_info, provider_user_id, token):
        super().__init__(self.user)
        self.provider = provider
        self.provider_user_id = provider_user_id
        self._user_info = user_info
        self.token = token
        self.resources.append(provider.api_resource)

    def as_http_header(self):
        return f"{self.provider.token_type} {self.token['access_token']}"

    @property
    def username(self):
        return f"{self.provider.name}_{self.provider_user_id}"

    @property
    def user_info(self):
        if not self._user_info:
            self._user_info = self.provider.get_user_info(self.provider_user_id, self.token)
        return self._user_info

    @user_info.setter
    def user_info(self, value):
        self._user_info = value

    def set_token(self, token):
        self.token = token

    def __repr__(self):
        parts = []
        parts.append(self.__class__.__name__)
        if self.id:
            parts.append("id={}".format(self.id))
        if self.provider:
            parts.append('provider="{}"'.format(self.provider))
        return "<{}>".format(" ".join(parts))

    @staticmethod
    def find_by_user_id(user_id, provider_name) -> OAuthIdentity:
        try:
            return OAuthIdentity.query\
                .filter(OAuthIdentity.provider.has(name=provider_name))\
                .filter_by(user_id=user_id).one()
        except NoResultFound:
            raise OAuthIdentityNotFoundException(f"{user_id}_{provider_name}")

    @staticmethod
    def find_by_provider_user_id(provider_user_id, provider_name) -> OAuthIdentity:
        try:
            return OAuthIdentity.query\
                .filter(OAuthIdentity.provider.has(name=provider_name))\
                .filter_by(provider_user_id=provider_user_id).one()
        except NoResultFound:
            raise OAuthIdentityNotFoundException(f"{provider_name}_{provider_user_id}")

    @classmethod
    def all(cls) -> List[OAuthIdentity]:
        return cls.query.all()


class OAuth2IdentityProvider(db.Model, ModelMixin):

    id = db.Column(db.Integer, primary_key=True)
    _type = db.Column("type", db.String, nullable=False)
    name = db.Column(db.String, nullable=False, unique=True)
    client_id = db.Column(db.String, nullable=False)
    client_secret = db.Column(db.String, nullable=False)
    client_kwargs = db.Column(JSONB, nullable=True)
    _authorize_url = db.Column("authorize_url", db.String, nullable=False)
    authorize_params = db.Column(JSONB, nullable=True)
    _access_token_url = db.Column("access_token_url", db.String, nullable=False)
    access_token_params = db.Column(JSONB, nullable=True)
    userinfo_endpoint = db.Column(db.String, nullable=False)
    api_resource_id = db.Column(db.Integer, db.ForeignKey("resource.id"), nullable=False)
    api_resource = db.relationship("Resource", cascade="all, delete")
    identities = db.relationship("OAuthIdentity",
                                 back_populates="provider", cascade="all, delete")

    __tablename__ = "oauth2_identity_provider"
    __mapper_args__ = {
        'polymorphic_on': _type,
        'polymorphic_identity': 'oauth2_identity_provider'
    }

    def __init__(self, name,
                 client_id, client_secret,
                 api_base_url, authorize_url, access_token_url, userinfo_endpoint,
                 client_kwargs=None,
                 authorize_params=None,
                 access_token_params=None,
                 **kwargs):
        self.name = name
        self.client_id = client_id
        self.client_secret = client_secret
        self.api_resource = models.Resource(api_base_url, name=self.name)
        self.client_kwargs = client_kwargs
        self.authorize_url = authorize_url
        self.access_token_url = access_token_url
        self.access_token_params = access_token_params
        self.userinfo_endpoint = urljoin(api_base_url, userinfo_endpoint)

    @property
    def type(self):
        return self._type

    @property
    def token_type(self):
        return "Bearer"

    def get_user_info(self, provider_user_id, token, normalized=True):
        data = requests.get(urljoin(self.api_base_url, self.userinfo_endpoint),
                            headers={'Authorization': f'Bearer {token}'})
        return data if not normalized else self.normalize_userinfo(None, data)

    @property
    def api_base_url(self):
        return self.api_resource.uri

    @api_base_url.setter
    def api_base_url(self, api_base_url):
        assert api_base_url and len(api_base_url) > 0, "URL cannot be empty"
        self.uri = api_base_url
        self.api_resource.uri = api_base_url

    @hybrid_property
    def authorize_url(self):
        return self._authorize_url

    @authorize_url.setter
    def authorize_url(self, authorize_url):
        assert authorize_url and len(authorize_url) > 0, "URL cannot be empty"
        self._authorize_url = urljoin(self.api_base_url, authorize_url)

    @hybrid_property
    def access_token_url(self):
        return self._access_token_url

    @access_token_url.setter
    def access_token_url(self, token_url):
        assert token_url and len(token_url) > 0, "URL cannot be empty"
        self._access_token_url = urljoin(self.api_base_url, token_url)

    @property
    def oauth_config(self):
        return {
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'client_kwargs': self.client_kwargs,
            'api_base_url': self.api_base_url,
            'authorize_url': self.authorize_url,
            'authorize_params': self.authorize_params,
            'access_token_url': self.access_token_url,
            'access_token_params': self.access_token_params,
            'userinfo_endpoint': self.userinfo_endpoint,
            'userinfo_compliance_fix': self.normalize_userinfo,
        }

    def normalize_userinfo(self, client, data):
        m = f"lifemonitor.auth.oauth2.client.providers.{self.type}"
        try:
            mod = import_module(m)
            return getattr(mod, "normalize_userinfo")(client, data)
        except ModuleNotFoundError:
            raise LifeMonitorException(f"ModuleNotFoundError: Unable to load module {m}")
        except AttributeError:
            raise LifeMonitorException(f"Unable to create an instance of WorkflowRegistryClient from module {m}")

    def find_identity_by_provider_user_id(self, provider_user_id):
        try:
            return OAuthIdentity.query.with_parent(self)\
                .filter_by(provider_user_id=provider_user_id).one()
        except NoResultFound:
            raise OAuthIdentityNotFoundException(f"{provider_user_id}@{self}")

    @classmethod
    def find(cls, name) -> OAuth2IdentityProvider:
        try:
            return cls.query.filter(cls.name == name).one()
        except NoResultFound:
            raise EntityNotFoundException(cls, entity_id=name)

    @classmethod
    def all(cls) -> List[OAuth2IdentityProvider]:
        return cls.query.all()
