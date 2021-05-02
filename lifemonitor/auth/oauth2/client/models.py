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
import time
from datetime import datetime
from importlib import import_module
from typing import List
from urllib.parse import urljoin

import requests
from authlib.integrations.flask_client import FlaskRemoteApp, OAuth
from authlib.integrations.requests_client import OAuth2Session
from authlib.oauth2.rfc6749 import OAuth2Token as OAuth2TokenBase
from flask import current_app
from flask_login import current_user
from lifemonitor.auth import models
from lifemonitor.db import db
from lifemonitor.exceptions import (EntityNotFoundException,
                                    LifeMonitorException,
                                    NotAuthorizedException)
from lifemonitor.models import JSON, ModelMixin
from sqlalchemy import DateTime
from sqlalchemy import inspect
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm.collections import attribute_mapped_collection
from sqlalchemy.orm.exc import NoResultFound

logger = logging.getLogger(__name__)


class OAuthIdentityNotFoundException(EntityNotFoundException):
    def __init__(self, entity_id=None) -> None:
        super().__init__(entity_class=self.__class__)
        self.entity_id = entity_id


class OAuth2Token(OAuth2TokenBase):

    def __init__(self, params):
        if params.get('expires_at'):
            params['expires_at'] = int(params['expires_at'])
        elif params.get('expires_in') and params.get('created_at'):
            params['expires_at'] = int(params['created_at']) + \
                int(params['expires_in'])
        super().__init__(params)

    def is_expired(self):
        expires_at = self.get('expires_at')
        if not expires_at:
            return None
        return expires_at < time.time()

    @property
    def threashold(self):
        try:
            return int(current_app.config['OAUTH2_REFRESH_TOKEN_BEFORE_EXPIRATION'])
        except Exception as e:
            logger.debug("Unable to get a configured OAUTH2_REFRESH_TOKEN_BEFORE_EXPIRATION property: %r", e)
            return 0

    def to_be_refreshed(self):
        # the token should be refreshed
        # if it is expired or close to expire (i.e., n secs before expiration)
        expires_at = self.get('expires_at')
        if not expires_at:
            return None
        return (expires_at - self.threashold) < time.time()


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
    _token = db.Column("token", JSON, nullable=True)
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
        return f"{self.provider.token_type} {self.fetch_token()['access_token']}"

    @property
    def username(self):
        return f"{self.provider.name}_{self.provider_user_id}"

    @property
    def token(self) -> OAuth2Token:
        return OAuth2Token(self._token)

    @token.setter
    def token(self, token: dict):
        self._token = token

    def fetch_token(self):
        # enable dynamic refresh only if the identity
        # has been already stored in the database
        if inspect(self).persistent:
            # fetch up to date identity data
            self.refresh()
            # reference to the token associated with the identity instance
            token = self.token
            # the token should be refreshed
            # if it is expired or close to expire (i.e., n secs before expiration)
            if token.to_be_refreshed():
                if 'refresh_token' not in token:
                    logger.debug("The token should be refreshed but no refresh token is associated with the token")
                else:
                    logger.debug("Trying to refresh the token...")
                    oauth2session = OAuth2Session(
                        self.provider.client_id, self.provider.client_secret, token=self.token)
                    new_token = oauth2session.refresh_token(
                        self.provider.access_token_url, refresh_token=token['refresh_token'])
                    self.token = new_token
                    self.save()
                    logger.debug("User token updated")
                    logger.debug("Using token %r", self.token)
        return self.token

    @property
    def user_info(self):
        if not self._user_info:
            logger.debug("[Identity %r], Trying to read profile of user %r from provider %r...", self. id, self.user_id, self.provider.name)
            self._user_info = self.provider.get_user_info(
                self.provider_user_id, self.fetch_token())
        return self._user_info

    @user_info.setter
    def user_info(self, value):
        self._user_info = value

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


