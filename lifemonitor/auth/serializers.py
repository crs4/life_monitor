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

from lifemonitor.serializers import BaseSchema, ma
from marshmallow import fields

from . import models


class ProviderSchema(BaseSchema):
    uuid = fields.String()
    name = fields.String()
    type = fields.Method('get_type')
    uri = fields.String(attribute="api_base_url")
    userinfo_endpoint = fields.String()

    def get_type(self, object):
        return object.type \
            if object.type == 'oauth2_identity_provider' \
            else 'registry'


class IdentitySchema(BaseSchema):
    sub = fields.String(attribute="provider_user_id")
    iss = fields.String(attribute="provider.api_base_url")
    email = fields.String(attribute="user_info.email")
    mbox_sha1sum = fields.String(attribute="user_info.mbox_sha1sum")
    profile = fields.String(attribute="user_info.profile")
    picture = fields.String(attribute="user_info.picture")
    provider = fields.Nested(ProviderSchema())


class UserSchema(BaseSchema):
    __envelope__ = {"single": None, "many": "items"}
    __model__ = models.User

    class Meta:
        model = models.User

    id = ma.auto_field()
    username = ma.auto_field()
    #identity = fields.Nested(IdentitySchema(), attribute="current_identity")
    # Uncomment to include all identities
    identity = fields.Dict(attribute="current_identity",
                           keys=fields.String(),
                           values=fields.Nested(IdentitySchema()))
