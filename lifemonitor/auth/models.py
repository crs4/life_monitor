from __future__ import annotations

import datetime
import logging
import uuid as _uuid
from typing import List

from authlib.integrations.sqla_oauth2 import OAuth2TokenMixin
from flask_bcrypt import check_password_hash, generate_password_hash
from flask_login import AnonymousUserMixin, UserMixin
from lifemonitor.db import db
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


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(256), unique=True, nullable=False)
    password_hash = db.Column(db.LargeBinary, nullable=True)

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
        from .services import current_registry
        if current_registry:
            for i in self.oauth_identity.values():
                if i.provider == current_registry.server_credentials:
                    return i
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


class ApiKey(db.Model):
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

    def save(self):
        db.session.add(self)
        db.session.commit()

    def delete(self):
        db.session.delete(self)
        db.session.commit()

    @classmethod
    def find(cls, api_key) -> ApiKey:
        return cls.query.filter(ApiKey.key == api_key).first()

    @classmethod
    def all(cls):
        return cls.query.all()


resource_owners_table = db.Table(
    'resource_owner', db.Model.metadata,
    db.Column('resource_id', db.Integer,
              db.ForeignKey("resource.id", ondelete="CASCADE")),
    db.Column('user_id', db.Integer,
              db.ForeignKey("user.id", ondelete="CASCADE"))
)

resource_viewers_table = db.Table(
    'resource_viewer', db.Model.metadata,
    db.Column('resource_id', db.Integer,
              db.ForeignKey("resource.id", ondelete="CASCADE")),
    db.Column('user_id', db.Integer,
              db.ForeignKey("user.id", ondelete="CASCADE"))
)


class Resource(db.Model):

    id = db.Column('id', db.Integer, primary_key=True)
    uuid = db.Column(db.String, default=_uuid.uuid4)
    rtype = db.Column(db.String, nullable=False)
    type = db.Column(db.String, nullable=False)
    name = db.Column(db.String, nullable=True)
    uri = db.Column(db.String, nullable=False)
    version = db.Column(db.String, nullable=True)

    owners = db.relationship("User",
                             secondary=resource_owners_table,
                             backref="own_resources", passive_deletes=True)

    viewers = db.relationship("User",
                              secondary=resource_owners_table,
                              backref="shared_resources", passive_deletes=True)

    __mapper_args__ = {
        'polymorphic_identity': 'resource',
        'polymorphic_on': rtype,
    }

    # __table_args__ = (
    #     db.UniqueConstraint(uuid, version),
    # )

    def __init__(self, type, uri, uuid=None,
                 name=None, version=None) -> None:
        self.type = type
        self.uri = uri
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
    def find_by_uuid(cls, uuid):
        return cls.query.filter(cls.uuid == uuid).first()


resource_authorization_table = db.Table(
    'resource_authorization', db.Model.metadata,
    db.Column('resource_id', db.Integer,
              db.ForeignKey("resource.id", ondelete="CASCADE")),
    db.Column('authorization_id', db.Integer,
              db.ForeignKey("external_service_access_authorization.id", ondelete="CASCADE"))
)


class ExternalServiceAccessAuthorization(db.Model):

    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String, nullable=False)
    user_id = db.Column('user_id', db.Integer,
                        db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False)

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
