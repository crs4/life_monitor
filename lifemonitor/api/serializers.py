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
from typing import List
from urllib.parse import urljoin

from lifemonitor import exceptions as lm_exceptions
from lifemonitor import utils as lm_utils
from lifemonitor.auth import models as auth_models
from lifemonitor.auth.serializers import SubscriptionSchema, UserSchema
from lifemonitor.serializers import (BaseSchema, ListOfItems,
                                     ResourceMetadataSchema, ResourceSchema,
                                     ma)
from marshmallow import fields, post_dump

from . import models

# set module level logger
logger = logging.getLogger(__name__)


class WorkflowRegistrySchema(ResourceMetadataSchema):
    __envelope__ = {"single": None, "many": "items"}
    __model__ = models.WorkflowRegistry

    class Meta:
        model = models.WorkflowRegistry

    uuid = ma.auto_field()
    uri = ma.auto_field()
    type = fields.Method("get_type")
    name = fields.String(attribute="server_credentials.name")

    def get_type(self, obj):
        return obj.type.replace('_registry', '')


class ListOfWorkflowRegistriesSchema(ListOfItems):
    __item_scheme__ = WorkflowRegistrySchema


class WorkflowSchema(ResourceMetadataSchema):
    __envelope__ = {"single": None, "many": "items"}
    __model__ = models.WorkflowVersion

    class Meta:
        model = models.WorkflowVersion

    uuid = ma.auto_field()
    name = ma.auto_field()


class RegistryWorkflowSchema(WorkflowSchema):
    registry = fields.Nested(WorkflowRegistrySchema(exclude=('meta', 'links')), attribute="")


