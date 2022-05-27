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
from lifemonitor.api.models.issues import WorkflowRepositoryIssue
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
    identifier = fields.String(attribute="client_name")
    uri = ma.auto_field()
    type = fields.Method("get_type")
    name = fields.String(attribute="server_credentials.name")

    def get_type(self, obj):
        return obj.type.replace('_registry', '')

    @post_dump
    def remove_skip_values(self, data, **kwargs):
        return {
            key: value for key, value in data.items()
            if value is not None
        }


class ListOfWorkflowRegistriesSchema(ListOfItems):
    __item_scheme__ = WorkflowRegistrySchema


class RegistryIndexItemSchema(ResourceMetadataSchema):
    __envelope__ = {"single": None, "many": "items"}
    __model__ = models.RegistryWorkflow

    class Meta:
        model = models.RegistryWorkflow

    identifier = fields.String(attribute="identifier")
    name = fields.String(attribute="name")
    latest_version = fields.String(attribute="latest_version")
    versions = fields.List(fields.String, attribute="versions")
    registry = ma.Nested(WorkflowRegistrySchema(exclude=('meta', 'links')), attribute="registry")
    links = fields.Method('get_links')

    def get_links(self, obj):
        links = ResourceMetadataSchema.get_links(self, obj)
        if links is not None:
            links['origin'] = obj.external_link
            return links
        return {
            'origin': obj.external_link
        }

    @post_dump
    def remove_skip_values(self, data, **kwargs):
        return {
            key: value for key, value in data.items()
            if value is not None
        }


class ListOfRegistryIndexItemsSchema(ListOfItems):
    __item_scheme__ = RegistryIndexItemSchema


class WorkflowIssueTypeSchema(ResourceMetadataSchema):
    __envelope__ = {"single": None, "many": "items"}

    identifier = fields.String(attribute="identifier")
    name = fields.String(attribute="name")
    labels = fields.Method("get_labels")
    depends_on = fields.String(attribute="get_depends_on")

    def get_labels(self, issue: WorkflowRepositoryIssue):
        return issue.labels

    def get_depends_on(self, issue: WorkflowRepositoryIssue):
        return [_.identifier for _ in issue.depends_on] if issue.depends_on else []


class ListOfWorkflowIssueTypesSchema(ListOfItems):
    __item_scheme__ = WorkflowIssueTypeSchema
    __exclude__ = ('meta', 'links')


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
    authors = fields.List(attribute="authors", cls_or_instance=fields.Dict())
    links = fields.Method('get_links')

    class Meta:
        model = models.WorkflowVersion
        additional = ('rocrate_metadata',)

    def get_links(self, obj: models.WorkflowVersion):
        links = {
            'origin': "local file uploaded" if obj.uri.startswith("tmp://") else obj.uri,
        }
        if obj.based_on:
            links['based_on'] = obj.based_on
        links['registries'] = {}
        for r_name, rv in obj.registry_workflow_versions.items():
            links['registries'][r_name] = rv.link
        return links

    def get_rocrate(self, obj: models.WorkflowVersion):
        rocrate = {
            'links': {
                'origin': "local file uploaded" if obj.uri.startswith("tmp://") else obj.uri,
                'metadata': urljoin(lm_utils.get_external_server_url(),
                                    f"workflows/{obj.workflow.uuid}/rocrate/{obj.version}/metadata"),
                'download': urljoin(lm_utils.get_external_server_url(),
                                    f"workflows/{obj.workflow.uuid}/rocrate/{obj.version}/download")
            }
        }
        if obj.based_on:
            rocrate['links']['based_on'] = obj.based_on
        rocrate['links']['registries'] = {}
        for r_name, rv in obj.registry_workflow_versions.items():
            rocrate['links']['registries'][r_name] = rv.link
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
    registries = fields.Method("get_registries")
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

    def get_registries(self, obj):
        result = []
        for r in obj.registries:
            result.append(WorkflowRegistrySchema(exclude=('meta', 'links'), self_link=False).dump(r))
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
                                           "is_latest", "submitter", "authors")).dump(v)
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
            'uuid': str(obj.testing_service.uuid),
            'url': obj.testing_service.url,
            'type': obj.testing_service._type.replace('_testing_service', '')
        }

    @post_dump
    def remove_skip_values(self, data, **kwargs):
        return {
            key: value for key, value in data.items()
            if value is not None
        }


def format_availability_issues(status: models.WorkflowStatus):
    issues = status.availability_issues
    logger.info(issues)
    if 'not_available' == status.aggregated_status and len(issues) > 0:
        return ', '.join([f"{i['issue']}: Unable to get resource '{i['resource']}' from service '{i['service']}'" if 'service' in i and 'resource' in i else i['issue'] for i in issues])
    return None


class BuildSummarySchema(ResourceMetadataSchema):
    __envelope__ = {"single": None, "many": None}
    __model__ = models.TestBuild

    class Meta:
        model = models.TestBuild

    def __init__(self, *args, self_link: bool = True, exclude_nested=True, **kwargs):
        exclude = set(kwargs.pop('exclude', ()))
        if exclude_nested:
            exclude = exclude.union(('suite', 'workflow'))
        super().__init__(*args, self_link=self_link, exclude=tuple(exclude), **kwargs)

    build_id = fields.String(attribute="id")
    suite_uuid = fields.String(attribute="test_instance.test_suite.uuid")
    status = fields.String()
    instance = ma.Nested(TestInstanceSchema(self_link=False, exclude=('meta',)),
                         attribute="test_instance")
    timestamp = fields.String()
    duration = fields.Integer()
    links = fields.Method('get_links')
    suite = ma.Nested(TestInstanceSchema(self_link=False,
                                         only=('uuid', 'name')), attribute="test_instance.test_suite")
    workflow = ma.Nested(WorkflowVersionSchema(self_link=False, only=('uuid', 'name', 'version')),
                         attribute="test_instance.test_suite.workflow_version")

    def get_links(self, obj):
        links = {
            'origin': obj.external_link
        }
        if self._self_link:
            links['self'] = self.self_link
        return links


