from __future__ import annotations

import logging

from lifemonitor.serializers import BaseSchema, ma
from marshmallow import fields

from . import models

# set module level logger
logger = logging.getLogger(__name__)


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
    __model__ = models.WorkflowVersion

    class Meta:
        model = models.WorkflowVersion

    uuid = ma.auto_field()
    name = ma.auto_field()


class WorkflowVersionSchema(BaseSchema):
    __envelope__ = {"single": None, "many": "items"}
    __model__ = models.WorkflowVersion

    class Meta:
        model = models.WorkflowVersion

    uuid = fields.Method("get_uuid")
    version = ma.auto_field()
    roc_link = fields.String(attributes="ro_crate.uri")
    name = ma.auto_field()
    latest_version = fields.Boolean(attributes="latest_version")

    def get_uuid(self, obj):
        return obj.workflow.uuid


class WorkflowVersionDetailsSchema(WorkflowVersionSchema):
    versions = fields.Method("get_versions")

    def get_versions(self, obj: models.WorkflowVersion):
        return [v.version for v in obj.workflow.versions.values()]


class LatestWorkflowSchema(WorkflowVersionSchema):
    previous_versions = fields.List(fields.String, attribute="previous_versions")


class TestInstanceSchema(BaseSchema):
    __envelope__ = {"single": None, "many": None}
    __model__ = models.TestInstance

    class Meta:
        model = models.TestInstance

    uuid = ma.auto_field()
    name = ma.auto_field()
    service = fields.Method("get_testing_service")

    def get_testing_service(self, obj):
        logger.debug("Test current obj: %r", obj)
        return {
            'uuid': obj.testing_service.uuid,
            'url': obj.testing_service.url,
            'type': obj.testing_service._type,
            'resource': obj.resource
        }


class BuildSummarySchema(BaseSchema):
    __envelope__ = {"single": None, "many": None}
    __model__ = models.TestBuild

    class Meta:
        model = models.TestBuild

    build_id = fields.String(attribute="id")
    suite_uuid = fields.String(attribute="test_instance.test_suite.uuid")
    status = fields.String()
    instance = ma.Nested(TestInstanceSchema(), attribute="test_instance")
    timestamp = fields.String()
    last_logs = fields.Method("get_last_logs")

    def get_last_logs(self, obj):
        return obj.get_output(0, 131072)


class WorkflowStatusSchema(BaseSchema):
    __envelope__ = {"single": None, "many": "items"}
    __model__ = models.WorkflowStatus

    class Meta:
        model = models.WorkflowStatus

    workflow = ma.Nested(WorkflowVersionSchema(only=("uuid", "version", "name")))
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
