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
from urllib.parse import urljoin

from flask.globals import request
from lifemonitor import utils as lm_utils
from lifemonitor.auth.serializers import UserSchema
from lifemonitor.serializers import BaseSchema, ma
from marshmallow import fields, post_dump

from . import models

# set module level logger
logger = logging.getLogger(__name__)


class MetadataSchema(BaseSchema):

    class Meta:
        ordered = True

    base_url = fields.Method("get_base_url")
    resource = fields.Method("get_self_path")
    created = fields.DateTime(attribute='created')
    modified = fields.DateTime(attribute='modified')

    def get_base_url(self, obj):
        return lm_utils.get_external_server_url()

    def get_self_path(self, obj):
        try:
            return request.full_path
        except RuntimeError:
            # when there is no active HTTP request
            return None


class ResourceMetadataSchema(BaseSchema):
    meta = fields.Method("get_metadata")

    def get_metadata(self, obj):
        return MetadataSchema().dump(obj)


class ResourceSchema(ResourceMetadataSchema):
    uuid = fields.String(attribute="uuid")
    name = fields.String(attribute="name")


class WorkflowRegistrySchema(BaseSchema):
    __envelope__ = {"single": None, "many": "items"}
    __model__ = models.WorkflowRegistry

    class Meta:
        model = models.WorkflowRegistry

    uuid = ma.auto_field()
    uri = ma.auto_field()
    type = fields.Method("get_type")
    name = fields.String(attributes="server_credentials.name")

    def get_type(self, obj):
        return obj.type.replace('_registry', '')


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


class RegistryWorkflowSchema(WorkflowSchema):

    registry = fields.Nested(WorkflowRegistrySchema(), attribute="")


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
                'download': urljoin(lm_utils.get_external_server_url(), f"ro_crates/{obj.id}/downloads")
            }
        }

    @post_dump
    def remove_skip_values(self, data, **kwargs):
        return {
            key: value for key, value in data.items()
            if value is not None
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
    registry = ma.Nested(WorkflowRegistrySchema(), attribute="workflow_registry")

    def get_version(self, obj):
        return VersionDetailsSchema().dump(obj)

    @post_dump
    def remove_skip_values(self, data, **kwargs):
        return {
            key: value for key, value in data.items()
            if value is not None
        }


class ListOfWorkflowVersions(ResourceMetadataSchema):
    __envelope__ = {"single": None, "many": "items"}
    __model__ = models.Workflow

    class Meta:
        model = models.Workflow
        ordered = True

    workflow = fields.Method("get_workflow")
    versions = fields.Method("get_versions")

    def get_workflow(self, obj: models.Workflow):
        return WorkflowSchema().dump(obj)

    def get_versions(self, obj: models.Workflow):
        return [VersionDetailsSchema(only=("uuid", "version", "ro_crate", "submitter")).dump(v)
                for v in obj.versions.values()]


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
    resource = ma.auto_field()
    service = fields.Method("get_testing_service")

    def get_testing_service(self, obj):
        logger.debug("Test current obj: %r", obj)
        assert obj.testing_service, "Missing testing service"
        return {
            'uuid': obj.testing_service.uuid,
            'url': obj.testing_service.url,
            'type': obj.testing_service._type.replace('_testing_service', '')
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


class WorkflowStatusSchema(WorkflowVersionSchema):
    __envelope__ = {"single": None, "many": "items"}
    __model__ = models.WorkflowStatus

    class Meta:
        model = models.WorkflowStatus

    aggregate_test_status = fields.String(attribute="status.aggregated_status")
    latest_builds = ma.Nested(BuildSummarySchema(),
                              attribute="status.latest_builds", many=True)


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
