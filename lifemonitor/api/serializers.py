from __future__ import annotations

import logging
from urllib.parse import urljoin

from flask import current_app
from flask.globals import request
from lifemonitor.auth.serializers import UserSchema
from lifemonitor.serializers import BaseSchema, ma
from marshmallow import fields

from . import models

# set module level logger
logger = logging.getLogger(__name__)


def _get_base_url():
    if 'EXTERNAL_ACCESS_BASE_URL' in current_app.config:
        return current_app.config['EXTERNAL_ACCESS_BASE_URL']
    return current_app.config.get("BASE_URL", None)


class MetadataSchema(BaseSchema):

    class Meta:
        ordered = True

    base_url = fields.Method("get_base_url")
    resource = fields.Method("get_self_path")
    created = fields.DateTime(attribute='created')
    modified = fields.DateTime(attribute='modified')

    def get_base_url(self, obj):
        return _get_base_url()

    def get_self_path(self, obj):
        try:
            return request.full_path
        except RuntimeError:
            # when there is no active HTTP request
            return None


class ResourceSchema(BaseSchema):
    uuid = fields.String(attribute="uuid")
    name = fields.String(attribute="name")
    meta = fields.Method("get_metadata")

    def get_metadata(self, obj):
        return MetadataSchema().dump(obj)


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


class VersionDetailsSchema(BaseSchema):
    __envelope__ = {"single": None, "many": "items"}

    uuid = fields.String(attribute="uuid")
    version = fields.String(attribute="version")
    is_latest = fields.Boolean(attribute="is_latest")
    ro_crate = fields.Method("get_rocrate")
    submitter = ma.Nested(UserSchema(only=('id', 'username')), attribute="submitter")

    def get_rocrate(self, obj):
        return {
            'links': {
                'external': obj.uri,
                'download': urljoin(_get_base_url(), f"ro_crates/{obj.id}/downloads")
            }
        }


class WorkflowVersionSchema(ResourceSchema):
    __envelope__ = {"single": None, "many": "items"}
    __model__ = models.WorkflowVersion

    class Meta:
        model = models.WorkflowVersion
        ordered = True

    uuid = fields.String(attribute="workflow.uuid")
    name = ma.auto_field()
    version = fields.Method("get_version")

    def get_version(self, obj):
        return VersionDetailsSchema().dump(obj)


class LatestWorkflowSchema(WorkflowVersionSchema):
    previous_versions = fields.Method("get_versions")

    def get_versions(self, obj: models.WorkflowVersion):
        return [VersionDetailsSchema(only=("uuid", "version", "submitter")).dump(v)
                for v in obj.workflow.versions.values() if not v.is_latest]


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