class OAuth2Registry(OAuth):

    __instance = None

    @classmethod
    def get_instance(cls) -> OAuth2Registry:
        if not cls.__instance:
            cls.__instance = cls()
        return cls.__instance

    def __init__(self, app=None, cache=None):
        if self.__instance:
            raise RuntimeError("OAuth2Registry instance already exists!")
        super().__init__(app=app, cache=cache,
                         fetch_token=self.fetch_token, update_token=self.update_token)

    def get_client(self, name):
        try:
            return self._clients[name]
        except ValueError:
            raise LifeMonitorException(f"Unable to load the '{name}' OAuth2 client")

    def register_client(self, client_config):
        class OAuth2Client(FlaskRemoteApp):
            NAME = client_config.name
            OAUTH_APP_CONFIG = client_config.oauth_config

        super().register(client_config.name, overwrite=True, client_cls=OAuth2Client)

    @staticmethod
    def fetch_token(name, user=None):
        user = user or current_user
        logger.debug("NAME: %s", name)
        logger.debug("CURRENT APP: %r", current_app.config)
        api_key = current_app.config.get("{}_API_KEY".format(name.upper()), None)
        if api_key:
            logger.debug("FOUND an API KEY for the OAuth Service '%s': %s", name, api_key)
            return {"access_token": api_key}
        identity = OAuthIdentity.find_by_user_id(user.id, name)
        logger.debug("The token: %r", identity.token)
        return OAuth2Token(identity.token)

    @staticmethod
    def update_token(name, token, refresh_token=None, access_token=None):
        if access_token:
            logger.debug("Fetching token by access_token...")
            identity = OAuthIdentity.query.filter(
                OAuthIdentity.token['access_token'] == access_token).one()
        elif refresh_token:
            logger.debug("Fetching token by refresh_token...")
            identity = OAuthIdentity.query.filter(
                OAuthIdentity.token['refresh_token'] == refresh_token).one()
        # update old token
        logger.debug("Updating the token to access the user's identity...")
        identity.token = token
        logger.debug("Save the user's identity...")
        identity.save()


class OAuth2IdentityProvider(db.Model, ModelMixin):

    id = db.Column(db.Integer, primary_key=True)
    _type = db.Column("type", db.String, nullable=False)
    name = db.Column(db.String, nullable=False, unique=True)
    client_id = db.Column(db.String, nullable=False)
    client_secret = db.Column(db.String, nullable=False)
    client_kwargs = db.Column(JSON, nullable=True)
    _authorize_url = db.Column("authorize_url", db.String, nullable=False)
    authorize_params = db.Column(JSON, nullable=True)
    _access_token_url = db.Column("access_token_url", db.String, nullable=False)
    access_token_params = db.Column(JSON, nullable=True)
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
        access_token = token['access_token'] if isinstance(token, dict) else token
        response = requests.get(urljoin(self.api_base_url, self.userinfo_endpoint),
                                headers={'Authorization': f'Bearer {access_token}'})
        if response.status_code in (401, 403):
            raise NotAuthorizedException(detail=f"Unable to get user info from provider {self.name}")
        if response.status_code != 200:
            raise LifeMonitorException(details=response.content)
        try:
            data = response.json()
        except Exception as e:
            raise LifeMonitorException(title="Unable to decode user data", details=str(e))
        return data if not normalized \
            else self.normalize_userinfo(OAuth2Registry.get_instance().get_client(self.name), data)

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
        errors = []
        for client_type in (self.name, self.type):
            logger.debug(f"Searching with {client_type}")
            try:
                m = f"lifemonitor.auth.oauth2.client.providers.{client_type}"
                mod = import_module(m)
                return getattr(mod, "normalize_userinfo")(client, data)
            except ModuleNotFoundError:
                errors.append(f"ModuleNotFoundError: Unable to load module {m}")
            except AttributeError:
                errors.append(f"Unable to create an instance of WorkflowRegistryClient from module {m}")

        raise LifeMonitorException(f"Unable to load utility to normalize user info from provider {self.name}")

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
