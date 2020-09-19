from __future__ import annotations
import os
import logging
from typing import Union

from lifemonitor.auth.models import User
from lifemonitor.common import EntityNotFoundException
from ..models import Workflow, WorkflowRegistryClient as _BaseRegistryClient


# set module level logger
logger = logging.getLogger(__name__)


class WorkflowRegistryClient(_BaseRegistryClient):

    def get_workflows_metadata(self, user, details=False):
        r = self._get(user, "/workflows?format=json")
        if r.status_code != 200:
            raise RuntimeError(f"ERROR: unable to get workflows (status code: {r.status_code})")
        workflows = r.json()['data']
        return workflows if not details \
            else [self.get_workflow_metadata(user, w['id']) for w in workflows]

    def get_workflow_metadata(self, user, w: Union[Workflow, str]):
        _id = w.external_id if isinstance(w, Workflow) else w
        r = self._get(user, f"/workflows/{_id}?format=json")
        if r.status_code != 200:
            raise RuntimeError(f"ERROR: unable to get workflow (status code: {r.status_code})")
        return r.json()['data']

    def build_ro_link(self, w: Workflow) -> str:
        return "{}?version={}".format(os.path.join(self.uri, "workflow", w.uuid), w.version)

    def filter_by_user(self, workflows: list, user: User):
        result = []
        allowed = [w["id"] for w in self.get_workflows_metadata(user)]
        for w in workflows:
            if str(w.external_id) in allowed:
                result.append(w)
        return result
