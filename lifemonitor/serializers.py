from marshmallow import pre_load, post_dump, post_load
from flask_marshmallow import Marshmallow


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
