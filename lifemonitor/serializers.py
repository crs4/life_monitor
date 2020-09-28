from marshmallow import pre_load, post_dump, post_load, fields
from flask_marshmallow import Marshmallow

import logging

logger = logging.getLogger(__name__)

ma = Marshmallow()


class BaseSchema(ma.SQLAlchemySchema):
    # Custom options
    __envelope__ = {"single": None, "many": None}
    __model__ = None

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


class ProblemDetailsSchema(BaseSchema):

    type = fields.String(default="about:blank")
    title = fields.String(default="Internal Error")
    detail = fields.String()
    status = fields.Integer(default=501)
    instance = fields.String()
    extra_info = fields.Dict()
