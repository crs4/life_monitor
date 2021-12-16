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
from typing import List, Union

import requests
from lifemonitor.api import models
from lifemonitor.auth.models import User
from lifemonitor.exceptions import (EntityNotFoundException,
                                    LifeMonitorException)

from .registry import (RegistryWorkflow, WorkflowRegistry,
                       WorkflowRegistryClient)

# set module level logger
logger = logging.getLogger(__name__)


class SeekWorkflowRegistry(WorkflowRegistry):

    id = models.db.Column(models.db.Integer,
                          models.db.ForeignKey(WorkflowRegistry.id), primary_key=True)

    __mapper_args__ = {
        'polymorphic_identity': 'seek_registry'
    }

    def __init__(self, client_credentials, server_credentials):
        super().__init__('seek_registry', client_credentials, server_credentials)


class SeekWorkflowRegistryClient(WorkflowRegistryClient):

    def get_workflows_metadata(self, user, details=False):
        r = self._get(user, f"{self.registry.uri}/workflows?format=json")
        if r.status_code != 200:
            raise RuntimeError(f"ERROR: unable to get workflows (status code: {r.status_code})")
        workflows = r.json()['data']
        return workflows if not details \
            else [self.get_workflow_metadata(user, w['id']) for w in workflows]

    def get_workflow_metadata(self, user, w: Union[models.WorkflowVersion, str]):
        _id = w.workflow.external_id if isinstance(w, models.WorkflowVersion) else w
        r = self._get(user, f"{self.registry.uri}/workflows/{_id}?format=json")
        if r.status_code != 200:
            raise RuntimeError(f"ERROR: unable to get workflow (status code: {r.status_code})")
        return r.json()['data']

    def get_index(self, user: User) -> List[RegistryWorkflow]:
        result = []
        for w in self.get_workflows_metadata(user):
            result.append(RegistryWorkflow(self.registry, w['id'], w['attributes']['title']))
        return result

    def get_index_workflow(self, user: User, workflow_identifier: str) -> RegistryWorkflow:
        try:
            w = self.get_workflow_metadata(user, workflow_identifier)
            return RegistryWorkflow(self.registry, w['id'], w['attributes']['title'],
                                    latest_version=w['attributes']['version'],
                                    versions=[_['version'] for _ in w['attributes']['versions']]) if w else None
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                raise EntityNotFoundException(WorkflowRegistry, entity_id=workflow_identifier)
            raise LifeMonitorException(original_error=e)

    def get_external_link(self, external_id: str, version: str) -> str:
        version_param = '' if not version or version == 'latest' else f"?version={version}"
        return f"{self.registry.uri}/workflows/{external_id}{version_param}"

    def get_rocrate_external_link(self, external_id: str, version: str) -> str:
        return f'{self.registry.uri}/workflows/{external_id}/ro_crate?version={version}'

    def filter_by_user(self, workflows: list, user: User):
        result = []
        allowed = [w["id"] for w in self.get_workflows_metadata(user)]
        for w in workflows:
            if str(w.workflow.external_id
                   if isinstance(w, models.WorkflowVersion) else w.external_id) in allowed:
                result.append(w)
        return result

    def get_external_id(self, uuid, version, user) -> str:
        matches = [str(w['id']) for w in self.get_workflows_metadata(user, details=True)
                   if w['meta']['uuid'] == str(uuid)]
        if len(matches) != 1:
            raise EntityNotFoundException(models.WorkflowVersion, f"{uuid}_{version}")
        return matches[0]

    def get_external_uuid(self, identifier, version, user) -> str:
        return self.get_workflow_metadata(user, identifier)['meta']['uuid']