class WorkflowStatusSchema(WorkflowVersionSchema):
    __envelope__ = {"single": None, "many": "items"}
    __model__ = models.WorkflowStatus

    class Meta:
        model = models.WorkflowStatus

    _errors = []

    aggregate_test_status = fields.Method("get_aggregate_test_status")
    latest_builds = fields.Method("get_latest_builds")
    reason = fields.Method("get_reason")

    def get_aggregate_test_status(self, workflow_version):
        try:
            return workflow_version.status.aggregated_status
        except Exception as e:
            logger.debug(e)
            self._errors.append(str(e))
            return "not_available"

    def get_latest_builds(self, workflow_version):
        try:
            return BuildSummarySchema(exclude=('meta', 'links'), many=True).dump(
                workflow_version.status.latest_builds)
        except Exception as e:
            logger.debug(e)
            self._errors.append(str(e))
            return []

    def get_reason(self, workflow_version):
        try:
            if(len(self._errors) > 0):
                return ', '.join([str(i) for i in self._errors])
            return format_availability_issues(workflow_version.status)
        except Exception as e:
            return str(e)

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
    versions = fields.Method("get_versions")

    def __init__(self, *args, self_link: bool = True,
                 workflow_versions: bool = False, subscriptionsOf: List[auth_models.User] = None, **kwargs):
        super().__init__(*args, self_link=self_link, **kwargs)
        self.subscriptionsOf = subscriptionsOf
        self.workflow_versions = workflow_versions

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
                "latest_build": None,
                "reason": str(e)
            }
        except Exception as e:
            logger.debug(e)
            return {
                "aggregate_test_status": "not_available",
                "latest_build": None,
                "reason": str(e)
            }

    def get_versions(self, workflow):
        try:
            if self.workflow_versions:
                schema = VersionDetailsSchema(only=("uuid", "version", "ro_crate", "is_latest"))
                return [schema.dump(v) for v in workflow.versions.values()]
            return None
        except Exception as e:
            logger.debug(e)
            return None

    def get_latest_build(self, workflow):
        try:
            latest_builds = workflow.latest_version.status.latest_builds
            if latest_builds and len(latest_builds) > 0:
                return BuildSummarySchema(exclude=('meta', 'links')).dump(latest_builds[0])
            return None
        except Exception as e:
            logger.debug(e)
            return None

    def get_subscriptions(self, w: models.Workflow):
        result = []
        if self.subscriptionsOf:
            for user in self.subscriptionsOf:
                s = user.get_subscription(w)
                if s:
                    result.append(SubscriptionSchema(exclude=('meta', 'links'), self_link=False).dump(s))
        return result

    @post_dump
    def remove_skip_values(self, data, **kwargs):
        return {
            key: value for key, value in data.items()
            if value is not None
        }


class ListOfWorkflows(ListOfItems):
    __item_scheme__ = WorkflowVersionListItem

    subscriptionsOf: List[auth_models.User] = None

    def __init__(self, *args,
                 workflow_status: bool = False, workflow_versions: bool = False,
                 subscriptionsOf: List[auth_models.User] = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.workflow_status = workflow_status
        self.workflow_versions = workflow_versions
        self.subscriptionsOf = subscriptionsOf

    def get_items(self, obj):
        exclude = ['meta', 'links']
        if not self.workflow_status:
            exclude.append('status')
        if not self.subscriptionsOf or len(self.subscriptionsOf) == 0:
            exclude.append('subscriptions')
        return [self.__item_scheme__(exclude=tuple(exclude), many=False,
                                     subscriptionsOf=self.subscriptionsOf,
                                     workflow_versions=self.workflow_versions).dump(_) for _ in obj] \
            if self.__item_scheme__ else None


class SuiteSchema(ResourceMetadataSchema):
    __envelope__ = {"single": None, "many": "items"}
    __model__ = models.TestSuite

    class Meta:
        model = models.TestSuite

    uuid = ma.auto_field()
    roc_suite = fields.String(attribute="roc_suite")
    name = ma.auto_field()
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
    __model__ = models.TestSuite

    class Meta:
        model = models.TestSuite

    suite_uuid = fields.String(attribute="uuid")
    status = fields.Method("get_aggregated_status")
    latest_builds = fields.Method("get_builds")
    reason = fields.Method("get_reason")
    _errors = []

    def get_builds(self, suite):
        try:
            return BuildSummarySchema(
                exclude=('meta', 'links'), many=True).dump(suite.status.latest_builds)
        except Exception as e:
            self._errors.append(str(e))
            logger.debug(e)
            return []

    def get_reason(self, suite):
        if(len(self._errors) > 0):
            return ", ".join(self._errors)
        try:
            return format_availability_issues(suite.status)
        except Exception as e:
            return str(e)

    def get_aggregated_status(self, suite):
        try:
            return suite.status.aggregated_status
        except Exception as e:
            self._errors.append(str(e))
            return 'not_available'

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
