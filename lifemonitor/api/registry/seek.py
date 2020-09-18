from __future__ import annotations
import os
import logging

from lifemonitor.auth.models import User
from ..models import Workflow, WorkflowRegistryClient as _BaseRegistryClient


# set module level logger
logger = logging.getLogger(__name__)


class WorkflowRegistryClient(_BaseRegistryClient):

    def get_workflows_metadata(self, user):
        r = self._get(user, "/workflows?format=json")
        if r.status_code != 200:
            raise RuntimeError(f"ERROR: unable to get workflows (status code: {r.status_code})")
        return r.json()['data']

    def get_workflow_metadata(self, user, w: Workflow):
        r = self._get(user, f"/workflows/{w.external_id}?format=json")
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
