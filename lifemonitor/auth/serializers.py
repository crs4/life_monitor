from __future__ import annotations
from . import models

from marshmallow import fields
from lifemonitor.serializers import ma, BaseSchema


class IdentitySchema(BaseSchema):

    user_info = fields.Dict()


class UserSchema(BaseSchema):
    __envelope__ = {"single": None, "many": "items"}
    __model__ = models.User

    class Meta:
        model = models.User

    id = ma.auto_field()
    username = ma.auto_field()
    identities = fields.Nested(IdentitySchema(), attribute="oauth_identity.values()", many=True)
