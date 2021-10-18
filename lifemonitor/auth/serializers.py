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

from lifemonitor.serializers import (BaseSchema, ListOfItems,
                                     ResourceMetadataSchema, ma)
from marshmallow import fields

from . import models
from ..utils import get_external_server_url

# Config a module level logger
logger = logging.getLogger(__name__)


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
    name = fields.String(attribute="user_info.name")
    username = fields.String(attribute="user_info.preferred_username")
    email = fields.String(attribute="user_info.email")
    mbox_sha1sum = fields.String(attribute="user_info.mbox_sha1sum")
    profile = fields.String(attribute="user_info.profile")
    picture = fields.String(attribute="user_info.picture")
    provider = fields.Nested(ProviderSchema())


class UserSchema(ResourceMetadataSchema):
    __envelope__ = {"single": None, "many": "items"}
    __model__ = models.User

    class Meta:
        model = models.User

    id = ma.auto_field()
    username = ma.auto_field()
    # identities = fields.Dict(attribute="current_identity",
    #                          keys=fields.String(),
    #                          values=fields.Nested(IdentitySchema()))
    identities = fields.Method("current_identity")

    def current_identity(self, user):
        # TODO:  these should probably defined in a Model somewhere
        lm_identity_provider = {
            "name": "LifeMonitor",
            "type": "oauth2_identity_provider",
            "uri": get_external_server_url(),
            "userinfo_endpoint": get_external_server_url() + "/users/current"
        }
        lm_user_identity = {
            "sub": str(user.id),
            "username": user.username,
            "picture": user.picture,
            "provider": lm_identity_provider,
        }

        identities = {"lifemonitor": lm_user_identity}

        # Add any other identities that the user has
        if user.current_identity:
            for k, v in user.current_identity.items():
                if k == 'lifemonitor':
                    raise RuntimeError("BUG: user has a second lifemonitor identity")
                try:
                    identities[k] = IdentitySchema().dump(v)
                except Exception as e:
                    logger.error("Unable to retrieve profile"
                                 "of user % r from provider % r: % r", user.id, k, str(e))
        return identities


class ListOfUsers(ListOfItems):
    __item_scheme__ = UserSchema


class SubscriptionSchema(ResourceMetadataSchema):
    __envelope__ = {"single": None, "many": "items"}
    __model__ = models.Subscription

    class Meta:
        model = models.Subscription

    user = ma.Nested(UserSchema(only=('id', 'username')),
                     attribute="user", many=False)
    created = fields.String(attribute='created')
    modified = fields.String(attribute='modified')

    resource = fields.Method("get_resource")

    def get_resource(self, obj: models.Subscription):
        return {
            'uuid': obj.resource.uuid,
            'type': obj.resource.type
        }


class ListOfSubscriptions(ListOfItems):
    __item_scheme__ = SubscriptionSchema
