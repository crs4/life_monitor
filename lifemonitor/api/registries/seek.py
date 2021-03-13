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
import os
import logging
from typing import Union
from lifemonitor.auth.models import User
from lifemonitor.common import EntityNotFoundException
from lifemonitor.api import models


# set module level logger
logger = logging.getLogger(__name__)


class SeekWorkflowRegistry(models.WorkflowRegistry):

    __mapper_args__ = {
        'polymorphic_identity': 'seek'
    }


class SeekWorkflowRegistryClient(models.WorkflowRegistryClient):

    def get_workflows_metadata(self, user, details=False):
        r = self._get(user, "/workflows?format=json")
        if r.status_code != 200:
            raise RuntimeError(f"ERROR: unable to get workflows (status code: {r.status_code})")
        workflows = r.json()['data']
        return workflows if not details \
            else [self.get_workflow_metadata(user, w['id']) for w in workflows]

    def get_workflow_metadata(self, user, w: Union[models.Workflow, str]):
        _id = w.external_id if isinstance(w, models.Workflow) else w
        r = self._get(user, f"/workflows/{_id}?format=json")
        if r.status_code != 200:
            raise RuntimeError(f"ERROR: unable to get workflow (status code: {r.status_code})")
        return r.json()['data']

    def build_ro_link(self, w: models.Workflow) -> str:
        return "{}?version={}".format(os.path.join(self.uri, "workflow", w.uuid), w.version)

    def filter_by_user(self, workflows: list, user: User):
        result = []
        allowed = [w["id"] for w in self.get_workflows_metadata(user)]
        for w in workflows:
            if str(w.external_id) in allowed:
                result.append(w)
        return result

    def get_external_id(self, uuid, version, user) -> str:
        """ Return CSV of uuid and version"""
        matches = [str(w['id']) for w in self.get_workflows_metadata(user, details=True)
                   if w['meta']['uuid'] == str(uuid)]
        if len(matches) != 1:
            raise EntityNotFoundException(models.Workflow, f"{uuid}_{version}")
        return matches[0]
