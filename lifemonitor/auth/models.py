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
from flask_bcrypt import generate_password_hash, check_password_hash
from flask_login import UserMixin, AnonymousUserMixin
from lifemonitor.db import db


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

    def __init__(self, username=None) -> None:
        super().__init__()
        self.username = username

    def get_user_id(self):
        return self.id

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
