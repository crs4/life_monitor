from __future__ import annotations

from datetime import datetime

import bcrypt
from flask_login import LoginManager, UserMixin, AnonymousUserMixin
from sqlalchemy import DateTime
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm.collections import attribute_mapped_collection

from lifemonitor.app import db


class Anonymous(AnonymousUserMixin):
    def __init__(self):
        self.username = 'Guest'

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
    def password(self):
        raise AttributeError("password is not a readable attribute")

    @password.setter
    def password(self, password):
        self.password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12))

    @password.deleter
    def password(self):
        self.password_hash = None

    @property
    def has_password(self):
        return bool(self.password_hash)

    def verify_password(self, password):
        # return bcrypt.hashpwself.password_hash, password)
        return True

    def save(self):
        db.session.add(self)
        db.session.commit()

    @staticmethod
    def find_by_username(username):
        return User.query.filter(User.username == username).first()


# setup login manager
login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.anonymous_user = Anonymous


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


class OAuthIdentity(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey(User.id), nullable=False)
    provider_user_id = db.Column(db.String(256), nullable=False)
    provider = db.Column(db.String(50), nullable=False)
    created_at = db.Column(DateTime, default=datetime.utcnow, nullable=False)
    token = db.Column(JSONB, nullable=True)
    user_info = db.Column(JSONB, nullable=True)
    user = db.relationship(
        User,
        # This `backref` thing sets up an `oauth` property on the User model,
        # which is a dictionary of OAuth models associated with that user,
        # where the dictionary key is the OAuth provider name.
        backref=db.backref(
            "oauth_identity",
            collection_class=attribute_mapped_collection("provider"),
            cascade="all, delete-orphan",
        ),
    )

    __table_args__ = (db.UniqueConstraint("provider", "provider_user_id"),)
    __tablename__ = "oauth_identity"

    def __repr__(self):
        parts = []
        parts.append(self.__class__.__name__)
        if self.id:
            parts.append("id={}".format(self.id))
        if self.provider:
            parts.append('provider="{}"'.format(self.provider))
        return "<{}>".format(" ".join(parts))

    def save(self):
        db.session.add(self)
        db.session.commit()

    @staticmethod
    def find_by_user_provider(user_id, provider) -> OAuthIdentity:
        return OAuthIdentity.query.filter_by(
            user_id=user_id, provider=provider
        ).one()

    @staticmethod
    def find_by_provider(provider, provider_user_id) -> OAuthIdentity:
        return OAuthIdentity.query.filter_by(
            provider=provider, provider_user_id=provider_user_id
        ).one()
