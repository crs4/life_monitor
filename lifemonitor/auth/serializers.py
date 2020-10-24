from __future__ import annotations
from . import models
from marshmallow import fields
from lifemonitor.serializers import ma, BaseSchema


class ProviderSchema(BaseSchema):
    uuid = fields.String()
    name = fields.String()
    type = fields.String()
    uri = fields.String(attribute="api_base_url")
    userinfo_endpoint = fields.String()


class IdentitySchema(BaseSchema):
    sub = fields.String(attribute="provider_user_id")
    # iss = fields.String(attribute="provider.api_base_url")
    # email = fields.String(attribute="user_info.email")
    # mbox_sha1sum = fields.String(attribute="user_info.mbox_sha1sum")
    # profile = fields.String(attribute="user_info.profile")
    # picture = fields.String(attribute="user_info.picture")
    provider = fields.Nested(ProviderSchema())


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
