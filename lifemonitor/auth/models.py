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
import abc

import datetime
import logging
import uuid as _uuid
from typing import List, Union

from authlib.integrations.sqla_oauth2 import OAuth2TokenMixin
from flask_bcrypt import check_password_hash, generate_password_hash
from flask_login import AnonymousUserMixin, UserMixin
from lifemonitor import utils as lm_utils
from lifemonitor.db import db
from lifemonitor.models import UUID, ModelMixin
from sqlalchemy.ext.hybrid import hybrid_property

# Set the module level logger
logger = logging.getLogger(__name__)


class Anonymous(AnonymousUserMixin):
    def __init__(self):
        self.username = 'Guest'

    @property
    def id(self):
        return None

    def get_user_id(self):
        return None


class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(256), unique=True, nullable=False)
    password_hash = db.Column(db.LargeBinary, nullable=True)
    picture = db.Column(db.String(), nullable=True)

    permissions = db.relationship("Permission", back_populates="user",
                                  cascade="all, delete-orphan")
    authorizations = db.relationship("ExternalServiceAccessAuthorization",
                                     cascade="all, delete-orphan")

    def __init__(self, username=None) -> None:
        super().__init__()
        self.username = username

    def get_user_id(self):
        return self.id

    def get_authorization(self, resource: Resource):
        auths = ExternalServiceAccessAuthorization.find_by_user_and_resource(self, resource)
        # check for sub-resource authorizations
        for subresource in ["api"]:
            if hasattr(resource, subresource):
                auths.extend(ExternalServiceAccessAuthorization
                             .find_by_user_and_resource(self, getattr(resource, subresource)))
        return auths

    @property
    def current_identity(self):
        from .services import current_registry, current_user
        if not current_user.is_anonymous:
            return self.oauth_identity
        if current_registry:
            for p, i in self.oauth_identity.items():
                if i.provider == current_registry.server_credentials:
                    return {p: i}
        return None

    @property
    def password(self):
        raise AttributeError("password is not a readable attribute")

    @password.setter
    def password(self, password):
        self.password_hash = generate_password_hash(password)

    @password.deleter
    def password(self):
        self.password_hash = None

    @property
    def has_password(self):
        return bool(self.password_hash)

    def has_permission(self, resource: Resource) -> bool:
        return self.get_permission(resource) is not None

    def get_permission(self, resource: Resource) -> Permission:
        return next((p for p in self.permissions if p.resource == resource), None)

    def verify_password(self, password):
        return check_password_hash(self.password_hash, password)

    def save(self):
        db.session.add(self)
        db.session.commit()

    def to_dict(self):
        return {
            "id": self.id,
            "username": self.username,
            "identities": {
                n: i.user_info for n, i in self.oauth_identity.items()
            }
        }

    @classmethod
    def find_by_username(cls, username):
        return cls.query.filter(cls.username == username).first()

    @classmethod
    def all(cls):
        return cls.query.all()


class ApiKey(db.Model, ModelMixin):
    SCOPES = ["read", "write"]

    key = db.Column(db.String, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey('user.id', ondelete='CASCADE')
    )
    user = db.relationship(
        'User',
        backref=db.backref("api_keys", cascade="all, delete-orphan"),
    )
    scope = db.Column(db.String, nullable=False)

    def __init__(self, key=None, user=None, scope=None) -> None:
        super().__init__()
        self.key = key
        self.user = user
        self.scope = scope or ""

    def __repr__(self) -> str:
        return "ApiKey {} (scope: {})".format(self.key, self.scope)

    def set_scope(self, scope):
        if scope:
            for s in scope.split(" "):
                if s not in self.SCOPES:
                    raise ValueError("Scope '{}' not valid".format(s))
                self.scope = "{} {}".format(self.scope, s)

    def check_scopes(self, scopes: list or str):
        if isinstance(scopes, str):
            scopes = scopes.split(" ")
        supported_scopes = self.scope.split(" ")
        for scope in scopes:
            if scope not in supported_scopes:
                return False
        return True

    @classmethod
    def find(cls, api_key) -> ApiKey:
        return cls.query.filter(ApiKey.key == api_key).first()

    @classmethod
    def all(cls) -> List[ApiKey]:
        return cls.query.all()


