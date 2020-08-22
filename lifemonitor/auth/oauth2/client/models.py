from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm.collections import attribute_mapped_collection

from lifemonitor.app import db
from lifemonitor.auth.models import User


class OAuthUserProfile(object):

    def __init__(self, sub=None, name=None, email=None, preferred_username=None,
                 profile=None, picture=None, website=None) -> None:
        self.sub = sub
        self.name = name
        self.email = email
        self.preferred_username = preferred_username
        self.profile = profile
        self.picture = picture
        self.website = website

    def to_dict(self):
        res = {}
        for k in ['sub', 'name', 'email', 'preferred_username', 'profile', 'picture', 'website']:
            res[k] = getattr(self, k)
        return res

    @staticmethod
    def from_dict(data: dict):
        profile = OAuthUserProfile()
        for k, v, in data.items():
            setattr(profile, k, v)
        return profile


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
