from __future__ import annotations
from . import models
from marshmallow import fields
from lifemonitor.serializers import ma, BaseSchema


class ProviderSchema(BaseSchema):

    name = fields.String()
    type = fields.String()
    uri = fields.String(attribute="api_base_url")
    userinfo_endpoint = fields.String()


class IdentitySchema(BaseSchema):
    id = fields.String(attribute="user_info.sub")
    provider = fields.Nested(ProviderSchema())
    user_profile = fields.Dict(attribute="user_info")


class UserSchema(BaseSchema):
    __envelope__ = {"single": None, "many": "items"}
    __model__ = models.User

    class Meta:
        model = models.User

    id = ma.auto_field()
    username = ma.auto_field()
    identity = fields.Nested(IdentitySchema(), attribute="current_identity")
    # Uncomment to include all identities
    # identities = fields.Dict(attribute="oauth_identity",
    #                          keys=fields.String(),
    #                          values=fields.Nested(IdentitySchema()))
