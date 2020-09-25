from __future__ import annotations
from . import models

from marshmallow import fields
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


class TestServiceSchema(BaseSchema):
    __envelope__ = {"single": None, "many": "items"}
    __model__ = models.TestingService

    class Meta:
        model = models.TestingService

    uuid = ma.auto_field()
    type = fields.String(attribute="_type")
    url = ma.auto_field()
    resource = ma.auto_field()


class TestInstanceSchema(BaseSchema):
    __envelope__ = {"single": None, "many": "items"}
    __model__ = models.TestInstance

    class Meta:
        model = models.TestInstance

    name = ma.auto_field()
    service = ma.Nested(TestServiceSchema(), attribute="testing_service")


class BuildSummarySchema(BaseSchema):
    __envelope__ = {"single": None, "many": None}
    __model__ = models.TestBuild

    class Meta:
        model = models.TestBuild

    build_id = fields.String(attribute="build_number")
    suite_uuid = fields.String(attribute="testing_service.test_instance.test_suite.uuid")
    status = fields.String()
    instance = ma.Nested(TestInstanceSchema(), attribute="testing_service.test_instance")
    timestamp = fields.String()
    last_logs = fields.String()


class WorkflowStatusSchema(BaseSchema):
    __envelope__ = {"single": None, "many": "items"}
    __model__ = models.WorkflowStatus

    class Meta:
        model = models.WorkflowStatus

    workflow = ma.Nested(WorkflowSchema(only=("uuid", "version", "name")))
    aggregate_test_status = fields.String(attribute="aggregated_status")
    latest_builds = ma.Nested(BuildSummarySchema(), many=True)
