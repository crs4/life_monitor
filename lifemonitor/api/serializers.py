from __future__ import annotations
from . import models

from marshmallow import fields
from lifemonitor.serializers import ma, BaseSchema


class WorkflowRegistrySchema(BaseSchema):
    __envelope__ = {"single": None, "many": "items"}
    __model__ = models.WorkflowRegistry

    class Meta:
        model = models.WorkflowRegistry

    uuid = ma.auto_field()
    uri = ma.auto_field()
    type = ma.auto_field()
    name = fields.String(attributes="server_credentials.name")


class ListOfWorkflowRegistriesSchema(BaseSchema):
    __envelope__ = {"single": None, "many": "items"}

    items = fields.Nested(WorkflowRegistrySchema(), many=True)


class WorkflowSchema(BaseSchema):
    __envelope__ = {"single": None, "many": "items"}
    __model__ = models.Workflow

    class Meta:
        model = models.Workflow

    uuid = ma.auto_field()
    version = ma.auto_field()
    roc_link = ma.auto_field()
    name = ma.auto_field()


class LatestWorkflowSchema(WorkflowSchema):
    previous_versions = fields.List(fields.String, attribute="previous_versions")


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
    __envelope__ = {"single": None, "many": None}
    __model__ = models.TestInstance

    class Meta:
        model = models.TestInstance

    uuid = ma.auto_field()
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
    last_logs = fields.Method("get_last_logs")

    def get_last_logs(self, obj):
        return "" if not obj.output else obj.output[-400:]


class WorkflowStatusSchema(BaseSchema):
    __envelope__ = {"single": None, "many": "items"}
    __model__ = models.WorkflowStatus

    class Meta:
        model = models.WorkflowStatus

    workflow = ma.Nested(WorkflowSchema(only=("uuid", "version", "name")))
    aggregate_test_status = fields.String(attribute="aggregated_status")
    latest_builds = ma.Nested(BuildSummarySchema(), many=True)


class SuiteSchema(BaseSchema):
    __envelope__ = {"single": None, "many": "items"}
    __model__ = models.TestSuite

    class Meta:
        model = models.TestSuite

    uuid = ma.auto_field()
    test_suite_metadata = fields.Dict(attribute="test_definition")  # TODO: rename the property to metadata
    instances = fields.Nested(TestInstanceSchema(),
                              attribute="test_instances", many=True)


class SuiteStatusSchema(BaseSchema):
    __envelope__ = {"single": None, "many": "items"}
    __model__ = models.SuiteStatus

    class Meta:
        model = models.SuiteStatus

    suite_uuid = fields.String(attribute="suite.uuid")
    status = fields.String(attribute="aggregated_status")
    latest_builds = fields.Nested(BuildSummarySchema(), many=True)


class ListOfTestInstancesSchema(BaseSchema):
    __envelope__ = {"single": None, "many": "items"}

    items = fields.Nested(TestInstanceSchema(), attribute="test_instances", many=True)


class ListOfTestBuildsSchema(BuildSummarySchema):
    __envelope__ = {"single": None, "many": "items"}