class VersionDetailsSchema(BaseSchema):
    __envelope__ = {"single": None, "many": "items"}

    uuid = fields.String(attribute="uuid")
    name = fields.String(attribute="name")
    version = fields.String(attribute="version")
    is_latest = fields.Boolean(attribute="is_latest")
    ro_crate = fields.Method("get_rocrate")
    submitter = ma.Nested(UserSchema(only=('id', 'username')), attribute="submitter")
    links = fields.Method('get_links')

    class Meta:
        model = models.WorkflowVersion
        additional = ('rocrate_metadata',)

    def get_links(self, obj: models.WorkflowVersion):
        return {
            'origin': obj.external_link
        }

    def get_rocrate(self, obj):
        rocrate = {
            'links': {
                'origin': obj.uri,
                'metadata': urljoin(lm_utils.get_external_server_url(),
                                    f"workflows/{obj.workflow.uuid}/rocrate/{obj.version}/metadata"),
                'download': urljoin(lm_utils.get_external_server_url(),
                                    f"workflows/{obj.workflow.uuid}/rocrate/{obj.version}/download")
            }
        }
        rocrate['metadata'] = obj.crate_metadata
        if 'rocrate_metadata' in self.exclude or \
                self.only and 'rocrate_metadata' not in self.only:
            del rocrate['metadata']
        return rocrate

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
    name = ma.auto_field(attribute="workflow.name")
    version = fields.Method("get_version")
    public = fields.Boolean(attribute="workflow.public")
    registry = ma.Nested(WorkflowRegistrySchema(exclude=('meta', 'links')),
                         attribute="hosting_service")
    subscriptions = fields.Method("get_subscriptions")

    rocrate_metadata = False
    subscriptionsOf: List[auth_models.User] = None

    def __init__(self, *args, rocrate_metadata=False, subscriptionsOf=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.rocrate_metadata = rocrate_metadata
        self.subscriptionsOf = subscriptionsOf

    def get_version(self, obj):
        exclude = ('rocrate_metadata',) if not self.rocrate_metadata else ()
        return VersionDetailsSchema(exclude=exclude).dump(obj)

    def get_subscriptions(self, wv: models.WorkflowVersion):
        result = []
        if self.subscriptionsOf:
            for user in self.subscriptionsOf:
                s = user.get_subscription(wv)
                if s:
                    result.append(SubscriptionSchema(exclude=('meta', 'links'), self_link=False).dump(s))
                s = user.get_subscription(wv.workflow)
                if s:
                    result.append(SubscriptionSchema(exclude=('meta', 'links'), self_link=False).dump(s))
        return result

    @post_dump
    def remove_skip_values(self, data, **kwargs):
        return {
            key: value for key, value in data.items()
            if value is not None
        }


class LatestWorkflowVersionSchema(WorkflowVersionSchema):

    previous_versions = fields.Method("get_versions")

    def get_versions(self, obj: models.WorkflowVersion):
        schema = VersionDetailsSchema(only=("uuid", "version", "ro_crate"))
        return [schema.dump(v)
                for v in obj.workflow.versions.values() if not v.is_latest]


class ListOfWorkflowVersions(ResourceMetadataSchema):

    class Meta:
        model = models.Workflow
        ordered = True

    workflow = fields.Method("get_workflow")
    versions = fields.Method("get_versions")

    def get_workflow(self, obj: models.Workflow):
        return WorkflowSchema(exclude=('meta',)).dump(obj)

    def get_versions(self, obj: models.Workflow):
        return [VersionDetailsSchema(only=("uuid", "version", "ro_crate",
                                           "submitter", "is_latest")).dump(v)
                for v in obj.versions.values()]


class LatestWorkflowSchema(WorkflowVersionSchema):
    previous_versions = fields.Method("get_versions")

    def get_versions(self, obj: models.WorkflowVersion):
        schema = VersionDetailsSchema(only=("uuid", "version", "submitter"))
        return [schema.dump(v)
                for v in obj.workflow.versions.values() if not v.is_latest]


class TestInstanceSchema(ResourceMetadataSchema):
    __envelope__ = {"single": None, "many": None}
    __model__ = models.TestInstance

    class Meta:
        model = models.TestInstance

    uuid = ma.auto_field()
    roc_instance = ma.auto_field()
    name = ma.auto_field()
    resource = ma.auto_field()
    managed = fields.Boolean(attribute="managed")
    service = fields.Method("get_testing_service")
    links = fields.Method('get_links')

    def get_links(self, obj):
        links = {}
        try:
            links['origin'] = obj.external_link
        except lm_exceptions.RateLimitExceededException:
            links['origin'] = None
        if self._self_link:
            links['self'] = self.self_link
        return links

    def get_testing_service(self, obj):
        logger.debug("Test current obj: %r", obj)
        assert obj.testing_service, "Missing testing service"
        return {
            'uuid': obj.testing_service.uuid,
            'url': obj.testing_service.url,
            'type': obj.testing_service._type.replace('_testing_service', '')
        }

    @post_dump
    def remove_skip_values(self, data, **kwargs):
        return {
            key: value for key, value in data.items()
            if value is not None
        }


class BuildSummarySchema(ResourceMetadataSchema):
    __envelope__ = {"single": None, "many": None}
    __model__ = models.TestBuild

    class Meta:
        model = models.TestBuild

    build_id = fields.String(attribute="id")
    suite_uuid = fields.String(attribute="test_instance.test_suite.uuid")
    status = fields.String()
    instance = ma.Nested(TestInstanceSchema(self_link=False, exclude=('meta',)), attribute="test_instance")
    timestamp = fields.String()
    duration = fields.Integer()
    links = fields.Method('get_links')

    def get_links(self, obj):
        links = {
            'origin': obj.external_link
        }
        if self._self_link:
            links['self'] = self.self_link
        return links


def format_availability_issues(status: models.WorkflowStatus):
    issues = status.availability_issues
    logger.info(issues)
    if 'not_available' == status.aggregated_status and len(issues) > 0:
        return ', '.join([f"{i['issue']}: Unable to get resource '{i['resource']}' from service '{i['service']}'" if 'service' in i else i['issue'] for i in issues])
    return None


class WorkflowStatusSchema(WorkflowVersionSchema):
    __envelope__ = {"single": None, "many": "items"}
    __model__ = models.WorkflowStatus

    class Meta:
        model = models.WorkflowStatus

    aggregate_test_status = fields.String(attribute="status.aggregated_status")
    latest_builds = ma.Nested(BuildSummarySchema(exclude=('meta', 'links')),
                              attribute="status.latest_builds", many=True)
    reason = fields.Method("get_reason")

    def get_reason(self, workflow_version):
        return format_availability_issues(workflow_version.status)

    @post_dump
    def remove_skip_values(self, data, **kwargs):
        return {
            key: value for key, value in data.items()
            if value is not None
        }


class WorkflowVersionListItem(WorkflowSchema):

    subscriptionsOf: List[auth_models.User] = None
    public = fields.Boolean(attribute="public")
    latest_version = fields.String(attribute="latest_version.version")
    status = fields.Method("get_status")
    subscriptions = fields.Method("get_subscriptions")

    def __init__(self, *args, self_link: bool = True, subscriptionsOf: List[auth_models.User] = None, **kwargs):
        super().__init__(*args, self_link=self_link, **kwargs)
        self.subscriptionsOf = subscriptionsOf

    def get_status(self, workflow):
        try:
            result = {
                "aggregate_test_status": workflow.latest_version.status.aggregated_status,
                "latest_build": self.get_latest_build(workflow)
            }
            reason = format_availability_issues(workflow.latest_version.status)
            if reason:
                result['reason'] = reason
            return result
        except lm_exceptions.RateLimitExceededException as e:
            logger.debug(e)
            return {
                "aggregate_test_status": "not_available",
                "latest_build": [],
                "reason": str(e)
            }

    def get_latest_build(self, workflow):
        latest_builds = workflow.latest_version.status.latest_builds
        if latest_builds and len(latest_builds) > 0:
            return BuildSummarySchema(exclude=('meta', 'links')).dump(latest_builds[0])
        return None

    def get_subscriptions(self, w: models.Workflow):
        result = []
        if self.subscriptionsOf:
            for user in self.subscriptionsOf:
                s = user.get_subscription(w)
                if s:
                    result.append(SubscriptionSchema(exclude=('meta', 'links'), self_link=False).dump(s))
        return result


class ListOfWorkflows(ListOfItems):
    __item_scheme__ = WorkflowVersionListItem

    subscriptionsOf: List[auth_models.User] = None

    def __init__(self, *args, workflow_status: bool = False, subscriptionsOf: List[auth_models.User] = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.workflow_status = workflow_status
        self.subscriptionsOf = subscriptionsOf

    def get_items(self, obj):
        exclude = ['meta', 'links']
        if not self.workflow_status:
            exclude.append('status')
        if not self.subscriptionsOf or len(self.subscriptionsOf) == 0:
            exclude.append('subscriptions')
        return [self.__item_scheme__(exclude=tuple(exclude), many=False,
                                     subscriptionsOf=self.subscriptionsOf).dump(_) for _ in obj] \
            if self.__item_scheme__ else None


class SuiteSchema(ResourceMetadataSchema):
    __envelope__ = {"single": None, "many": "items"}
    __model__ = models.TestSuite

    class Meta:
        model = models.TestSuite

    uuid = ma.auto_field()
    roc_suite = fields.String(attribute="roc_suite")
    definition = fields.Method("get_definition")
    instances = fields.Nested(TestInstanceSchema(self_link=False, exclude=('meta',)),
                              attribute="test_instances", many=True)

    def get_definition(self, obj):
        to_skip = ['path']
        return {k: v for k, v in obj.definition.items() if k not in to_skip}

    @post_dump
    def remove_skip_values(self, data, **kwargs):
        return {
            key: value for key, value in data.items()
            if value is not None
        }


class ListOfSuites(ListOfItems):
    __item_scheme__ = SuiteSchema


class SuiteStatusSchema(ResourceMetadataSchema):
    __envelope__ = {"single": None, "many": "items"}
    __model__ = models.SuiteStatus

    class Meta:
        model = models.SuiteStatus

    suite_uuid = fields.String(attribute="suite.uuid")
    status = fields.String(attribute="aggregated_status")
    latest_builds = fields.Nested(BuildSummarySchema(exclude=('meta', 'links')), many=True)
    reason = fields.Method("get_reason")

    def get_reason(self, status):
        return format_availability_issues(status)

    @post_dump
    def remove_skip_values(self, data, **kwargs):
        return {
            key: value for key, value in data.items()
            if value is not None
        }


class ListOfTestInstancesSchema(ListOfItems):
    __item_scheme__ = TestInstanceSchema


class ListOfTestBuildsSchema(ListOfItems):
    __item_scheme__ = BuildSummarySchema
