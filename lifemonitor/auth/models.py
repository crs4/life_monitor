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
import base64
import datetime
import json
import logging
import random
import string
import uuid as _uuid
from enum import Enum
from typing import List

from authlib.integrations.sqla_oauth2 import OAuth2TokenMixin
from flask_bcrypt import check_password_hash, generate_password_hash
from flask_login import AnonymousUserMixin, UserMixin
from lifemonitor import exceptions as lm_exceptions
from lifemonitor import utils as lm_utils
from lifemonitor.db import db
from lifemonitor.models import JSON, UUID, IntegerSet, ModelMixin
from sqlalchemy import null
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.ext.mutable import MutableSet

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
    _email_notifications_enabled = db.Column("email_notifications", db.Boolean,
                                             nullable=False, default=True)
    _email = db.Column("email", db.String(), nullable=True)
    _email_verification_code = None
    _email_verification_hash = db.Column("email_verification_hash", db.String(256), nullable=True)
    _email_verified = db.Column("email_verified", db.Boolean, nullable=True, default=False)
    permissions = db.relationship("Permission", back_populates="user",
                                  cascade="all, delete-orphan")
    authorizations = db.relationship("ExternalServiceAccessAuthorization",
                                     cascade="all, delete-orphan")

    subscriptions = db.relationship("Subscription", cascade="all, delete-orphan")

    notifications: List[UserNotification] = db.relationship("UserNotification",
                                                            back_populates="user",
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

    def verify_password(self, password):
        return check_password_hash(self.password_hash, password)

    def _generate_random_code(self, chars=string.ascii_uppercase + string.digits):
        return base64.b64encode(
            json.dumps(
                {
                    "email": self._email,
                    "code": ''.join(random.choice(chars) for _ in range(16)),
                    "expires": (datetime.datetime.now() + datetime.timedelta(hours=1)).timestamp()
                }
            ).encode('ascii')
        ).decode()

    @staticmethod
    def _decode_random_code(code):
        try:
            code = code.encode() if isinstance(code, str) else code
            return json.loads(base64.b64decode(code.decode('ascii')))
        except Exception as e:
            logger.debug(e)
            return None

    @property
    def email_notifications_enabled(self):
        return self._email_notifications_enabled

    def disable_email_notifications(self):
        self._email_notifications_enabled = False

    def enable_email_notifications(self):
        self._email_notifications_enabled = True

    @property
    def email(self) -> str:
        return self._email

    @email.setter
    def email(self, email: str):
        if email and email != self._email:
            self._email = email
            self.generate_email_verification_code()

    @email.deleter
    def email(self):
        self._email = None
        self._email_verified = False

    def generate_email_verification_code(self):
        self._email_verified = False
        code = self._generate_random_code()
        self._email_verification_code = code
        self._email_verification_hash = generate_password_hash(code).decode('utf-8')
        return self._email_verification_code

    @property
    def email_verification_code(self) -> str:
        return self._email_verification_code

    @property
    def email_verified(self) -> bool:
        return self._email_verified

    def verify_email(self, code):
        if not self._email:
            raise lm_exceptions.IllegalStateException(detail="No notification email found")
        # verify integrity
        if not code or \
            not check_password_hash(
                self._email_verification_hash, code):
            raise lm_exceptions.LifeMonitorException(detail="Invalid verification code")
        try:
            data = self._decode_random_code(code)
        except Exception as e:
            logger.debug(e)
            raise lm_exceptions.LifeMonitorException(detail="Invalid verification code")
        if data['email'] != self._email:
            raise lm_exceptions.LifeMonitorException(detail="Notification email not valid")
        if data['expires'] < datetime.datetime.now().timestamp():
            raise lm_exceptions.LifeMonitorException(detail="Verification code expired")
        self._email_verified = True
        return True

    def get_user_notification(self, notification_uuid: str) -> UserNotification:
        return next((n for n in self.notifications if str(n.notification.uuid) == notification_uuid), None)

    def get_notification(self, notification_uuid: str) -> Notification:
        user_notification = self.get_user_notification(notification_uuid)
        return None if not user_notification else user_notification.notification

    def remove_notification(self, n: Notification | UserNotification):
        user_notification = None
        try:
            user_notification = self.get_user_notification(n.uuid)
            if user_notification is None:
                raise ValueError(f"notification {n.uuid} not associated to this user")
        except Exception:
            user_notification = n
        if n is None:
            raise ValueError("notification cannot be None")
        self.notifications.remove(user_notification)
        logger.debug("User notification %r removed", user_notification)

    def has_permission(self, resource: Resource) -> bool:
        return self.get_permission(resource) is not None

    def get_permission(self, resource: Resource) -> Permission:
        return next((p for p in self.permissions if p.resource == resource), None)

    def get_subscription(self, resource: Resource) -> Subscription:
        return next((s for s in self.subscriptions if s.resource == resource), None)

    def is_subscribed_to(self, resource: Resource) -> bool:
        return self.get_subscription(resource) is not None

    def subscribe(self, resource: Resource) -> Subscription:
        s = self.get_subscription(resource)
        if not s:
            s = Subscription(resource, self)
        return s

    def unsubscribe(self, resource: Resource):
        s = self.get_subscription(resource)
        if s:
            self.subscriptions.remove(s)
        return s

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


class EventType(Enum):
    ALL = 0
    BUILD_FAILED = 1
    BUILD_RECOVERED = 2

    @classmethod
    def all(cls):
        return list(map(lambda c: c, cls))

    @classmethod
    def all_names(cls):
        return list(map(lambda c: c.name, cls))

    @classmethod
    def all_values(cls):
        return list(map(lambda c: c.value, cls))

    @classmethod
    def to_string(cls, event: EventType) -> str:
        return event.name if event else None

    @classmethod
    def to_strings(cls, event_list: List[EventType]) -> List[str]:
        return [cls.to_string(_) for _ in event_list if _] if event_list else []

    @classmethod
    def from_string(cls, event_name: str) -> EventType:
        try:
            return cls[event_name]
        except KeyError:
            raise ValueError("'%s' is not a valid EventType", event_name)

    @classmethod
    def from_strings(cls, event_name_list: List[str]) -> List[EventType]:
        if not event_name_list:
            return []
        return [cls.from_string(_) for _ in event_name_list]


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
        self.uri = uri.rstrip('/')
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

    def get_subscribers(self, event: EventType = EventType.ALL) -> List[User]:
        users = {s.user for s in self.subscriptions if s.has_event(event)}
        users.update({s.user for s in self.subscriptions if s.has_event(event)})
        return users


resource_authorization_table = db.Table(
    'resource_authorization', db.Model.metadata,
    db.Column('resource_id', db.Integer,
              db.ForeignKey("resource.id", ondelete="CASCADE")),
    db.Column('authorization_id', db.Integer,
              db.ForeignKey("external_service_access_authorization.id", ondelete="CASCADE"))
)


class Subscription(db.Model, ModelMixin):
    id = db.Column(db.Integer, primary_key=True)
    created = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    modified = db.Column(db.DateTime, default=datetime.datetime.utcnow,
                         onupdate=datetime.datetime.utcnow)

    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    user: User = db.relationship("User", uselist=False, back_populates="subscriptions", foreign_keys=[user_id])

    resource_id = db.Column(db.Integer, db.ForeignKey("resource.id"), nullable=False)
    resource: Resource = db.relationship("Resource", uselist=False,
                                         backref=db.backref("subscriptions", cascade="all, delete-orphan"),
                                         foreign_keys=[resource_id])
    _events = db.Column("events", MutableSet.as_mutable(IntegerSet()), default={0})

    def __init__(self, resource: Resource, user: User) -> None:
        self.resource = resource
        self.user = user

    def __get_events(self):
        if self._events is None:
            self._events = {0}
        return self._events

    @property
    def events(self) -> set:
        return [EventType(e) for e in self.__get_events()]

    @events.setter
    def events(self, events: List[EventType]):
        self.__get_events().clear()
        if events:
            for e in events:
                if not isinstance(e, EventType):
                    raise ValueError(f"Not valid event value: expected {EventType.__class__}, got {type(e)}")
                self.__get_events().add(e.value)

    def has_event(self, event: EventType) -> bool:
        return False if event is None else \
            EventType.ALL.value in self.__get_events() or \
            event.value in self.__get_events()

    def has_events(self, events: List[EventType]) -> bool:
        if events:
            for e in events:
                if not self.has_event(e):
                    return False
        return True


class Notification(db.Model, ModelMixin):

    id = db.Column(db.Integer, primary_key=True)
    uuid = db.Column(UUID, default=_uuid.uuid4, nullable=False, index=True)
    created = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    name = db.Column("name", db.String, nullable=True, index=True)
    _event = db.Column("event", db.Integer, nullable=False)
    _data = db.Column("data", JSON, nullable=True)

    users: List[UserNotification] = db.relationship("UserNotification",
                                                    back_populates="notification", cascade="all, delete-orphan")

    def __init__(self, event: EventType, name: str, data: object, users: List[User]) -> None:
        self.name = name
        self._event = event.value
        self._data = data
        for u in users:
            self.add_user(u)

    @property
    def event(self) -> EventType:
        return EventType(self._event)

    @property
    def data(self) -> object:
        return self._data

    def add_user(self, user: User):
        if user and user not in self.users:
            UserNotification(user, self)

    def remove_user(self, user: User):
        self.users.remove(user)

    @classmethod
    def find_by_name(cls, name: str) -> List[Notification]:
        return cls.query.filter(cls.name == name).all()

    @classmethod
    def not_read(cls) -> List[Notification]:
        return cls.query.join(UserNotification, UserNotification.notification_id == cls.id)\
            .filter(UserNotification.read == null()).all()

    @classmethod
    def not_emailed(cls) -> List[Notification]:
        return cls.query.join(UserNotification, UserNotification.notification_id == cls.id)\
            .filter(UserNotification.emailed == null()).all()


class UserNotification(db.Model):

    emailed = db.Column(db.DateTime, default=None, nullable=True)
    read = db.Column(db.DateTime, default=None, nullable=True)

    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, primary_key=True)

    notification_id = db.Column(db.Integer, db.ForeignKey("notification.id"), nullable=False, primary_key=True)

    user: User = db.relationship("User", uselist=False,
                                 back_populates="notifications", foreign_keys=[user_id],
                                 cascade="save-update")

    notification: Notification = db.relationship("Notification", uselist=False,
                                                 back_populates="users",
                                                 foreign_keys=[notification_id],
                                                 cascade="save-update")

    def __init__(self, user: User, notification: Notification) -> None:
        self.user = user
        self.notification = notification

    def save(self):
        db.session.add(self)
        db.session.commit()

    def delete(self):
        db.session.delete(self)
        db.session.commit()


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
    def get_rocrate_external_link(self, external_id: str, version: str) -> str:
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
