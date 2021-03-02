from __future__ import annotations

import logging
import os
from typing import Union

from lifemonitor.api import models
from lifemonitor.auth.models import User
from lifemonitor.exceptions import EntityNotFoundException
from .registry import WorkflowRegistry, WorkflowRegistryClient

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

    def build_ro_link(self, w: models.WorkflowVersion) -> str:
        return "{}?version={}".format(os.path.join(self.uri, "workflow", w.uuid), w.version)

    def filter_by_user(self, workflows: list, user: User):
        result = []
        allowed = [w["id"] for w in self.get_workflows_metadata(user)]
        for w in workflows:
            if str(w.workflow.external_id) in allowed:
                result.append(w)
        return result

    def get_external_id(self, uuid, version, user) -> str:
        """ Return CSV of uuid and version"""
        matches = [str(w['id']) for w in self.get_workflows_metadata(user, details=True)
                   if w['meta']['uuid'] == str(uuid)]
        if len(matches) != 1:
            raise EntityNotFoundException(models.WorkflowVersion, f"{uuid}_{version}")
        return matches[0]
