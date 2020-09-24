
from . import models


from lifemonitor.serializers import ma, BaseSchema


class WorkflowSchema(BaseSchema):
    __envelope__ = {"single": None, "many": "items"}
    __model__ = models.Workflow

    class Meta:
        model = models.Workflow

    uuid = ma.auto_field()
    version = ma.auto_field()
    roc_link = ma.auto_field()
    name = ma.auto_field()