class Resource(db.Model, ModelMixin):

    id = db.Column('id', db.Integer, primary_key=True)
    uuid = db.Column(UUID, default=_uuid.uuid4)
    type = db.Column(db.String, nullable=False)
    name = db.Column(db.String, nullable=True)
    uri = db.Column(db.String, nullable=False)
    version = db.Column(db.String, nullable=True)
    created = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    modified = db.Column(db.DateTime, default=datetime.datetime.utcnow,
                         onupdate=datetime.datetime.utcnow)

    permissions = db.relationship("Permission", back_populates="resource",
                                  cascade="all, delete-orphan")

    __mapper_args__ = {
        'polymorphic_identity': 'resource',
        'polymorphic_on': type,
    }

    def __init__(self, uri, uuid=None,
                 name=None, version=None) -> None:
        assert uri, "URI cannot be empty"
        self.uri = uri.strip('/')
        self.name = name
        self.version = version
        self.uuid = uuid

    def __repr__(self):
        return '<Resource {}: {} -> {} (type={}))>'.format(
            self.id, self.uuid, self.uri, self.type)

    @hybrid_property
    def authorizations(self):
        return self._authorizations

    def get_authorization(self, user: User):
        auths = ExternalServiceAccessAuthorization.find_by_user_and_resource(user, self)
        # check for sub-resource authorizations
        for subresource in ["api"]:
            if hasattr(self, subresource):
                auths.extend(ExternalServiceAccessAuthorization
                             .find_by_user_and_resource(self, getattr(self, subresource)))
        return auths

    @classmethod
    def find_by_uuid(cls, uuid):
        return cls.query.filter(cls.uuid == lm_utils.uuid_param(uuid)).first()


resource_authorization_table = db.Table(
    'resource_authorization', db.Model.metadata,
    db.Column('resource_id', db.Integer,
              db.ForeignKey("resource.id", ondelete="CASCADE")),
    db.Column('authorization_id', db.Integer,
              db.ForeignKey("external_service_access_authorization.id", ondelete="CASCADE"))
)


class HostingService(Resource):

    id = db.Column(db.Integer, db.ForeignKey(Resource.id), primary_key=True)

    __mapper_args__ = {
        'polymorphic_identity': 'hosting_service'
    }

    @abc.abstractmethod
    def get_external_id(self, uuid: str, version: str, user: User) -> str:
        pass

    @abc.abstractmethod
    def get_external_link(self, external_id: str, version: str) -> str:
        pass

    @abc.abstractmethod
    def get_rocrate_external_link(self, user, w: Union[object, str]) -> str:
        pass


class RoleType:
    owner = "owner"
    viewer = "viewer"


class Permission(db.Model):
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), primary_key=True)
    resource_id = db.Column(db.Integer, db.ForeignKey('resource.id', ondelete='CASCADE'), primary_key=True)
    roles = db.Column(db.ARRAY(db.String), nullable=True)
    user = db.relationship("User", back_populates="permissions")
    resource = db.relationship("Resource", back_populates="permissions")

    def __repr__(self):
        return '<Permission of user {} for resource {}: {}>'.format(
            self.user, self.resource, self.roles)

    def __init__(self, user: User = None, resource: Resource = None, roles=None) -> None:
        self.user = user
        self.resource = resource
        self.roles = []
        if roles:
            for r in roles:
                self.roles.append(r)


class ExternalServiceAccessAuthorization(db.Model):

    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String, nullable=False)
    user_id = db.Column(db.Integer,
                        db.ForeignKey(User.id, ondelete='CASCADE'), nullable=True)

    resources = db.relationship("Resource",
                                secondary=resource_authorization_table,
                                backref="_authorizations",
                                passive_deletes=True)

    user = db.relationship("User", back_populates="authorizations", cascade="all, delete")

    __mapper_args__ = {
        'polymorphic_identity': 'authorization',
        'polymorphic_on': type,
    }

    def __init__(self, user) -> None:
        super().__init__()
        self.user = user

    def as_http_header(self):
        return ""

    @staticmethod
    def find_by_user_and_resource(user: User, resource: Resource):
        return [a for a in user.authorizations if resource in a.resources]


class ExternalServiceAuthorizationHeader(ExternalServiceAccessAuthorization):

    id = db.Column(db.Integer, db.ForeignKey('external_service_access_authorization.id'), primary_key=True)

    __mapper_args__ = {
        'polymorphic_identity': 'authorization_header'
    }

    header = db.Column(db.String, nullable=False)

    def __init__(self, user, header) -> None:
        super().__init__(user)
        self.header = header

    def as_http_header(self):
        return self.header


class ExternalServiceAccessToken(ExternalServiceAccessAuthorization, OAuth2TokenMixin):

    id = db.Column(db.Integer, db.ForeignKey('external_service_access_authorization.id'), primary_key=True)

    __mapper_args__ = {
        'polymorphic_identity': 'access_token'
    }

    def is_expired(self) -> bool:
        return self.check_token_expiration(self.expires_at)

    def is_refresh_token_valid(self) -> bool:
        return self if not self.revoked else None

    def save(self):
        db.session.add(self)
        db.session.commit()

    def delete(self):
        db.session.delete(self)
        db.session.commit()

    def as_http_header(self):
        return f"{self.token_type} {self.access_token}"

    @classmethod
    def find(cls, access_token):
        return cls.query.filter(cls.access_token == access_token).first()

    @classmethod
    def find_by_user(cls, user: User) -> List[ExternalServiceAccessToken]:
        return cls.query.filter(cls.user == user).all()

    @classmethod
    def all(cls):
        return cls.query.all()

    @staticmethod
    def check_token_expiration(expires_at) -> bool:
        return datetime.utcnow().timestamp() - expires_at > 0
