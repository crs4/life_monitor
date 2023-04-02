# Copyright (c) 2020-2022 CRS4
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

import logging

from flask.globals import request
from flask_marshmallow import Marshmallow
from marshmallow import fields, post_dump, post_load, pre_load

from . import utils as lm_utils

# set logger
logger = logging.getLogger(__name__)

# init
ma = Marshmallow()


class BaseSchema(ma.SQLAlchemySchema):
    # Custom options
    __envelope__ = {"single": None, "many": None}
    __model__ = None

    class Meta:
        ordered = True

    @property
    def api_version(self):
        return lm_utils.OpenApiSpecs.get_instance().version

    @property
    def base_url(self):
        return lm_utils.get_external_server_url()

    @property
    def self_path(self):
        try:
            return request.full_path.strip('?')
        except RuntimeError:
            # when there is no active HTTP request
            return None

    @property
    def self_link(self):
        return f"{self.base_url}{self.self_path}"

    def get_envelope_key(self, many):
        """Helper to get the envelope key."""
        return self.__envelope__.get("many", None) if many\
            else self.__envelope__.get("single", None)

    @pre_load(pass_many=True)
    def unwrap_envelope(self, data, many, **kwargs):
        key = self.get_envelope_key(many)
        return data[key] if key else data

    @post_dump(pass_many=True)
    def wrap_with_envelope(self, data, many, **kwargs):
        key = self.get_envelope_key(many)
        return {key: data} if key else data

    @post_load
    def make_object(self, data, **kwargs):
        return self.__model__(**data) if self.__model__ else data


class MetadataSchema(BaseSchema):

    class Meta:
        ordered = True

    api_version = fields.Method("get_api_version")
    base_url = fields.Method("get_base_url")
    resource = fields.Method("get_self_path")
    created = fields.DateTime(attribute='created')
    modified = fields.DateTime(attribute='modified')

    def get_api_version(self, obj):
        return self.api_version

    def get_base_url(self, obj):
        return self.base_url

    def get_self_path(self, obj):
        return self.self_path


class ResourceMetadataSchema(BaseSchema):
    meta = fields.Method("get_metadata")
    links = fields.Method("get_links")

    def __init__(self, *args, self_link: bool = True, **kwargs):
        super().__init__(*args, **kwargs)
        self._self_link = self_link

    def get_metadata(self, obj):
        return MetadataSchema().dump(obj)

    def get_links(self, obj):
        if self._self_link:
            return {
                "self": self.self_link
            }
        return None


class ResourceSchema(ResourceMetadataSchema):
    uuid = fields.String(attribute="uuid")
    name = fields.String(attribute="name")


class ListOfItems(ResourceMetadataSchema):
    __envelope__ = {"single": None, "many": None}
    __item_scheme__ = None
    __exclude__ = ('meta',)

    items = fields.Method("get_items")

    def get_items(self, obj):
        return [self.__item_scheme__(self_link=False, exclude=self.__exclude__, many=False).dump(_) for _ in obj] \
            if self.__item_scheme__ else None


class ProblemDetailsSchema(BaseSchema):

    type = fields.String(dump_default="about:blank")
    title = fields.String(dump_default="Internal Error")
    detail = fields.String()
    status = fields.Integer(dump_default=501)
    instance = fields.String()
    extra_info = fields.Dict()
